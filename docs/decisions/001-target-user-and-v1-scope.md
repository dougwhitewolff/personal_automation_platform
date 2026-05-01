---
number: 001
title: Target user and v1 scope
status: accepted
date: 2026-04-28
---

# 001 — Target user and v1 scope

**Status:** accepted
**Date:** 2026-04-28

## Question

Who is v1 for, and what does "done" mean for v1? Specifically: how many users does v1 serve in practice, and is the v1 finish line measured in pipeline depth (one hard pipeline working end-to-end) or pipeline breadth (several shallow pipelines)?

## Why this matters now

This is the design-pressure question. Every later decision — workflow engine, data model, auth, hosting, observability — gets sized against the answer. If v1 is "author only with one deep pipeline," we can take shortcuts on onboarding UX, billing, and surface ergonomics, and pour effort into the workflow engine, retrieval, and pipeline definition format. If v1 is "author plus a real second user," multi-tenancy stops being a checkbox and becomes a daily-tested constraint, which raises the bar on auth and data isolation. If v1 is "breadth over depth," routing and pipeline-onboarding ergonomics dominate the architecture; if it's "depth over breadth," durable execution and context retrieval dominate.

The "done" definition also locks in the dogfooding loop. A v1 that the author can't use daily produces no signal. A v1 that other people depend on early creates real reliability requirements before the engine is ready for them. We need to choose where the pressure points are.

## Options

### Option A — Author-only, single deep pipeline (the north-star case)

Build for one user (the author). "Done" = the north-star "follow-up with prep" pipeline (or one similarly complex pipeline) works end-to-end, durably, on real Plaud transcripts arriving via email. Multi-tenancy is structurally present (tenant boundaries in the data model, auth scaffolding) but only one tenant exists in production. Routing is trivial because there's only one pipeline.

**Steel-manned reasoning:** The architecture only earns its keep when it makes the hard case tractable. The north-star use case in VISION.md is intentionally complex — it ingests, classifies, schedules a future event, fans out to retrieval across multiple sources, calls external APIs that can fail, drafts text, and surfaces output before a deadline. A single pipeline that fully exercises that flow pressure-tests every architectural choice that matters: durable execution, retry semantics, LLM context plumbing, retrieval, external API integration, and tenant boundaries. Three shallow pipelines do not produce that pressure — they produce three barely-integrated CRUD apps with a transcript on top. Worse, breadth-first tends to lock in the wrong primitives because the breadth comes from cosmetic differences, not architectural ones. The author also builds the most conviction by dogfooding the genuinely hard case daily; a working follow-up-with-prep pipeline is something they will actually rely on, which keeps the feedback loop tight.

**Priors / assumptions this rests on:**
- The north-star pipeline exercises substantially more of the architecture than 3–4 shallow pipelines combined — confidence: **high**
- The author will use a single deep pipeline often enough to generate useful daily signal — confidence: **medium** (depends on how often a "follow-up with prep" voice memo actually happens; could be weekly, not daily)
- One deep pipeline takes comparable calendar time to several shallow ones once you account for switching costs — confidence: **medium**
- Multi-tenancy concerns can be validated structurally (schema review, code review) without a second real user — confidence: **medium-low** (multi-tenancy bugs often only surface with two real users)

### Option B — Author-only, pipeline breadth (3–4 simpler pipelines)

Build for one user. "Done" = three to four simpler pipelines work end-to-end (e.g., calendar reminder, task capture, note search, follow-up draft). Routing is the central problem to solve. Each pipeline is shallow on its own but the surface area exercises the routing layer, the pipeline-onboarding ergonomics, and the user-facing breadth that makes the system feel like an assistant rather than a single automation.

**Steel-manned reasoning:** The platform is the product. A platform with one pipeline isn't a platform — it's a workflow with too much scaffolding. The questions that will dominate v2, v3, and every future user are: how does a new pipeline get added, how does routing decide which one to fire, how do pipelines share or isolate state. Ducking those questions in v1 means designing the wrong primitives in isolation and discovering it later when retrofitting is expensive. Breadth-first also produces dramatically more daily utility for the author — a system that handles many small voice memos gets used many times a day; a system that handles one complex memo gets used once a week. More usage means more bug reports, more rough edges surfaced, and a system that genuinely earns trust. And the cost of "shallow" pipelines is overstated: even a calendar-reminder pipeline still needs durable execution, retry, and context-aware drafting, so the architecture is still being exercised.

