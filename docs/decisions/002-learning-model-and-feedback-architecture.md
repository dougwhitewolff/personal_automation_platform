---
number: 002
title: Learning model and feedback architecture
status: accepted
date: 2026-04-28
---

# 002 — Learning model and feedback architecture

**Status:** accepted
**Date:** 2026-04-28

## Question

Does the v1 system learn from user feedback (accepts, rejects, edits, deltas), and if so, by what mechanism? Specifically: is feedback captured at all, and if it is, is it consumed at runtime via in-context retrieval or via continuous fine-tuning of an underlying model?

## Why this matters now

This is a foundational architectural decision that ripples beyond intelligence into the data model, workflow engine, surface, and provider choice:

- **Data model.** If verdicts (accept/reject/edit) feed back into the system, pipeline runs are no longer fire-and-forget. They have post-completion state — a "human-in-the-loop" lifecycle that must be modeled as first-class. Retrofitting this onto a one-shot run model is painful.
- **Workflow engine (Q5).** Pause-for-human-input becomes a first-class need, not an afterthought. Some engines support this gracefully (Temporal, Inngest with manual events), some don't.
- **Pipeline definition (Q14).** Pipelines need explicit "human review" steps as a primitive.
- **Memory / retrieval (Q16).** Past verdicts join past transcripts as part of the retrieval corpus.
- **Surface (Q3).** The dashboard becomes load-bearing rather than optional polish if structured feedback capture is required.
- **LLM provider (Q13).** Fine-tuning constrains provider choice; in-context learning does not.

Decided up front, all of these get framed correctly. Decided later, several require a refactor.

## Options

### Option A — No learning loop in v1

Run pipelines, log outputs, treat feedback as a future feature. Pipeline runs are fire-and-forget. The system is autonomous in the sense that it doesn't model user verdicts at all.

**Steel-manned reasoning:** v1 already has a lot to prove — durable execution, retrieval, external integrations, tenant scoping. A learning loop is over-scoping for v1, especially when the base model (Claude/Anthropic frontier) is already quite good out of the box. Many real production assistants ship without learning loops and rely entirely on prompt engineering and base-model quality. Adding a learning loop is a clean *additive* change later if the base-model performance proves insufficient. Designing for learning when you don't yet know whether you need it is the textbook YAGNI mistake.

**Priors / assumptions this rests on:**
- Learning loops can be retrofitted cleanly onto an autonomous-pipeline data model — confidence: **low** (data-model retrofits to add post-completion state are notoriously painful)
- Base-model quality is sufficient for v1 trust-building without learning — confidence: **medium** (depends heavily on which pipeline)
- The author tolerates not seeing visible improvement-from-feedback in v1 — confidence: **medium-low** (the trust-building motivation in Q1 explicitly relies on the system getting better over time)

### Option B — Audit-only logging

Capture verdicts (accepts, rejects, edits, deltas) in structured form. Don't use them at runtime. The data is there for later — manual analysis, future fine-tuning, future in-context use — but v1 runtime behavior is unchanged.

**Steel-manned reasoning:** Captures the structural commitment without taking on runtime complexity. The data model is right from day one (verdicts are first-class), but the pipeline-run-time behavior is the same as Option A — simpler to debug, simpler to reason about. When the time comes to actually use the data, it's already collected, and the choice between in-context learning and fine-tuning can be made empirically with real corpus in hand.

