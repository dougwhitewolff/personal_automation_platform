---
number: 018
title: Memory and retrieval strategy
status: accepted
date: 2026-04-28
---

# 018 — Memory and retrieval strategy

**Status:** accepted
**Date:** 2026-04-28

## Question

What does the assistant *remember* across transcripts, and how does that memory get into LLM context at the right moment? Specifically:

1. **What gets indexed** — transcripts, verdicts, pipeline outputs, agent runs, all of the above?
2. **How it's stored** — single corpus table or specialized tables per kind?
3. **How it's chunked** — whole-item embeddings, sentence chunks, semantic chunks?
4. **How it's retrieved** — extension of [007](007-primary-database-and-vector-store.md)'s `RetrievalStore`, with what filtering/ranking knobs?
5. **How retrieval results enter LLM context** — naive top-k, summarized, recency-weighted, citation-anchored?

[002](002-learning-model-and-feedback-architecture.md) committed verdicts to the retrieval corpus as first-class data. [007](007-primary-database-and-vector-store.md) committed to pgvector + `RetrievalStore` abstraction. This decision fills in the memory layer specifics.

## Why this matters now

Memory is what makes the system genuinely *useful* over time vs. a one-shot LLM. A pipeline that drafts a follow-up with Sarah should know what was last drafted for Sarah, what verdict the user gave, and what context exists from prior transcripts about Sarah. Without memory, every pipeline run starts from zero.

The shape decided here also affects:
- **[016] (agents and tools)** — `searchTranscripts`, `searchVerdicts`, and possibly a unified `recallMemory` tool consume this layer. Agent-driven retrieval depends on the interface.
- **[017] (pipeline dispatch)** — Stage 3+ LLM classifier can use memory for context-aware routing.
- **Q21 (observability)** — retrieval queries and their results need to be inspectable per pipeline run.
- **Q25 (compliance)** — memory contents are sensitive (transcripts of personal life); retention policy applies.

## Sub-decisions

### 1. What gets indexed (the corpus)

V1 corpus contains four item kinds:

| Kind | Content | Why |
|---|---|---|
| `transcript` | Full transcript text + metadata | Recall prior voice memos by topic / person |
| `verdict` | The user's accept/reject/edit + delta + reason (if given) | Learning loop per [002](002-learning-model-and-feedback-architecture.md); "last time, Doug edited X out of similar drafts" |
| `output` | Pipeline outputs that were delivered (accepted artifacts) | Recall what's already been drafted/sent so we don't duplicate |
| `pipeline_run_summary` | Short summary of what a pipeline did, written by the pipeline at completion | Recall "the system already handled the Sarah follow-up" without re-reading every step |

Each item has: `id`, `kind`, `tenant_id`, `created_at`, `content` (text used for embedding + display), `embedding` (vector), `metadata` (JSONB; kind-specific fields like `contact_id`, `run_id`, `transcript_id`, `outcome`).

### 2. Schema: single `memory_items` table with `kind` discriminator

One table, polymorphic. Reasons:
- Most queries are "find anything related to Sarah" — works naturally across kinds in one query
- pgvector index efficiency is best with one large index over one larger column
- Adding new kinds (agent_runs, tool_calls if we ever want them retrievable) is a config change, not a migration
- RLS policies are written once, not per-kind

```sql
create table memory_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  kind text not null check (kind in ('transcript', 'verdict', 'output', 'pipeline_run_summary')),
  source_id uuid not null,        -- id of the underlying entity (transcript.id, verdict.id, etc.)
  content text not null,           -- the text that was embedded
  embedding vector(1536) not null, -- OpenAI text-embedding-3-small dimensionality
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index memory_items_embedding_hnsw_idx on memory_items
  using hnsw (embedding vector_cosine_ops);
create index memory_items_tenant_kind_idx on memory_items (tenant_id, kind, created_at desc);
create index memory_items_metadata_gin on memory_items using gin (metadata);
```

RLS policies match [008](008-multi-tenancy-model.md). Foreign keys aren't enforced to underlying tables (they're cross-kind); `source_id` + `kind` is the logical reference.

### 3. Chunking: whole-item embeddings in v1

Voice memos are short (<5 min ≈ <750 words). Verdicts are short (delta + reason). Pipeline outputs are short. Pipeline-run summaries are deliberately short (one paragraph max).

V1 embeds the whole item as a single vector. No chunking. Simpler, cheaper, fewer rows, and short content fits comfortably in the embedding model's context.

When/if we ever ingest long-form content (a customer pastes a multi-page document into a transcript via direct API), we add semantic chunking at that point. Future-extension pattern documented; not v1 scope.

### 4. Retrieval interface: `RetrievalStore` extended with filters and weighting

Extends [007](007-primary-database-and-vector-store.md)'s interface:

```ts
interface RetrievalStore {
  upsert(items: MemoryItem[]): Promise<void>;
  delete(ids: string[]): Promise<void>;

  // Vector-similarity search with filters
  search(input: {
    query: number[];               // embedding of the query text
    tenantId: string;              // always required (RLS also enforces)
    filter?: {
      kinds?: Kind[];              // restrict to specific kinds
      contactId?: string;          // metadata-filtered
      since?: Date;                // recency window
      until?: Date;
      excludeIds?: string[];       // skip already-cited items
    };
    k?: number;                    // top-K, default 10
    minScore?: number;             // similarity floor, default 0.3
    rerankBy?: 'similarity' | 'recency-weighted'; // default 'similarity'
  }): Promise<SearchResult[]>;

  // Future v2: hybrid (text + vector) search
  hybridSearch?(...): Promise<SearchResult[]>;
}

type SearchResult = {
  item: MemoryItem;
  score: number;          // raw similarity score
  rerankedScore?: number; // if rerankBy was used
};
```

