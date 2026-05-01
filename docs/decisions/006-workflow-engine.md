---
number: 006
title: Workflow / job engine
status: accepted
date: 2026-04-28
---

# 006 — Workflow / job engine

**Status:** accepted
**Date:** 2026-04-28

## Question

What engine handles durable execution of pipelines? Pipelines run for minutes to hours, call external APIs that fail, must retry, and — per [002](002-learning-model-and-feedback-architecture.md) — must pause to wait for human-in-the-loop verdicts before completing. The engine must own the durable state of every run; the Next.js app is the dashboard host, not the source of truth for pipeline state.

## Why this matters now

This is the engine that makes the system "durable, not best-effort" — one of the explicit non-negotiables in VISION.md. The choice locks in:

- **Run state ownership.** Pipeline runs and their step-by-step state live in the engine, not in our database. Migrations between engines are painful.
- **Pipeline definition style.** Each engine has its own DSL/SDK shape. Pipeline code is engine-coupled.
- **Operational surface.** Hosted vs. self-hosted is a major ergonomics decision; engines vary widely on this.
- **Human-in-the-loop primitive.** This is non-negotiable per 002. Engines that don't support pause-for-event are out.
- **Retry / observability story.** Each engine has its own retry semantics, dead-letter handling, and run-inspection UX. We rely on the engine's own UI for debugging in v1.

This is also one of the highest-risk decisions: we're betting on a vendor (or a piece of self-hosted infrastructure) that owns the most critical durable state in the system. A wrong choice doesn't just mean a refactor — it means rewriting every pipeline.

## Options

### Option A — Inngest

TS-first event-driven durable execution platform. Functions are triggered by events (`event.send(...)`) and execute as a series of `step.*` calls, each automatically durable and retried on failure. `step.waitForEvent(...)` and `step.sleep(...)` give first-class pause primitives. Next.js integration is a single route handler (`/api/inngest`). Hosted free tier is generous; self-host is available.

**Steel-manned reasoning:** The event-driven model is a *natural fit* for this architecture, not just a workable one. A transcript arriving is an event (`transcript.received`). A pipeline run is a function reacting to that event. A user verdict is an event (`verdict.captured`). The pipeline's pause-for-review step is `step.waitForEvent('verdict.captured', { match: 'data.runId' })`. That's the entire human-in-the-loop primitive expressed in one line. The step model gives automatic retries with backoff on every external call (LLM, calendar API, doc API), checkpointed durably so a crash mid-pipeline resumes from the last completed step. Next.js integration is genuinely two lines. The hosted free tier is generous enough to cover v1 + early v2 with zero ops burden. And the data model — events, runs, steps, all queryable via the Inngest dashboard — gives us best-in-class debugging UX for free, which directly addresses the "email-as-observability tops out fast" risk from 003. Vendor lock-in is mitigated by the self-host option, and pipeline code is portable enough that a future migration is bounded.

**Priors / assumptions this rests on:**
- Event-driven model maps cleanly to our transcript + verdict architecture — confidence: **high**
- `step.waitForEvent` is sufficient and idiomatic for human-in-the-loop pauses lasting hours/days — confidence: **high**
- Inngest's hosted free tier + reasonable paid tiers cover v1/v2 cost realistically — confidence: **medium-high**
- Next.js integration ergonomics are best-in-class among workflow engines — confidence: **medium-high**
- Inngest's debugging UX is good enough to be our primary v1 pipeline-observability surface — confidence: **medium-high**
- Self-host escape hatch is real and reduces vendor lock-in risk — confidence: **medium**

### Option B — Trigger.dev

TS-first task-based durable execution. v3+ introduced significantly improved primitives. Tasks are durable functions that can be invoked by events, schedules, or directly. Wait tokens (`wait.for(...)`) handle pause-for-event. Next.js integration via SDK + a worker process. Hosted + self-host (open-source).

**Steel-manned reasoning:** Trigger.dev's task-based model is more "job orchestration" than "event-driven function," which can be a better fit for thinking about pipelines as discrete units of work. v3 introduced waitTokens, retries, and machine-runtime improvements that make it competitive with Inngest on every dimension. The OSS license is friendlier than Inngest's, which matters if you ever want to hard-fork. The dev experience around inspecting runs, retrying tasks, and managing concurrency is excellent. The wait-for-event primitive is solid even if slightly less ergonomic than Inngest's.

