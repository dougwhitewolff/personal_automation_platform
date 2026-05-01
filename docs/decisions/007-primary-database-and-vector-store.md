---
number: 007
title: Primary database and vector store
status: accepted
date: 2026-04-28
---

# 007 — Primary database and vector store

**Status:** accepted
**Date:** 2026-04-28

> **Scope note (2026-04-28):** Originally scoped as Q7 (primary database) only. Research on coupling with the vector-store decision (originally Q8) showed the choice is tightly intertwined — picking Postgres-with-pgvector resolves both, and the `RetrievalStore` abstraction described below is the real hedge against future migration. Q8 was therefore folded into this decision.

## Question

Where does our application data live? Inngest owns durable run-step state per [006](006-workflow-engine.md), so the database is *not* the workflow state store. It is, however, source of truth for:

- Users / tenants
- Transcripts (raw, ingested via email)
- Pipeline runs (high-level metadata; step-level state lives in Inngest)
- Pipeline outputs (drafts, accepted artifacts)
- **Verdicts** — accept/reject/edit deltas, first-class per [002](002-learning-model-and-feedback-architecture.md)
- The retrieval corpus (transcripts + outputs + verdicts) for in-context learning at pipeline-run time
- Pipeline definitions (or pointers to them; depends on Q15)
- Native-target delivery records (what got sent where, when)

The realistic answer is Postgres in 2026 for a TS+Next.js stack. The actual question is *which* Postgres — managed-and-bundled (Supabase), serverless (Neon), platform-co-located (Railway), or self-hosted (Fly/Render Postgres).

## Why this matters now

The database choice constrains several downstream decisions and locks in a vendor relationship for the most foundational durable state in the system (everything except workflow run-step state, which Inngest owns):

