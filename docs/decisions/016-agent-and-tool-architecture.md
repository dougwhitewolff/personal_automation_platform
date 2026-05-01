---
number: 016
title: Agent and tool architecture
status: accepted
date: 2026-04-28
---

# 016 — Agent and tool architecture

**Status:** accepted
**Date:** 2026-04-28

## Question

[015](015-pipeline-definition-format.md) settled the *orchestration* layer (deterministic pipelines as TypeScript code with structured helpers). This decision settles the *sub-task* layer: when a pipeline step needs open-ended LLM-driven work (e.g., "look up Sarah's relationship history and summarize what's relevant for Tuesday's meeting"), how is that work expressed?

Five interrelated sub-decisions:

1. **Agent shape.** TS-defined `defineAgent({...})` vs. markdown-based `SKILL.md` files vs. hybrid?
2. **Tool registry.** How do tools (functions agents and pipelines call) get declared, scoped, and audited?
3. **Invocation surface.** How does a pipeline step invoke an agent?
4. **Execution model.** Max iterations, timeout, cost caps — how are agent runs bounded?
5. **Cross-product reuse.** Are tools shared between voice-app and 4tradesCRM, or duplicated?

## Why this matters now

Pipelines orchestrate. Agents do *the parts that need judgment* — choosing what to look up, deciding when enough context has been gathered, picking a draft format. Without a well-shaped agent layer, every judgment-needing step becomes either (a) a hard-coded if-else tree the LLM is wedged into, or (b) a free-form `generateText` call with no guardrails. Both age poorly.

This decision also touches:

- **[007] (data layer)** — agents query the retrieval store and write tool-specific records.
- **[008] (multi-tenancy)** — every tool call must be tenant-scoped; agents must not leak across tenants.
- **[014] (LLM provider)** — agent invocations use Vercel AI SDK's tool-calling feature.
- **[015] (pipeline format)** — pipelines invoke agents via `step.invokeAgent`.
- **4tradesCRM integration** — some tool concepts (e.g., `createLead`, `searchContacts`) overlap with the CRM's domain. Reusability shape decided here.

## Sub-decisions

### Sub-decision 1 — Agent shape: **TS-defined `defineAgent({...})`**

Settled in conversation (2026-04-28). Doug confirmed non-engineer agent authoring is a v2+ concern; for v1, type safety + refactor support of TS-defined agents wins decisively. The asymmetric migration kicker also held: A → B (export to SKILL.md) is a serializer's worth of work; B → A would be expensive re-importing.

```ts
// agents/research-relationship.ts
import { defineAgent } from '@/lib/agents';
import { searchTranscripts, queryRecentRevenue, listCalendarEvents } from '@/tools';
import { z } from 'zod';

export default defineAgent({
  id: 'research-relationship',
  description: 'Gathers prior interactions, notes, and recent revenue context for a contact.',
  modelTier: 'high-quality',
  tools: [searchTranscripts, queryRecentRevenue, listCalendarEvents],
  maxIterations: 8,
  timeoutMs: 5 * 60 * 1000,
  costCapUsd: 0.50,
  systemPrompt: `You are a research assistant. Given a contact, gather prior context that
would help in an upcoming meeting. Use tools to search transcripts, calendar events, and
revenue data. Return a structured summary.`,
  inputSchema: z.object({
    contactId: z.string(),
    dateRange: z.object({ from: z.string(), to: z.string() }).optional(),
    purpose: z.string().describe('Why are we researching — meeting, follow-up, etc.'),
  }),
  outputSchema: z.object({
    summary: z.string(),
    keyMoments: z.array(z.object({
      date: z.string(),
      description: z.string(),
      sourceType: z.enum(['transcript', 'calendar', 'revenue']),
    })),
    notesForMeeting: z.string().optional(),
  }),
});
```

Agent metadata is intentionally a strict superset of SKILL.md frontmatter conventions. A future serializer can export `defineAgent` definitions to SKILL.md format if/when non-engineer authoring or external skill-marketplace publishing becomes a real need.

