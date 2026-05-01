---
number: 017
title: Pipeline dispatch (transcript → pipeline routing)
status: accepted
date: 2026-04-28
---

# 017 — Pipeline dispatch (transcript → pipeline routing)

**Status:** accepted
**Date:** 2026-04-28

## Question

When a `transcript.ingested` event fires (per [013](013-transcript-source-adapter.md)), how does it get to the right pipeline? V1 has only one pipeline per [001](001-target-user-and-v1-scope.md), so this question is mostly about v2: when multiple pipelines exist, how do we decide which receives each transcript?

This was originally framed as "keyword routing strategy" in the queue. The framing is wrong — keyword matching is one possible *implementation*, not the question itself. The question is the *architecture* (where routing logic lives), with the implementation algorithm decided later when v2 pipelines actually exist.

## Why this matters now

Even though v1 has trivial routing (single pipeline = every transcript goes to it), the architectural choice now determines whether v2's "second pipeline" is a clean addition or a refactor. Picking wrong means restructuring how the existing v1 pipeline listens for events when the second pipeline arrives.

The decision also touches:
- **[015] (pipeline definition)** — pipelines declare triggers in `definePipeline({...})`. The shape of the trigger declaration is constrained by the routing model.
- **[019] (memory / retrieval)** — if routing uses semantic similarity (embeddings or LLM), the retrieval store overlap matters.
- **Q21 (observability)** — routing decisions need to be observable; "why did this transcript go to pipeline X?" is a real debugging question.

## Options

### Option A — Filter-based (Inngest-native event matching)

Each pipeline declares Inngest event filters in its `definePipeline({...})` triggers. Multiple pipelines can match the same event. Inngest fans out the event to every matching pipeline.

```ts
export default definePipeline({
  triggers: [{
    event: 'transcript.ingested',
    match: 'data.transcript.text',
    if: 'event.data.transcript.text.match(/follow up|reminder|next.*meeting/i)',
  }],
  // ...
});
```

**Steel-manned reasoning:** Uses Inngest's native filtering — no extra layer to build. Filters live with the pipeline that owns them, which is a defensible co-location. Filtering happens before pipeline execution begins, so non-matching transcripts cost nothing.

**Priors:**
- Inngest filter expressions can express the routing logic we'll need — confidence: **medium-low** (Inngest's filter language is limited; complex matching becomes ugly fast)
- Per-pipeline trigger declarations age well as pipelines accumulate — confidence: **low** (drift; overlaps; "which pipeline gets this?" becomes hard to debug across files)
- Routing logic doesn't benefit from being centralized — confidence: **low** (centralized routing is genuinely easier to reason about and observe)

### Option B — Dispatcher-based (centralized router → pipeline-specific events)

One Inngest function (`dispatch-transcript`) listens to `transcript.ingested`, applies routing logic, and emits a pipeline-specific event (`pipeline.follow-up-with-prep.requested`, `pipeline.daily-briefing.requested`, etc.). Each pipeline listens to its own pipeline-specific event.

```ts
inngest.createFunction(
  { id: 'dispatch-transcript' },
  { event: 'transcript.ingested' },
  async ({ event, step }) => {
    const transcript = event.data.transcript;
    const pipelineId = await step.run('classify', () => routeToPipeline(transcript));
    await step.sendEvent('dispatch', {
      name: `pipeline.${pipelineId}.requested`,
      data: { transcript },
    });
  }
);
```

In v1, `routeToPipeline` is a one-line function returning the single pipeline's ID. In v2, it grows real classification logic — could be rule-based, embedding-similarity-based, or LLM-based, decided when pipelines exist to compare.

**Steel-manned reasoning:** Routing logic lives in one place. Easy to observe ("here's the dispatcher's classification log"). Easy to evolve (v2 dispatcher swaps classification algorithm without touching pipelines). Pipelines are decoupled from routing — they just listen to their own event. The dispatcher is itself an Inngest function, so its decisions are durable, retried, and visible in the run inspector. Adding a pipeline = (a) write the pipeline, (b) add a classification rule to the dispatcher. Two clean changes.

**Priors:**
- Centralized dispatcher is meaningfully cleaner than scattered filters at scale — confidence: **high**
- Thin dispatcher in v1 is bounded cost (~20 lines) — confidence: **high**
- Pipeline-specific events make Inngest's run inspector more useful for debugging — confidence: **medium-high**
- v2 dispatcher evolution (rule → LLM) doesn't require refactoring pipelines — confidence: **high**
- Inngest's native event-fanout doesn't give us anything we'd lose — confidence: **medium-high**

### Option C — LLM classifier in dispatcher (eager v2 implementation in v1)