- **Q8 (vector store)** — Supabase and Neon both ship pgvector first-class, Railway supports the extension; choosing one of these likely resolves Q8 in favor of pgvector.
- **Q9 (multi-tenancy model)** — Postgres RLS is the natural fit; Supabase has the most polished tooling around RLS-with-auth integration.
- **Q10 (auth provider)** — Supabase Auth is bundled into Supabase and integrates cleanly with RLS; choosing Supabase makes Supabase Auth the cheapest v1 path. Choosing Neon/Railway/self-host means picking auth separately (Clerk, WorkOS, Auth.js, etc.).
- **Q11 (hosting)** — DB choice influences hosting locality (Supabase's regions, Neon's regions, Railway's regions) and round-trip latency.

Switching primary database vendors after meaningful data accumulates is painful — schema migrations are doable but RLS rewrites, auth migrations, and re-indexing are all real costs. This is a "decide once" decision in practice.

## Options

### Option A — Supabase

Managed Postgres bundled with Auth, Realtime, Storage, Edge Functions, and pgvector. The dominant batteries-included platform for TS+Next.js apps in 2026. Generous free tier; clear pricing curve.

**Steel-manned reasoning:** Supabase is the maximum batteries-included experience for a solo dev. One platform, one dashboard, one billing surface, one SDK. RLS integrates with Supabase Auth out of the box — the canonical multi-tenancy pattern is `auth.uid() = user_id` in policies, and that maps directly onto our "structurally multi-tenant from day one" requirement from 001. pgvector is included natively, which likely resolves Q8 with no additional vendor. Storage handles email attachment buffering and any file artifacts pipelines produce. Realtime can power dashboard live updates ("your run just finished"). The free tier covers v1 author-only scale comfortably. Most importantly: every hour saved on integration plumbing is an hour spent on the actual product, and Supabase removes more integration plumbing than any other choice.

**Priors / assumptions this rests on:**
- Bundled features genuinely save time vs. assembling Neon + Clerk + S3 + Pinecone — confidence: **high**
- Supabase's RLS-with-auth pattern handles multi-tenancy cleanly — confidence: **high**
- Supabase free tier covers v1 author-only scale — confidence: **high**
- Vendor consolidation reduces operational surface meaningfully — confidence: **high**
- Lock-in to Supabase is bounded (it's standard Postgres + SDKs; migration is painful but not impossible) — confidence: **medium**
- Supabase Auth is sufficient for v1 multi-tenant patterns (orgs/teams come if needed later) — confidence: **medium** (B2C-leaning by design; orgs/teams patterns require setup but work)

### Option B — Neon

Serverless Postgres with branching, pure-DB focus, no bundled features. Branches give each PR its own ephemeral DB. Scales to zero on free tier; cold start in the few-hundred-ms range.

**Steel-manned reasoning:** Neon is the best pure-Postgres experience available. Branching is a killer feature for solo devs — every feature branch gets its own isolated DB, which makes destructive migrations and data experiments safe. Serverless scaling means dev/staging environments cost nothing when idle. The decoupled philosophy keeps the architecture clean: the DB is just a DB; auth, storage, and vector store are picked best-of-breed (Clerk, R2, Pinecone or pgvector). For a long-lived product where you may eventually want to swap any one of those vendors, decoupling from the start is much cheaper than untangling later. pgvector is supported, so Q8 can resolve to pgvector even on Neon.

**Priors / assumptions this rests on:**
- Branching is genuinely valuable for solo-dev workflow — confidence: **medium-high** (real value, but solo devs often work on one branch at a time)
- Decoupled best-of-breed is worth the integration cost in v1 — confidence: **medium-low** (more vendors to wire up; solo dev pays the integration time directly)
- Cold-start latency (~few hundred ms) is acceptable for v1 — confidence: **medium-high** (Inngest pipelines are async; user-facing dashboard cold starts are the only concern, and warm-up patterns mitigate)
- Neon's free tier (~192 MB DB) covers v1 — confidence: **medium** (tight; might force an early upgrade once verdict corpus grows)
- Composing Neon + separate auth + separate storage stays simple as the system grows — confidence: **medium**

### Option C — Railway Postgres

Managed Postgres co-located with the app on Railway's platform. Always-on, no cold starts. Less feature-rich than Supabase. Same dashboard and billing as the app, if the app is on Railway.

**Steel-manned reasoning:** Simplest possible operational model — same platform for app and DB, one dashboard, one bill, one set of credentials, low-latency in-region access. No cold starts, no warm-up tricks needed. For a solo dev who values consistency and predictability over feature breadth, Railway delivers a "just works" experience without Supabase's surface area or Neon's serverless quirks. Postgres is Postgres; pgvector is installable; RLS works the same.

**Priors / assumptions this rests on:**
- Co-located deploy meaningfully reduces ops complexity vs. Supabase or Neon — confidence: **medium** (real but small benefit)
- Railway's Postgres performance is comparable to Supabase/Neon — confidence: **medium-high**
- Railway's free tier / pricing covers v1 — confidence: **medium** (more limited than Supabase/Neon free tiers)
- Single-vendor concentration on Railway (app + DB + maybe more) is acceptable — confidence: **medium-high**
- Railway's longevity and product direction are stable — confidence: **medium** (smaller vendor; some platform risk)

### Option D — Self-hosted Postgres (Fly Postgres / Render Postgres / similar)

Run Postgres on your own infrastructure. Fly's managed Postgres or Render's managed Postgres are the closest "self-host" options that don't require true infrastructure management; running on a VM is also possible.

**Steel-manned reasoning:** Maximum control. Cheapest at scale. No vendor data-egress concerns or surprise billing changes. For a system where data is the moat (verdict corpus, user transcripts, pipeline outputs), owning the DB infrastructure is foundational. The architecture stays vendor-neutral; if you ever need to migrate clouds or change hosting, the DB comes with you.

**Priors / assumptions this rests on:**
- Solo dev can operate self-hosted Postgres reliably (backups, monitoring, scaling, patching) — confidence: **low** (real ops burden; one weekend a quarter at minimum)
- Cost savings materialize at v1 scale — confidence: **low** (free tiers on managed are very generous; self-host costs more in v1, less at scale)
- Vendor-neutral data ownership matters in v1 — confidence: **low-medium** (matters in theory; rarely materializes as a v1 concern)
- Self-host is reversible — confidence: **high** (can migrate to managed later cleanly)

## Recommendation

**Option A — Supabase.**

For a solo dev with multi-tenancy structurally required from day one, retrieval-over-verdicts as a core architectural commitment, and a bias toward shipping fast, Supabase is the highest-leverage choice. It bundles three decisions: primary DB (Q7), vector store (Q8 — pgvector built-in), and a strong default for auth (Q10 — Supabase Auth integrates with RLS cleanly). RLS gives us multi-tenancy enforcement in the database itself, which is the right place for it — app-layer enforcement is more error-prone, and Supabase's tooling around `auth.uid() = user_id` policies is the most polished in the ecosystem. The free tier covers v1; the paid tier ($25/mo as of 2026) covers significant growth. Vendor consolidation eliminates a meaningful chunk of integration plumbing that Neon + Clerk + R2 + pgvector would otherwise force a solo dev to build.

Neon (Option B) is the strongest decoupled alternative — better branching, cleaner pure-DB architecture, but pays a cost in additional vendors to wire up. Worth picking if Doug specifically values best-of-breed decoupling. Railway Postgres (Option C) is fine but less feature-rich and has less generous free tier. Self-hosting (Option D) is premature for v1 — the ops cost outweighs the control benefit at our scale.

**Caveat on Supabase Auth:** choosing Supabase for the DB does *not* commit us to Supabase Auth. We can still pick Clerk or WorkOS for auth in Q10 if we want stronger orgs/teams primitives later. Supabase Auth is the cheapest v1 path; Q10 will revisit the trade-off properly.

**Key reason it wins:** maximum batteries-included with multi-tenancy support out of the box, plus likely resolves Q8 (vector store) for free.

**Main risk we're accepting:** Supabase as a single-vendor concentration for DB + vector + (maybe) auth + storage. Mitigation: it's standard Postgres underneath; migration is painful but not catastrophic. We revisit if Supabase pricing, reliability, or product direction degrades.

## Decision

**Combined Option A — Supabase + pgvector + `RetrievalStore` abstraction.** Decided 2026-04-28.

- **Primary database:** Supabase (managed Postgres). Bundled features (auth, realtime, storage, pgvector) are all available; we'll evaluate which to actually adopt as separate decisions reach the queue.
- **Vector store:** pgvector running inside the same Supabase Postgres instance. HNSW index. Single store for relational and vector data.
- **Retrieval abstraction:** all vector retrieval flows through a `RetrievalStore` interface (typescript shape sketched below). No SQL with raw vector ops sprinkled through the codebase. This is the actual hedge against future migration.

```ts
interface RetrievalStore {
  upsert(items: VectorItem[]): Promise<void>;
  search(query: number[], filter?: Filter, k?: number): Promise<SearchResult[]>;
  hybridSearch?(text: string, query: number[], filter?: Filter, k?: number): Promise<SearchResult[]>;
  delete(ids: string[]): Promise<void>;
}
```

**Migration trigger documented now:** revisit dedicated vector DB (Qdrant, Pinecone, Turbopuffer, etc.) when **(a)** corpus exceeds ~10M vectors **AND (b)** p95 retrieval latency exceeds an SLO that we'll define in the observability work (Q19). Below that, no migration. Realistic scale curve puts the trigger in the v3 timeframe (~1,000 users), not v1 or v2.

**Hybrid search posture:** if/when hybrid search (vector + BM25 + filters in one query) becomes a v1 or v2 need, we implement it via tsvector + pgvector composition behind the `RetrievalStore` interface, in vendor-neutral terms — no Postgres-specific tricks leaking into call sites. This keeps hybrid search as the easiest piece to migrate later, not the hardest.

## Consequences

**Locks in:**
- Supabase as the primary application database vendor. All non-Inngest durable state lives here: users, tenants, transcripts, pipeline-run metadata, outputs, verdicts, retrieval corpus, native-target delivery records.
- pgvector as the v1 vector store. No separate vector DB vendor.
- `RetrievalStore` interface as the only path for retrieval calls. No exceptions.
- HNSW as the default index type. Tunable per-collection if needed.
- `tenant_id` (or equivalent) as a first-class column on every multi-tenant table — required for RLS in Q9.

**Creates / constrains follow-up decisions:**
- **Q9 (multi-tenancy model)** — Postgres RLS becomes the natural fit; Supabase has best-in-class RLS-with-auth tooling.
- **Q10 (auth provider)** — Supabase Auth becomes the cheapest v1 path because it integrates with RLS out of the box; alternatives (Clerk, WorkOS) are still viable but require manual RLS wiring.
- **Q11 (hosting)** — DB locality (Supabase region) influences hosting locality. Round-trip latency from Vercel/Fly/Railway/etc. to Supabase region matters.
- **Q19 (observability stack)** — must include p95 retrieval-latency monitoring per the migration trigger.
- **Q8 (vector store)** — *resolved by this decision.*

**Risks accepted:**
- Vendor concentration on Supabase for DB + (likely) vector + (maybe) auth + (maybe) storage. Mitigation: standard Postgres underneath; migration is painful but bounded. Revisit if pricing, reliability, or product direction degrades.
- pgvector's hybrid-search story is weaker than Qdrant/Weaviate (no native BM25). Acceptable in v1/v2 because hybrid search isn't a v1 requirement and tsvector-composition handles it adequately when needed.
- Supabase has historically lagged on extension support, so pgvectorscale (which would extend the pgvector runway to ~50M+ vectors) may not be available there. Mitigation: at the migration trigger, dedicated vector DBs are the comparison set anyway; pgvectorscale's absence doesn't change the calculus.
- Scale ceiling on pgvector + Supabase is real (~10M vectors). Mitigation: `RetrievalStore` abstraction makes migration bounded engineering work (~1 week), not a quarter.