### Sub-decision 2 — Tool registry: **file-per-tool, auto-discovered, Zod-typed I/O**

```ts
// tools/search-transcripts.ts
import { defineTool } from '@/lib/tools';
import { z } from 'zod';
import { withTenant } from '@/lib/db';

export default defineTool({
  id: 'searchTranscripts',
  description: 'Searches the user\'s transcript corpus for entries matching the query.',
  inputSchema: z.object({
    query: z.string(),
    contactId: z.string().optional(),
    limit: z.number().min(1).max(50).default(10),
  }),
  outputSchema: z.object({
    results: z.array(z.object({
      transcriptId: z.string(),
      capturedAt: z.string(),
      excerpt: z.string(),
      score: z.number(),
    })),
  }),
  async execute(input, ctx) {
    return withTenant(ctx.tenantId, async (db) => {
      // ...semantic search via RetrievalStore from 007
    });
  },
});
```

Conventions:
- One file per tool in `tools/` directory.
- Each tool exports a default `defineTool(...)` call.
- Auto-discovered via `tools/registry.ts`.
- Every tool execution is scoped via `ctx.tenantId` — tools cannot bypass tenant isolation by construction.
- Every tool call is audit-logged: `tool_id`, `agent_id` (if invoked from agent), `tenant_id`, `input_summary`, `duration_ms`, `error?`.
- Tools have no LLM dependency. Pure functions over typed inputs and outputs.

### Sub-decision 3 — Invocation surface: **`step.invokeAgent(agentId, { input })`**

```ts
// inside a pipeline
const research = await step.invokeAgent('research-relationship', {
  input: {
    contactId: extracted.contactId,
    purpose: 'Tuesday Q3 planning meeting',
  },
});
// `research` is typed via the agent's outputSchema
```

Two alternative surfaces considered and rejected for v1:

- **`step.delegateToAgent({ goal, availableAgents: [...] })`** — orchestrator picks agent based on goal description. Rejected: another LLM call to pick the agent adds cost, latency, and an extra failure surface. Pipelines know which agent they want.
- **Agent-to-agent invocation** (one agent calls another) — out of v1 scope. Risk of recursion and unbounded cost. Revisit if a real use case emerges.

`step.invokeAgent`:
- Is a thin wrapper around Vercel AI SDK's `generateText` with `tools` parameter (per [014](014-llm-provider-strategy.md)).
- Is a durable Inngest step — agent runs survive process crashes; Inngest's retry semantics apply.
- Surfaces in Inngest's run inspector with the agent's tool-calling history visible step-by-step.
- Enforces the agent's `maxIterations`, `timeoutMs`, and `costCapUsd` limits.

### Sub-decision 4 — Execution model: **hard limits with structured failure**

Each agent declares:
- `maxIterations` (default 8) — hard cap on tool-calling rounds.
- `timeoutMs` (default 5 minutes) — wall-clock cap.
- `costCapUsd` (default $0.50) — token-cost cap, computed via per-call usage from [014](014-llm-provider-strategy.md).

When any limit is hit, the agent run terminates with a structured `AgentLimitExceeded` error:

```ts
{
  reason: 'iterations' | 'timeout' | 'cost',
  partialOutput?: Partial<AgentOutput>,
  toolCallsMade: number,
  costSoFarUsd: number,
}
```

Pipelines decide how to handle it — usually by surfacing to the user via `step.review` with a message like "Research couldn't complete — proceed with partial info?"

Limits are tunable per-agent. Some agents need higher caps for genuinely hard tasks; others should be much tighter. Defaults are conservative.

### Sub-decision 5 — Cross-product reuse: **voice-app only in v1; extract to shared package in v2 if patterns warrant**

Tools live in voice-app's `tools/` directory in v1. 4tradesCRM has its own voice-capture feature with its own conventions (`backend/src/voice-capture/`). They're separate concerns in v1.

