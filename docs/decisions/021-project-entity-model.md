---
number: 021
title: Project entity model and identification
status: accepted
date: 2026-04-28
---

# 021 — Project entity model and identification

**Status:** accepted
**Date:** 2026-04-28

## Question

Per Doug's clarification (2026-04-28), the marketing-app consumer expects transcripts to be **attached to specific projects**. Use case: a fence company has 7 concurrent projects; a transcript is recorded on-site about a customer interaction; the system needs to attach it to the right project. This requires:

1. **Project as a first-class entity** in voice-app (or a synced reference to a canonical project store)
2. **Project identification step** that runs early in the ingestion pipeline (before pipeline dispatch) so all downstream pipelines and outputs inherit the `projectId`
3. **Identification algorithm** — for v1, embedding-similarity fast-path with LLM fallback for ambiguous cases (per Doug's explicit override)
4. **Low-confidence handling** — what happens when the system can't reliably attach a transcript to a project
5. **Memory integration** — project-scoped recall for downstream pipelines

## Why this matters now

Without project identification, the marketing app can't function — its core value is project-attached customer interactions. It also affects:

- **[013] (transcript source adapter)** — `transcript.normalized` event likely needs a `projectId` field (or a follow-on enrichment step adds it)
- **[017] (pipeline dispatch)** — pipelines depend on `projectId` being present in their input
- **[018] (memory and retrieval)** — `memory_items.metadata.projectId` becomes a critical filter for recall (e.g., "show me prior transcripts on Project Y")
- **[020] (integration contracts)** — outputs carry `projectId`; consuming apps route to the correct project context

## Decision

### 1. Project source-of-truth: 4tradesCRM (or whichever consuming app owns project records)

Voice-app does **not** maintain canonical project data. Projects are owned by the consuming apps that the customer uses (4tradesCRM owns the project list for fence-company-style customers; the marketing app may have its own project view). Voice-app maintains a **synced project reference** per tenant.

Sync mechanism:
- Voice-app exposes `/api/internal/projects/sync` — consuming apps POST their full project list (or deltas) for a tenant on creation/update/deletion of projects on their side
- Voice-app stores the synced reference in a `projects` table (`id`, `tenant_id`, `external_id`, `external_source` (e.g., `4tradesCRM`), `name`, `description`, `metadata` JSONB, `embedding`, `synced_at`)
- The `embedding` is recomputed when `name` or `description` changes — used by the identification fast-path

For v1, 4tradesCRM owns project sync (writes to voice-app whenever a project is created/edited there). Marketing app may also sync if it owns projects independently. If both apps own overlapping projects, that's a configuration decision for the customer (which app's projects are canonical for that tenant).

### 2. Identification step runs pre-dispatch

The `transcripts` ingestion pipeline (per [013](013-transcript-source-adapter.md)) gains an identification step inserted between `transcript.normalized` and `transcript.ingested`:

```
[email.received]
    ↓ handleEmailReceived (parses email, resolves tenant)
[transcript.normalized]
    ↓ identifyProject (THIS DECISION; embedding fast-path + LLM fallback)
[transcript.identified]   ← carries projectId (or null) plus identification metadata
    ↓ dedupeAndPersistTranscript
[transcript.ingested]
    ↓ dispatcher (per [017])
[pipeline.${id}.requested]
```

Pipelines and dispatch logic always see a transcript with `projectId` already resolved (or explicitly `null`).

### 3. Identification algorithm: embedding fast-path + LLM fallback (v1)

Per Doug's explicit call (2026-04-28), the v1 implementation is the production-ready hybrid, not LLM-only:

```ts
async function identifyProject(transcript, tenantId) {
  // Fast path: embedding similarity against tenant's projects
  const queryEmbedding = await embed(transcript.text);
  const candidates = await projectStore.search({
    query: queryEmbedding,
    tenantId,
    k: 3,
  });

  const top = candidates[0];

  // Confident match: top score above threshold AND well above runner-up
  if (top && top.score > 0.78 && (top.score - (candidates[1]?.score ?? 0) > 0.10)) {
    return {
      projectId: top.id,
      method: 'embedding',
      confidence: top.score,
      considered: candidates.map(c => ({ id: c.id, score: c.score })),
    };
  }

  // Ambiguous or no clear match: LLM fallback with top-N candidates in context
  const llmResult = await llm.generate({
    modelTier: 'cheap-and-fast', // routing/classification doesn't need the high-quality tier
    schema: z.object({
      projectId: z.string().nullable(),
      reasoning: z.string(),
      confidence: z.enum(['high', 'medium', 'low']),
    }),
    prompt: buildProjectIdentificationPrompt(transcript, candidates, tenantId),
  });

  return {
    projectId: llmResult.confidence === 'low' ? null : llmResult.projectId,
    method: 'llm',
    confidence: llmResult.confidence,
    reasoning: llmResult.reasoning,
    considered: candidates.map(c => ({ id: c.id, score: c.score })),
  };
}
```