Same shape as B, but the dispatcher's `routeToPipeline` is an LLM call that picks the pipeline ID based on transcript content.

**Steel-manned reasoning:** Maximum flexibility from day one. Adding a pipeline = write its `defineAgent`-style description; the LLM classifier picks it up. No code change to the dispatcher per pipeline.

**Priors:**
- LLM classification is reliable enough to ship in v2 — confidence: **medium** (reasonable with current models; adds latency and cost per transcript)
- Per-transcript LLM call is acceptable cost — confidence: **medium-low** (every transcript = one extra LLM call before routing; adds up at scale)
- LLM-based routing is needed in v1 — confidence: **very low** (v1 has one pipeline; LLM classification is over-engineering)
- LLM-based routing is the right v2 algorithm — confidence: **medium** (probably yes, but should be decided when v2 pipelines exist with real evidence)

### Option D — Embedding similarity in dispatcher

Same shape as B, but `routeToPipeline` embeds the transcript and compares to pre-computed embeddings of each pipeline's trigger description; picks the closest match.

**Steel-manned reasoning:** Cheaper than LLM classification (one embedding call per transcript instead of one chat completion). Reuses pgvector infrastructure from [007](007-primary-database-and-vector-store.md). Semantic matching is more flexible than keyword rules.

**Priors:**
- Embedding similarity is reliable enough for routing — confidence: **medium** (works for clearly-different pipelines; struggles with semantically overlapping ones)
- Per-transcript embedding cost is negligible — confidence: **high** (cents per thousand)
- Embedding-based routing works without an explicit "no match" path — confidence: **medium-low** (always picks *something*; need a similarity threshold + fallback)
- Right v2 algorithm — confidence: **medium** (good middle ground; defer decision until v2 pipelines exist)

## Recommendation

**Option B — Dispatcher-based architecture, with v1 implementation as a one-line trivial classifier.**

Architecture choice now (B), classification algorithm choice deferred to v2 when there's evidence about how pipelines actually differ. The thin v1 dispatcher costs ~20 lines — bounded — and avoids the v2 refactor that A would require. v2 evolution path: keep B's structure, swap `routeToPipeline`'s implementation from `() => 'follow-up-with-prep'` to whatever rule-based / embedding-based / LLM-based classifier the v2 evidence supports.

A is rejected because filter-based routing scatters logic across pipelines and ages poorly. C and D are premature implementations of v2 algorithms — pick the algorithm with v2 evidence, not v1 speculation.

**v1 deliverables:**
1. **`pipelines/dispatcher.ts`** — Inngest function listening to `transcript.ingested`. Calls `routeToPipeline(transcript)`, emits `pipeline.${pipelineId}.requested` event. Audit-logs the routing decision.
2. **`lib/pipelines/router.ts`** — exports `routeToPipeline(transcript): Promise<string>`. v1: returns the single pipeline's ID. v2: grows classification logic.
3. **Pipelines listen to their pipeline-specific event** (e.g., `pipeline.follow-up-with-prep.requested`) instead of `transcript.ingested`. The trigger declaration in `definePipeline({...})` references the pipeline-specific event.
4. **Routing audit log** — every dispatch decision records `transcript_id`, `tenant_id`, `chosen_pipeline_id`, `reason` (a short string explaining the choice — "only-pipeline" in v1; "rule:follow-up-keyword" or "llm-classification" in v2).

**v2 algorithm decision deferred** — when 3+ pipelines exist with potentially overlapping triggers, decide between rule-based, embedding-similarity, LLM-classifier, or hybrid based on real pipeline characteristics. The architecture supports any of them as a swap inside `routeToPipeline`.

**Key reason it wins:** correct architecture from day one with bounded v1 cost; v2 evolution doesn't refactor pipelines; routing decisions are observable and auditable.

**Main risk we're accepting:** dispatcher adds one Inngest hop per transcript even in v1 (where it's trivial). Mitigation: hop is fast (~milliseconds), durable, and the v2 win is significant.

## Decision

**Option B — Dispatcher-based architecture, with v1 implementation as a one-line trivial classifier.** Decided 2026-04-28.

V1 ships a thin dispatcher (`pipelines/dispatcher.ts`) that listens to `transcript.ingested`, calls `routeToPipeline(transcript)`, and emits `pipeline.${pipelineId}.requested`. v1 `routeToPipeline` returns the single pipeline's ID. Pipelines listen to their pipeline-specific event, not `transcript.ingested` directly. Every dispatch decision is audit-logged with a structured `reason`.

### Expected evolution path