**Priors / assumptions this rests on:**
- Daily utility comes more from frequency of small wins than from one big win — confidence: **medium** (genuinely depends on the author's habits)
- Pipeline-onboarding ergonomics are an architectural concern best surfaced by ≥3 pipelines — confidence: **high**
- 3–4 shallow pipelines fit in similar calendar time as one deep one — confidence: **medium-low** (probably false; depth typically beats breadth on calendar)
- Shallow pipelines still exercise enough of the architecture to validate it — confidence: **medium**

### Option C — Author + 1–2 trusted beta users, single pipeline

Build for the author plus one or two people the author already knows (spouse, close colleague, friend) using the system from day one. "Done" = one pipeline works for all users, auth is wired, manual onboarding works (no self-serve). Multi-tenancy stops being theoretical and becomes a continuously-tested constraint.

**Steel-manned reasoning:** "Productizable from day one" is one of the stated non-negotiables, and it is meaningless without a second real tenant exercising the boundaries. Adding one trusted beta user instantly converts multi-tenancy from a checklist item into a daily-tested invariant — identity confusion, data leakage, role assumptions, and onboarding gaps all surface immediately rather than at first-customer-launch. It also creates external accountability: someone else depending on the system raises the quality bar in a way that no amount of self-discipline replicates. From a productization-readiness angle, the leap from one user to two users is qualitatively the largest leap the system will ever make — far larger than two to a hundred. Crossing that chasm while you still have full architectural latitude is much cheaper than crossing it after launch when assumptions have ossified. Pairing this with a single pipeline keeps scope sane: one shared automation, two real tenants.

**Priors / assumptions this rests on:**
- A second real user surfaces multi-tenant bugs that solo dogfooding does not — confidence: **high**
- The author has a willing trusted beta user with overlapping pipeline needs — confidence: **low** (unknown — depends on social context)
- Manual onboarding overhead is bounded and won't dominate v1 effort — confidence: **medium**
- The second user's feedback will be high-signal rather than noise about polish gaps — confidence: **medium-low**

### Option D — Author-only, defer productization

Build a personal tool. "Done" = the author has something useful. Skip multi-tenancy, defer auth, defer the data-model gymnastics that productization requires. Use the system as a single user for 6–12 months, learn what's actually valuable, and revisit productization with hard-won evidence.

**Steel-manned reasoning:** Premature multi-tenancy is one of the most common forms of YAGNI in software. The vision doc says "personal assistant" — start there literally. Many durable products started as single-user or single-team tools before being abstracted: Linear's internal tracker, Basecamp's consultancy planner, Superhuman's founder's mailbox. Building for tenancy you don't have is paying interest on a loan you may never take out. The escape hatch is good engineering: clean interfaces, dependency injection, and a sane data model mean a future tenancy retrofit is bounded work, not a rewrite. Meanwhile, every hour not spent on auth, role checks, and tenant scoping is an hour spent on the actual product — which is what generates the learning that tells you whether productization is even the right move.

**Priors / assumptions this rests on:**
- Retrofitting multi-tenancy onto a clean single-user codebase is bounded work — confidence: **medium-low** (real-world retrofits frequently uncover tangled assumptions; this is the prior most commonly wrong)
- The author's single-user usage will reveal what's worth productizing — confidence: **medium**
- Time saved by deferring tenancy translates to a meaningfully faster v1 — confidence: **medium**
- The "productizable from day one" non-negotiable in VISION.md is worth revisiting if it's blocking velocity — confidence: **low** (the user explicitly listed it as non-negotiable; reopening it weakens the design framework)

## Recommendation

**Option A — author-only, single deep pipeline (the north-star case).**

The north-star use case is already on the wall as the architecture's design pressure. Use it. Building it end-to-end forces every load-bearing architectural decision to be made under real conditions: durable execution because the pipeline spans days, retrieval because it pulls from prior context, retries because it calls external APIs, and tenant boundaries because they're scaffolded from the start even if only one tenant exists. Option B sounds appealing but routing isn't a real problem until there are real pipelines to route between, and three shallow pipelines tend to ship as three barely-integrated automations rather than a coherent platform. Option C adds a hard dependency (a willing beta user, manual onboarding, real reliability) before the engine itself works — wrong order of operations. Option D contradicts a stated non-negotiable.

**Key reason it wins:** the deepest pipeline produces the most architectural pressure per unit of effort, and forcing v1 to express the north-star case is what prevents v1 from shipping the wrong primitives.

**Main risk we're accepting:** one pipeline may not fire often enough to generate dense daily dogfooding signal. Mitigation: pick the pipeline carefully — if "follow-up with prep" only triggers weekly, choose a north-star-class pipeline that fires more often (e.g., daily morning briefing assembly), or commit to pipeline #2 being scoped immediately after v1 lands rather than as a new milestone.

## Decision

**Option A — author-only, single deep pipeline (the north-star case).** Decided 2026-04-28.

V1 serves one user (the author). "Done" = a single north-star-class pipeline runs end-to-end on real Plaud transcripts arriving via email, durably and reliably. Multi-tenancy is structurally present in the data model and code (tenant boundaries, auth scaffolding) but only one tenant exists in production. Pipeline routing is trivial in v1 because there's only one pipeline.

The specific north-star pipeline (follow-up-with-prep vs. a higher-frequency variant like a daily morning briefing) is deferred to a sub-decision once the architecture is firmer.

## Consequences

**Locks in:**
- V1 success criterion is a single pipeline that exercises the full architecture: durable execution, retrieval, external API calls, retries, and tenant scoping.
- Multi-tenancy must be structurally present from day one even though only the author uses it. This shapes the data model, auth, and workflow-engine choice — none of these may assume a single-tenant world.
- Pipeline-routing ergonomics are a v2 concern, not a v1 concern. Trivial routing is acceptable in v1.
- Onboarding UX, billing, self-serve flows, and admin tooling are explicitly out of scope for v1.

**Creates / constrains follow-up decisions:**
- Q2 (primary user surface) is now narrower: the surface only needs to serve the author and the chosen pipeline, not a general user base.
- The choice of north-star pipeline (follow-up-with-prep vs. daily morning briefing vs. another candidate) is now an open sub-question. To be opened as a decision once the routing/pipeline-definition layer is firmer.
- Workflow engine (Q5) will be judged primarily on durable-execution depth, not on multi-pipeline orchestration breadth.
- Auth provider (Q9) will be judged on whether tenant scaffolding is clean, not on user-facing onboarding polish.

**Risks accepted:**
- The chosen pipeline may fire infrequently, producing thin daily dogfooding signal. Mitigation: pick a higher-frequency pipeline if follow-up-with-prep proves too rare in practice, or queue pipeline #2 immediately after v1 lands.