**Priors / assumptions this rests on:**
- Task-based mental model fits pipelines as well as event-driven — confidence: **medium-high** (depends on developer preference)
- v3 wait tokens are mature enough for production human-in-the-loop — confidence: **medium-high**
- Trigger.dev's Next.js integration is comparable to Inngest's — confidence: **medium** (close but Inngest is slightly tighter)
- OSS license advantage matters in practice — confidence: **low-medium** (may not actually exercise it)
- Trigger.dev's hosted tier is cost-effective for v1 — confidence: **medium-high**

### Option C — Temporal (Cloud or self-host)

Industry-standard durable execution. Multi-language (TS, Go, Java, Python). Workflows are deterministic functions that can sleep, wait for signals, and run for arbitrary durations. Activities are the units of side-effect work, retried automatically. Self-hosting historically required Cassandra/Elasticsearch (modern lighter-weight options exist); Temporal Cloud is hosted but paid.

**Steel-manned reasoning:** Temporal is the *correct* answer for durable workflows at scale. It's battle-tested at every major tech company, the conceptual model (workflows + activities + signals) is rigorously defined, and the SDK is mature in every language. Workflow code looks like normal code with `await sleep()` and `await condition()` baked in — extremely natural to read. Signals are the canonical pause-for-human-input primitive: `await workflow.condition(() => verdictReceived)`. The TS SDK is solid. Temporal Cloud removes the operational burden if you can pay. And once you've built on Temporal, you're never going to outgrow it — Stripe, Snap, Coinbase all run on Temporal. For a system you intend to take to production for many users, betting on Temporal is the safest long-term call.

**Priors / assumptions this rests on:**
- Temporal's TS SDK is as ergonomic as Inngest/Trigger.dev for v1 development — confidence: **medium-low** (more boilerplate, more concepts to learn)
- Temporal Cloud cost is reasonable for v1 scale — confidence: **medium** (priciest of the candidates; minimum costs apply)
- Self-host is feasible for solo dev — confidence: **low** (real ops burden even with modern lighter-weight setups)
- The "scale-ready from day one" benefit pays off in v1/v2 timeframes — confidence: **low-medium** (genuinely overkill for one user)
- Solo dev productivity on Temporal matches Inngest/Trigger.dev — confidence: **low** (Temporal has more concepts and ceremony)

### Option D — DBOS

TS-native (also Python) durable execution backed by Postgres. Decorate normal TS functions with `@DBOS.workflow` or `@DBOS.transaction`; DBOS uses your Postgres database as the durability layer. No separate runtime to operate — your existing DB *is* the workflow engine. Pause-for-event via `setEvent`/`getEvent`/`recv`/`send` primitives.

**Steel-manned reasoning:** DBOS is architecturally elegant in a way none of the others are. Your database is already the source of truth for everything; making it the source of truth for workflow state too eliminates an entire category of consistency problems. There's no separate vendor to depend on, no separate UI to integrate with, no second source of truth to keep in sync. Decorating normal TS functions to make them durable is the lowest-friction developer experience imaginable — you write business logic, you sprinkle decorators, you have durability. For a solo dev, eliminating "another service to operate" is a massive simplification. And because state is in your Postgres, you can join workflow state with your business data directly, which is uniquely useful for an observability dashboard that wants to show "all runs for this transcript."

**Priors / assumptions this rests on:**
- DBOS maturity in 2026 is sufficient for production — confidence: **medium** (newer than the others; less battle-tested at scale)
- "Postgres is the engine" model handles long-running pauses (hours/days) without performance issues — confidence: **medium** (needs careful schema/index design, but Postgres handles this well)
- Pause-for-event primitives (`recv`/`send`) are as ergonomic as Inngest's `waitForEvent` — confidence: **medium**
- Eliminating a separate workflow service is a major solo-dev productivity win — confidence: **medium-high**
- DBOS's debugging/observability UX is sufficient without a separate dashboard — confidence: **medium-low** (Inngest/Trigger.dev have polished run inspectors; DBOS is rougher)
- Joining workflow state with business data in Postgres queries provides real value — confidence: **medium**