Thresholds (`0.78` for top score, `0.10` for runner-up gap, "low" LLM confidence) are tunable from telemetry. Tracked in `project_identification_runs` audit table for analysis.

### 4. Low-confidence handling

When `projectId` is `null` after identification (LLM returned "low confidence" or no projects exist for the tenant):

- The transcript still ingests — `projectId: null` is a valid state
- `transcript.ingested` event fires; dispatch continues normally
- The dispatcher and pipelines handle the `null` case explicitly:
  - Pipelines that *require* a project (e.g., `marketing.attach-interaction-to-project`) emit a structured "needs project assignment" output and pause for review (per [003](003-primary-user-surface.md)); consuming apps can render this as "we received a voice memo but couldn't identify the project — please assign manually"
  - Pipelines that don't require a project (e.g., a generic CRM follow-up draft) proceed normally

The "needs project assignment" UX lives in the consuming app per [003](003-primary-user-surface.md). Voice-app surfaces the unassigned state via the standard `pipeline.output.proposed` webhook with a special output kind (e.g., `system.needs-project-assignment`).

### 5. Memory integration

`memory_items.metadata.projectId` (per [018](018-memory-and-retrieval-strategy.md)) is populated for transcripts, verdicts, outputs, and pipeline-run summaries scoped to a project. The `recallMemory` tool gains a `projectId` filter — agents and pipelines researching context for "Project Y" can scope retrieval to project-matching items.

This is a small extension of 018's interface, already supported by the existing `metadata` JSONB filter.

## Consequences

**Locks in:**
- `projects` table in voice-app: synced reference to consuming-app project records, with `external_id` + `external_source` discriminator. Per-project embeddings stored for fast-path identification.
- `/api/internal/projects/sync` endpoint that consuming apps call to maintain the synced project list per tenant.
- An `identifyProject` Inngest function inserted between `transcript.normalized` and `dedupeAndPersistTranscript`.
- Embedding fast-path with thresholds (0.78 top score, 0.10 runner-up gap) and LLM fallback as the v1 algorithm.
- `project_identification_runs` audit table: `transcript_id`, `tenant_id`, `chosen_project_id` (nullable), `method` (`embedding`|`llm`), `confidence`, `considered` (JSONB), `reasoning?`, `duration_ms`, `cost_usd?`.
- Pipelines and outputs carry `projectId` (or `null`) per [015](015-pipeline-definition-format.md) amendment.
- `recallMemory` tool filter extended with `projectId`.

**Creates / constrains follow-up decisions:**
- **Q21 (observability)** — identification accuracy is a key metric (sampled human-review against system decisions); thresholds tuned from this data.
- **Q23 (compliance)** — synced project data is sensitive; retention follows the same policy as other tenant data.
- **4tradesCRM-side work added (tracked separately)**: implement project-sync endpoint sender — push project list to voice-app on create/update/delete.
- **Marketing app-side work added**: same — implement project-sync sender if marketing app owns project records independently.

**Future evolution path documented:**
- v2: tune thresholds based on accuracy telemetry; experiment with re-ranking signals (recency of last interaction with the project, time-of-day patterns, etc.)
- v3: support cross-project transcripts (a single voice memo discusses two projects) — the identification step's output becomes `projectIds: string[]` instead of `projectId: string`. Outputs fan out per project.
- v3+: customer-facing "project hint" in the inbound email subject line or in the Plaud device's per-recording tag (when Plaud API arrives) — bypasses identification entirely when present.

**Risks accepted:**
- Embedding-similarity fast-path may miss semantic shifts (e.g., a project description that's stale relative to current work). Mitigation: re-embed on every project update; LLM fallback catches the rest.
- LLM fallback adds latency and cost on ambiguous transcripts. Mitigation: cheap model tier; only fires when fast-path doesn't decide; cost tracked per identification run.
- `null` `projectId` requires consuming-app UX for manual assignment. Bounded by consuming-app scope (CRM and marketing app each implement once).
- Project-sync from consuming apps adds operational coupling — voice-app's project list can drift if syncs fail. Mitigation: monitoring on sync freshness (alert if a tenant's project sync is >24h stale); on-demand resync endpoint.