The architecture is chosen specifically to enable an LLM-driven endstate without restructuring pipelines. **The expected trajectory ends with LLM-based dispatch — likely as the dominant classifier by v3, with deterministic fast-paths preserved as cost optimization for clear cases.** Documenting the trajectory so future-us doesn't have to re-derive it:

| Stage | Pipelines | Classifier | Notes |
|---|---|---|---|
| 1 (v1) | 1 | trivial constant | `() => 'follow-up-with-prep'` |
| 2 (v1.x – v2) | 3–10 | rules + embedding similarity fast-path | regex / keyword rules where signal is clear; pgvector similarity for ambiguous; "unmatched" fallback |
| 3 (v2 – v3) | 10–30 | LLM classifier as fallback; rules/embeddings stay as fast-path | LLM only sees ambiguous cases; cost stays bounded; structured `{ pipelineId, confidence, reasoning }` output |
| 4 (v3+) | many | multi-pipeline fan-out | dispatcher returns `DispatchPlan` (array of invocations with optional dependencies); VISION's "single-use transcripts" constraint relaxes when transcripts contain multiple intents |
| 5 (v4+) | many | **agent-as-dispatcher** | the dispatcher itself is an agent (per [016](016-agent-and-tool-architecture.md)) with tools to inspect prior runs, search the pipeline registry, preview pipelines, and produce a reasoned `DispatchPlan`. Symmetric with 016: pipelines invoke agents; the dispatcher is an agent invoking pipelines. |

**Why LLM is the expected endstate:** rule-based and embedding classifiers don't scale to 20+ pipelines with semantically overlapping triggers. LLMs handle ambiguity, multi-intent transcripts, and dependency reasoning natively. The hybrid (LLM-on-fallback, deterministic-on-fast-path) is the practical productionized shape because it bounds cost — most transcripts route via cheap deterministic paths; the LLM only intervenes when classification is genuinely hard.

**What stays constant across all stages:**
- Pipelines listen to `pipeline.${id}.requested` events. Pipeline contracts never change.
- `routeToPipeline` (or `routeToPipelines` after Stage 4) is the only thing that evolves.
- Audit log records every dispatch decision with structured `reason`. The reason field becomes richer over time: `"only-pipeline"` → `"rule:keyword-match:follow-up"` → `"embedding-similarity:0.82"` → `"llm-classifier: this transcript mentions both a meeting reminder and a revenue request"`.

**What changes:**
- Classification logic (rules → embeddings → LLM → agent).
- Whether one transcript triggers one pipeline or many (Stage 4+).
- Whether the dispatcher is a function or itself an agent (Stage 5).

## Consequences

**Locks in:**
- `pipelines/dispatcher.ts` — Inngest function listening to `transcript.ingested`, calling `routeToPipeline`, emitting `pipeline.${pipelineId}.requested`.
- `lib/pipelines/router.ts` — exports `routeToPipeline(transcript): Promise<string>` (v1 signature; will widen to `Promise<DispatchPlan>` at Stage 4).
- Pipelines declare triggers as `pipeline.${id}.requested` events in `definePipeline({...})`, never `transcript.ingested` directly.
- `routing_audit` table — `transcript_id`, `tenant_id`, `chosen_pipeline_id`, `reason` (structured string), `dispatcher_version` (so we can correlate routing changes with system version).

**Creates / constrains follow-up decisions:**
- **Q19 (memory / retrieval)** — when Stage 3 LLM classifier arrives, it consumes the retrieval store for context-aware classification. Pipeline descriptions become embeddable artifacts.
- **Q21 (observability)** — routing decisions surface in the dashboard's pipeline-debug view alongside agent-run and tool-call traces.
- **Future v3+ work — multi-pipeline fan-out & agent-as-dispatcher.** Tracked in deferred list. Triggers: 10+ pipelines with overlapping triggers (Stage 3); transcripts with genuine multi-intent (Stage 4); LLM-classifier alone struggles with disambiguation (Stage 5).

**Risks accepted:**
- Dispatcher adds one Inngest hop per transcript even in v1. Mitigation: hop is fast (~ms), durable, and the v3+ win is significant.
- Trivial v1 classifier feels over-engineered for one pipeline. Mitigation: ~20 lines; the v2 evolution doesn't refactor pipelines, which is the whole point.
- LLM-based classification (Stage 3+) adds latency and cost per ambiguous transcript. Mitigation: fast-path handles 80–90% of transcripts; LLM only sees the hard cases; cost bounded by per-classification token cap.
- "Unmatched" routing surface (when no pipeline matches confidently) needs a UX home — likely a dashboard list of "we received this but didn't know what to do with it" with manual pipeline-assign affordance. Defer detailed UX to when Stage 2 lands.