`recency-weighted` rerank applies a decay function: `effectiveScore = similarity * exp(-ageInDays / halfLifeDays)`. Half-life default: 30 days, tunable. This solves the "10 prior transcripts about Sarah, but the most recent one matters most" pattern.

### 5. LLM context insertion: explicit `recallMemory` tool, structured prompt template

Memory enters LLM context via an explicit tool call, not invisible prepending. Per [016](016-agent-and-tool-architecture.md), agents are scoped to allowed tools — `recallMemory` is one of them.

```ts
// tools/recall-memory.ts
export default defineTool({
  id: 'recallMemory',
  description: 'Searches the assistant\'s memory for items related to the query. Use when you need prior context about a person, topic, or recurring theme.',
  inputSchema: z.object({
    query: z.string(),
    kinds: z.array(z.enum(['transcript', 'verdict', 'output', 'pipeline_run_summary'])).optional(),
    contactId: z.string().optional(),
    sinceDays: z.number().min(1).max(365).optional(),
    k: z.number().min(1).max(20).default(8),
    rerankBy: z.enum(['similarity', 'recency-weighted']).optional(),
  }),
  outputSchema: z.object({
    results: z.array(z.object({
      id: z.string(),
      kind: z.string(),
      content: z.string(),
      capturedAt: z.string(),
      score: z.number(),
    })),
  }),
  async execute(input, ctx) {
    return withTenant(ctx.tenantId, async () => {
      const queryEmbedding = await embed(input.query);
      const results = await retrievalStore.search({
        query: queryEmbedding,
        tenantId: ctx.tenantId,
        filter: { kinds: input.kinds, contactId: input.contactId, since: input.sinceDays ? daysAgo(input.sinceDays) : undefined },
        k: input.k,
        rerankBy: input.rerankBy,
      });
      return { results: results.map(formatForLLM) };
    });
  },
});
```

Pipelines and agents that need memory call `recallMemory(...)`. The LLM sees structured results with citations (each result has an `id` it can reference in output), enabling "according to your transcript on Tuesday..." style grounded responses.

**Why explicit tool over invisible context-prepending:**
- Observability — every memory recall is a logged tool call, visible in Inngest's run inspector
- Cost — only retrieves when actually needed; no wasted tokens prefixed to every call
- Agent control — agents can decide *what* to recall and *when*; not forced to consume one prepared chunk
- Citation-anchored output — results have IDs that flow through to drafted artifacts as references

### 6. Embedding model: OpenAI `text-embedding-3-small` (1536 dims)

Matches the `vector(1536)` schema. Cheap (~$0.02 per million tokens), fast, supported by Vercel AI SDK. Anthropic doesn't have an embeddings model in 2026, so this is OpenAI-only for now. Compatible with our LLM provider strategy from [014](014-llm-provider-strategy.md).

When we want to swap models (e.g., to a higher-dim model for better recall), it's a re-embedding migration: spin up a new column, backfill, swap, drop the old. Bounded operation.

## Decision

**Memory and retrieval architecture as drafted.** Decided 2026-04-28.

Single `memory_items` table with `kind` discriminator (`transcript` | `verdict` | `output` | `pipeline_run_summary`). Whole-item embeddings via OpenAI `text-embedding-3-small` (1536 dims). HNSW pgvector index. RLS enforces tenant isolation per [008](008-multi-tenancy-model.md). Retrieval via extended `RetrievalStore.search(...)` with kind/contact/recency filters and optional recency-weighted rerank (30-day half-life default). Memory enters LLM context via an explicit `recallMemory` tool — no invisible prepending.

## Consequences

**Locks in:**
- `memory_items` table schema with HNSW index, GIN index on metadata, and tenant/kind/created_at composite index.
- Polymorphic kind discriminator approach. Adding new kinds is a config change, not a migration.
- OpenAI `text-embedding-3-small` (1536 dims). Re-embedding migration path documented for future model swaps.
- Retrieval interface extends [007](007-primary-database-and-vector-store.md)'s `RetrievalStore` with filter and rerank support.
- Recency-weighted rerank with `effectiveScore = similarity * exp(-ageInDays / halfLifeDays)`. Half-life default: 30 days, tunable per-call.
- `recallMemory` tool registered in `tools/`, scoped tenant-safe by [016](016-agent-and-tool-architecture.md)'s `withTenant` wrapper. Pipelines and agents call it explicitly.
- Citation anchoring: every search result returns an `id` that downstream draft artifacts reference. Helper utilities in `lib/memory/cite.ts` to make this automatic.
- Whole-item embeddings in v1; future-extension pattern documented for chunking when long-form content appears.

**Creates / constrains follow-up decisions:**
- **Q21 (observability)** — `recallMemory` tool calls and search results need to be inspectable per pipeline run.
- **Q25 (compliance)** — `memory_items` is highly sensitive PII; retention policy applies. The audit/retention story for memory is part of the broader compliance decision.
- **Future v2 work:** hybrid search (vector + tsvector) when retrieval-failure cases warrant; chunking for long-form content if it appears; alternative embedding models if OpenAI's pricing or quality changes.

**Risks accepted:**
- OpenAI-only for embeddings in v1 (no Anthropic alternative in 2026). Mitigation: bounded migration when needed.
- Fixed 30-day half-life is a guess. Mitigation: tunable per-call; revisit when actual recall failures surface in dogfooding.
- Citation anchoring requires pipeline code to preserve cited IDs. Mitigation: `lib/memory/cite.ts` helpers; can be added without restructuring the memory layer.