Triggers for extracting to a shared package (`@4trades/tools` or similar) at v2:
- Both products want to call the same tool with identical semantics (`createLead`, `searchContacts`, `scheduleReminder`)
- The CRM begins exposing more LLM-driven features that would benefit from the agent + tool architecture
- Maintaining two parallel tool implementations becomes painful

Until any of those trigger, v1 keeps the codebases separate. Voice-app pipelines that need to write CRM data call the CRM's REST API (per [009](009-crm-integration-shape.md)), not a shared tool function. The CRM's REST surface is the integration boundary, not shared TypeScript code.

## Decision

**Agent and tool architecture as outlined above.** Decided 2026-04-28.

Three-layer architecture is canonical from this decision forward:

- **`pipelines/`** — deterministic orchestration (per [015](015-pipeline-definition-format.md))
- **`agents/`** — TS-defined `defineAgent({...})` for LLM-driven sub-tasks
- **`tools/`** — TS-defined `defineTool({...})` for tenant-scoped, audited, deterministic functions

Agents invoked from pipelines via `step.invokeAgent(agentId, { input })` (durable Inngest step wrapping Vercel AI SDK's tool-calling). Hard execution limits per agent (`maxIterations: 8`, `timeoutMs: 5min`, `costCapUsd: $0.50` defaults; tunable). Structured `AgentLimitExceeded` errors when caps are hit. Cross-product tool sharing with 4tradesCRM deferred to v2 if patterns warrant.

## Consequences

**Locks in:**
- `lib/agents/define.ts` exports `defineAgent(opts)`. Validates metadata via Zod at load time. Wraps Vercel AI SDK's `generateText` with tool-calling and limit enforcement.
- `lib/tools/define.ts` exports `defineTool(opts)`. Wraps implementation with tenant-scoping and audit logging.
- `agents/` and `tools/` directories at the project root. One file per agent/tool. Auto-discovered registries.
- `step.invokeAgent` added to the helper set from [015](015-pipeline-definition-format.md). Returns typed output via the agent's `outputSchema`.
- Audit infrastructure: `agent_runs` table (agent_id, tenant_id, input/output hashes, iterations_used, duration_ms, cost_usd) + `tool_calls` table (tool_id, agent_run_id?, tenant_id, input_summary, duration_ms, success).
- Three-layer architecture is canonical: pipelines orchestrate; agents do open-ended LLM work; tools do deterministic work invoked by both.

**Creates / constrains follow-up decisions:**
- **Q19 (memory / retrieval)** — retrieval store consumed by tools (e.g., `searchTranscripts`); agents call those tools rather than calling retrieval directly.
- **Q21 (observability)** — `agent_runs` and `tool_calls` are first-class observability surfaces; dashboard's pipeline-debug view drills into agent runs, then into tool calls.
- **Q25 (compliance)** — agent inputs/outputs are sensitive; retention policy must address them alongside transcripts.

**Future v2 work (deferred):**
- SKILL.md export serializer (when non-engineer authoring or external skill marketplace becomes a real need).
- `@4trades/tools` shared package (when cross-product reuse patterns warrant).
- Agent-to-agent invocation (when a real recursive use case emerges; bounded by clear cost/iteration caps).
- `step.delegateToAgent({ goal, availableAgents })` orchestrator-driven dispatch (when goals need dynamic agent selection).

**Risks accepted:**
- Hard limits will sometimes terminate runs mid-task. Mitigation: structured `AgentLimitExceeded` gives partial output; `step.review` from [003](003-primary-user-surface.md) routes partial result to user.
- Agents may pick wrong tools or loop. Mitigation: `maxIterations` cap; observability via Inngest run inspector; per-agent prompt/toolset refinement over time.
- TS-defined agents not authorable by non-engineers in v1. Mitigation: SKILL.md export path designed for; deferred to v2+.
- Tool registry duplication with 4tradesCRM. Mitigation: migration trigger documented; extract to shared package when patterns warrant.