## Recommendation

**Option A — Inngest.**

The event-driven model is a *natural* fit for this architecture, not a forced one. A transcript arriving is an event; a verdict captured in the dashboard is an event; a pipeline run is a function reacting to those events. The `step.waitForEvent` primitive maps directly onto 002's pause-for-verdict requirement, in one line. The step model gives automatic retries on every external call (LLM, calendar, doc) with checkpointed durability so a crash mid-pipeline resumes cleanly. Next.js integration is a single route handler. The hosted free tier covers v1 + early v2 with zero ops burden. Inngest's run-inspector dashboard directly addresses the "email-as-observability tops out fast" risk we accepted in 003 — it's polished, free, and works out of the box.

Trigger.dev (Option B) is genuinely close — same league, same primitives, slightly different mental model. For most teams either choice works. Temporal (Option C) is the right answer at scale but is overkill and cost-heavy for v1. DBOS (Option D) is architecturally elegant but the maturity gap in 2026 is real, and the debugging UX isn't polished enough yet to be our v1 observability surface.

**Key reason it wins:** the event-driven mental model maps onto the architecture without translation, the human-in-the-loop primitive is one line of code, the Next.js integration is two lines, and the hosted free tier eliminates the ops burden a solo dev should not be paying. Every dimension lines up.

**Main risk we're accepting:** vendor dependency on Inngest's hosted service for the most critical durable state in the system. Mitigation: (a) Inngest is self-hostable as an escape hatch; (b) pipeline code is portable enough that a future migration to Temporal or DBOS is bounded engineering work, not a rewrite; (c) we revisit this decision if Inngest's hosted service proves unreliable, becomes prohibitively expensive at scale, or shows sustained roadmap divergence from our needs.

## Decision

**Option A — Inngest.** Decided 2026-04-28.

Inngest is the workflow engine. Pipelines are defined as Inngest functions invoked by events; each pipeline step is a `step.run` call that's checkpointed and auto-retried. Human-in-the-loop pauses use `step.waitForEvent` matched on run ID. The Inngest route handler lives in the Next.js app at `/api/inngest`. v1 starts on Inngest's hosted free tier; self-host is the documented escape hatch.

## Consequences

**Locks in:**
- Inngest owns durable run state. Our Postgres database does not duplicate run-step state — we read it from Inngest's API or rely on its dashboard for run inspection.
- Pipelines are written in Inngest's function-as-event-handler shape. Pipeline definition format (Q15) inherits this constraint — declarative configs must compile to or wrap Inngest functions.
- Verdict capture in the dashboard publishes an `inngest` event (e.g., `verdict.captured`) keyed by run ID, which the paused pipeline step matches and resumes on.
- Retry policy lives at the step level. External-call steps (LLM, calendar, doc) get Inngest's default retry semantics; can be tuned per step.
- Inngest's run-inspector dashboard is the v1 pipeline-debugging surface. Our own dashboard surfaces high-level run status to the author; deep step-by-step debugging happens in Inngest's UI.

**Creates / constrains follow-up decisions:**
- **Q11 (hosting)** — must support a long-running Next.js process able to receive Inngest's webhook callbacks. Vercel/Netlify/Fly/Railway all qualify.
- **Q15 (pipeline definition format)** — pipelines are TS code (Inngest functions); declarative config, if added later, compiles to Inngest functions.
- **Q19 (observability stack)** — Inngest covers run-level observability natively. App-level observability (Next.js routes, dashboard interactions) is a separate concern still open.

**Risks accepted:**
- Vendor dependency on Inngest's hosted service for v1's most critical durable state. Mitigation: Inngest is self-hostable; pipeline code is portable enough for a bounded migration to Temporal/DBOS if the vendor relationship deteriorates.
- Inngest is younger than Temporal as a category-defining vendor. If Inngest's product or company direction changes materially, we revisit. Trigger threshold: sustained reliability problems, prohibitive scale-cost, or public roadmap divergence from durable-execution-with-pause primitives.