**Priors / assumptions this rests on:**
- Captured-but-unused data is meaningfully cheaper than captured-and-used — confidence: **medium-high** (true; runtime retrieval adds complexity)
- Audit-only is meaningfully different from full feedback loop in *user* experience — confidence: **medium-high** (the user can't see "the system learning," so the trust-building benefit of a feedback loop is one-sided)
- The data captured under audit-only matches what runtime use would need — confidence: **high** (the schema is the same)

### Option C — In-context learning + structured data collection (deferred fine-tuning)

Capture structured feedback (verdicts, deltas) as first-class data. Use it at runtime via retrieval: at pipeline-run time, look up similar past transcripts/runs and their verdicts, include them in the LLM prompt ("last time you got a memo like this, the user removed section X"). Fine-tuning is enabled by the same data model when corpus volume and an evaluation harness justify it — expected v2.

**Steel-manned reasoning:** This is the version that delivers user-visible learning *immediately* without paying the full cost of fine-tuning. Frontier LLMs are extraordinarily good at in-context learning — with a handful of well-chosen prior examples in the prompt, they adapt behavior in ways that meaningfully match user preferences. The data model is identical to what fine-tuning needs, so v2 fine-tuning is a clean addition rather than a rebuild. It also defers the LLM-provider decision — Claude can stay primary in v1 because in-context learning works on any model. And it's honest about the cold-start problem: with one user generating 5–30 transcripts/week, fine-tuning is data-starved for months, while in-context learning works from the second feedback event onward.

**Priors / assumptions this rests on:**
- In-context retrieval delivers user-visible learning behavior at v1 data scale — confidence: **medium-high**
- Frontier model in-context performance ≥ a fine-tune of a smaller model at <1000 examples — confidence: **medium-high**
- The data model for verdicts + retrieval is the same data model fine-tuning would use — confidence: **high**
- Eval harness can wait until corpus is stable without losing — confidence: **medium-high**

### Option D — Continuous fine-tuning from v1

Capture data, build evaluation harness, run periodic fine-tunes from day one. Q13 (LLM provider) is decided immediately toward a fine-tunable model (OpenAI gpt-4o-mini, Bedrock-hosted Claude, or a local/open model). Eval infrastructure, model versioning, A/B comparison, and rollback are v1 scope.

**Steel-manned reasoning:** Fine-tuning produces qualitatively different behavior than in-context retrieval — faster at inference (no retrieval overhead in the prompt), more consistent (preferences encoded in weights, not reconstructed each call), and able to internalize patterns retrieval can't easily express (writing voice, multi-step preference patterns, structural format choices). Starting v1 with continuous fine-tuning means the system is dramatically better-personalized from week 8 onward, when the retrieval-only system is still essentially the base model with examples in the prompt. The ambition signals seriousness about the product.

**Priors / assumptions this rests on:**
- 50–100 examples is enough to fine-tune meaningfully on style/voice — confidence: **medium** (true on smaller models, less true on frontier reasoning models)
- Eval harness is buildable in v1 budget — confidence: **low** (evals for personal-assistant quality where "good" is partly mood-dependent are genuinely hard)
- Provider lock-in cost is acceptable — confidence: **medium** (Claude is currently strongest on reasoning; fine-tuning forces a meaningful tradeoff)
- Catastrophic forgetting / overfitting risk is manageable on small data — confidence: **low-medium** (real risk, especially with weekly retrains)
- MLOps overhead (versioning, A/B, rollback) is bounded — confidence: **low** (typically underestimated 3–5×)

## Recommendation

**Option C — in-context learning + structured data collection, with fine-tuning deferred to v2.**

This is the version that gets the architectural commitment right without paying the v1 cost of full fine-tuning infrastructure. The data model — verdicts as first-class, runs with post-completion state — is identical to what fine-tuning will eventually need, so v2 fine-tuning becomes an addition rather than a rebuild. In-context retrieval delivers user-visible learning behavior immediately, which is what makes the trust-building loop two-sided. And it doesn't force the LLM-provider decision before there's evidence to make it — Claude stays primary in v1.

**Key reason it wins:** the structural commitment is the load-bearing decision. The runtime mechanism (in-context vs. fine-tuning) is downstream of the data model and can be upgraded later without rebuilding. Option C makes the structural commitment now and picks the cheapest mechanism that produces visible learning.

**Main risk accepted:** in-context retrieval may not produce learning that *feels* visible to the author without intentional UX (e.g., "based on past similar runs" indicators in the dashboard). Mitigation: the surface decision must include explicit visibility into retrieved context.

## Decision

**Option C — in-context learning + structured data collection (deferred fine-tuning).** Decided 2026-04-28.

V1 captures structured feedback for every pipeline run: accepts, rejects, edits, and edit deltas. Verdicts are first-class entities in the data model. At pipeline-run time, the LLM prompt includes retrieved relevant past runs and their verdicts ("here's how you handled similar transcripts before"). The dashboard surfaces what was retrieved so the author can see the system's reasoning. Fine-tuning is explicitly deferred to v2, gated on (a) corpus volume threshold, (b) evaluation harness in place, (c) demonstrated regression in in-context-only baseline that fine-tuning would address.

Provider choice (Q13) is NOT pre-determined by this decision. Claude/Anthropic remains the default candidate.

## Consequences

**Locks in:**
- Verdicts (accept / reject / edit / delta) are first-class entities in the data model from v1.
- Pipeline runs have post-completion state — they're not fire-and-forget. The run lifecycle includes a human-in-the-loop phase.
- The dashboard becomes the canonical edit/review surface (because feedback capture must be structured; email/native-target-only loses delta signal).
- Memory/retrieval at pipeline-run time includes past runs + their verdicts, not just past transcripts.

**Creates / constrains follow-up decisions:**
- **Q3 (primary user surface)** is now constrained: a dashboard is mandatory. The remaining surface question is delivery flow (review-then-deliver vs. deliver-then-review), notification mechanism, and the role of native targets.
- **Q5 (workflow engine)** must support pause-for-human-input as a first-class concept. This narrows the field — engines that don't model long-pause durable execution well are out.
- **Q14 (pipeline definition format)** must allow "human review" steps as a primitive operation in pipeline definitions.
- **Q16 (memory / retrieval strategy)** is partially defined: verdicts join transcripts in the retrieval corpus.
- **Q13 (LLM provider)** is *not* constrained by this decision. Fine-tuning is not v1, so provider choice can be made on its own merits.
- **Eval harness** is added to the planning queue as a v1.x milestone (post-launch, when corpus is stable enough to evaluate against).
- **Fine-tuning** is added to the planning queue as a v2 decision, gated on the conditions named above.

**Risks accepted:**
- In-context retrieval may not produce visible "learning" without intentional UX. Mitigation: dashboard surfaces retrieved-context indicators so the author sees why the system did what it did.
- Verdict capture without immediate fine-tuning means the data model carries weight not fully exercised in v1. This is the whole point — structural readiness is the win. Acceptable.
- Author may want fine-tuning sooner than corpus volume justifies. Mitigation: revisit the corpus + eval question at 3 months and 6 months in production.
