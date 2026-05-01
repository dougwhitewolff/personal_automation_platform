---
number: 015
title: Pipeline definition format
status: accepted
date: 2026-04-28
---

# 015 — Pipeline definition format

**Status:** accepted
**Date:** 2026-04-28

## Question

How are pipelines defined in the codebase? Pipelines run on Inngest per [006](006-workflow-engine.md), but the question is whether they're written as raw Inngest functions (with conventions), wrapped in a typed helper (`definePipeline(...)`), declared as config files (YAML/JSON), or expressed in a fluent builder DSL.

The decided constraints make this question more focused than open-ended:

- [002](002-learning-model-and-feedback-architecture.md): "human review" must be a first-class primitive in pipeline definitions.
- [003](003-primary-user-surface.md): pipelines must declare a per-output `review_required` flag (default `true`).
- [009](009-crm-integration-shape.md): pipelines must declare CRM-integration requirements (so a "Lead-write required" pipeline is unavailable in standalone mode rather than failing at runtime).
- [014](014-llm-provider-strategy.md): LLM calls flow through `lib/llm/client.ts`.

The pipeline definition format must accommodate all four of these as first-class metadata + behavior, not as comments or runtime assertions.

## Why this matters now

Pipelines are the v1 product. Their definition shape determines:

- How fast a new pipeline can be added (a v1.x activity)
- How easy it is for a future-non-Doug to read and reason about an existing pipeline
- How metadata (review requirements, CRM dependencies) flows from declaration to dashboard UI to runtime enforcement
- How testable pipelines are in isolation
- How upgradeable the format is when needs change

This is a "decide once" decision because pipelines accumulate — once we have 5–10, retrofitting a new format is real work.

## Options

### Option A — TypeScript code with structured helpers (`definePipeline`, `step.review`)

Pipelines are TS files in `pipelines/` directory. Each file exports a default `definePipeline(...)` call that wraps the raw Inngest function with our domain metadata. A small set of helpers (`step.review`, `step.callCRM`, etc.) wrap Inngest primitives with our review and CRM semantics. Full TypeScript type safety, full debugger support, full editor experience.

```ts
// pipelines/follow-up-with-prep.ts
import { definePipeline, step } from '@/lib/pipelines';
import { llm } from '@/lib/llm/client';
import { z } from 'zod';

export default definePipeline({
  id: 'follow-up-with-prep',
  description: 'Schedule a follow-up reminder with prep work attached',
  triggers: { event: 'transcript.ingested' },
  requiresCRMIntegration: true, // for Lead/Contact write
  outputs: [
    { id: 'calendar-event', kind: 'crm.calendar', reviewRequired: true },
    { id: 'prep-doc', kind: 'crm.document', reviewRequired: true },
  ],
  async run({ event, step, ctx }) {
    const transcript = event.data.transcript;

    const draft = await step.run('draft-prep-doc', async () =>
      llm.generate({
        modelTier: 'high-quality',
        schema: z.object({ title: z.string(), body: z.string() }),
        prompt: `Draft a prep doc for: ${transcript.text}`,
      })
    );

    // First-class human-review primitive
    const verdict = await step.review('approve-prep-doc', {
      output: draft,
      timeoutMs: 24 * 60 * 60 * 1000,
    });

    if (verdict.accepted) {
      await step.run('create-prep-doc-in-crm', () =>
        ctx.crm.docs.create(verdict.editedOutput ?? draft)
      );
    }
  },
});
```

**Steel-manned reasoning:** Pure TypeScript with helpers gives us the maximum power-to-ceremony ratio. Every pipeline gets full TypeScript type safety on inputs, outputs, and step return values. Debugger and editor work normally — set a breakpoint inside a pipeline, see types on hover, refactor with rename across the codebase. Domain metadata (`requiresCRMIntegration`, `outputs[].reviewRequired`) is structured data on the `definePipeline` call — easy to validate, easy to surface to the dashboard UI ("this pipeline requires CRM integration"), easy to test. The `step.review` helper is one place we encode the "human review" primitive from 002 — every pipeline that uses it gets the same audit, timeout, and verdict-event semantics for free. Adding new helpers (e.g., `step.callCRM`, `step.scheduleReminder`) doesn't require changing the format — just write a new helper. This is the canonical "code-as-config" pattern for TypeScript-first stacks in 2026.

**Priors / assumptions this rests on:**
- Pipelines remain authored by engineers (Doug + future contributors), not non-technical operators — confidence: **high** (Q1 is engineer-authored; even productized scope keeps pipelines in code per VISION's "user-defined or app-defined" framing)
- TypeScript type safety on pipeline metadata is meaningfully valuable — confidence: **high** (catches "I forgot to declare requiresCRMIntegration" at compile time)
- A small set of helpers covers the common pipeline patterns — confidence: **medium-high** (review, CRM call, schedule, retrieval — bounded set)
- This format upgrades cleanly as needs evolve — confidence: **high** (just add fields to the `definePipeline` schema)

### Option B — Declarative config (YAML/JSON/TOML) + interpreter

Pipelines are config files. An interpreter at runtime compiles config into Inngest function calls. Config can be edited without recompiling code.

```yaml
# pipelines/follow-up-with-prep.yaml
id: follow-up-with-prep
description: Schedule a follow-up reminder with prep work attached
triggers:
  - event: transcript.ingested
requiresCRMIntegration: true
outputs:
  - id: calendar-event
    kind: crm.calendar
    reviewRequired: true
steps:
  - id: draft-prep-doc
    type: llm.generate
    modelTier: high-quality
    prompt: "Draft a prep doc for: {{ transcript.text }}"
  - id: approve-prep-doc
    type: human.review
    output: "{{ draft-prep-doc }}"
    timeoutMs: 86400000
  # ...
```

**Steel-manned reasoning:** Declarative config makes pipelines easy to read and modify by non-engineers. For a future where Doug or a customer-success team defines pipelines without writing code, this is the right shape. Validation can be enforced via JSON Schema. Config can be versioned, diffed, and reviewed without the cognitive load of TypeScript syntax.

**Priors / assumptions this rests on:**
- Non-engineer pipeline authoring is a v1/v2 concern — confidence: **low** (Q1 is engineer-authored; non-engineer authoring is a v3+ concern at earliest)
- Declarative config can express complex pipeline logic (conditionals, loops, dynamic templating) without becoming a new programming language — confidence: **low** (every config DSL eventually grows into a half-baked language)
- The cost of writing and maintaining the interpreter is bounded — confidence: **low-medium** (real ongoing cost: every new step type needs interpreter support; debugging is much harder)
- Type safety for declarative config matches TypeScript helpers — confidence: **medium** (JSON Schema / Zod can validate, but lacks editor refactoring power)

### Option C — TypeScript builder DSL (`pipeline().step().review().output()`)

Pipelines are TS files using a fluent builder API. Method chaining provides structure; types flow through the chain.

```ts
export default pipeline('follow-up-with-prep')
  .triggers({ event: 'transcript.ingested' })
  .requiresCRM()
  .step('draft-prep-doc', async ({ event }) => llm.generate(...))
  .review('approve-prep-doc', { timeoutMs: 86400000 })
  .step('create-prep-doc-in-crm', async ({ ctx, prev }) => ctx.crm.docs.create(prev))
  .output('prep-doc', { kind: 'crm.document', reviewRequired: true });
```

**Steel-manned reasoning:** Builder DSL provides more visible structure than raw `definePipeline` while staying in TypeScript. Method names guide the author. Type inference can carry data through the chain (each step's output becomes available to the next).

**Priors / assumptions this rests on:**
- Builder API provides meaningful clarity gain over `definePipeline` + helpers — confidence: **low-medium** (real but small; both express the same shape)
- Inter-step type flow via builder chain is implementable cleanly — confidence: **medium** (possible but TypeScript's type-level chains can get gnarly)
- The DSL doesn't grow into its own programming language over time — confidence: **medium-low** (these often do — `if`, `loop`, `parallel` get added)

### Option D — TS code + sibling metadata file

Pipeline logic lives in TS; metadata (review requirements, CRM dependencies, outputs) lives in a sibling JSON/TS const file.

**Steel-manned reasoning:** Separates "what the pipeline does" from "what the system knows about the pipeline." Metadata file is easy to read; logic file can be opaque without making the metadata harder to find.

**Priors / assumptions this rests on:**
- Separation of metadata from logic makes pipelines easier to reason about — confidence: **low** (in practice, drift between the two is common)
- The duplication overhead is bounded — confidence: **low-medium**
- Solo dev productivity is comparable to single-file format — confidence: **low** (more files; more switching)

## Recommendation

**Option A — TypeScript code with structured helpers.**

This is the right level of abstraction for v1 (and likely well past). Pipelines are engineer-authored code; TypeScript's type system catches metadata mistakes at compile time; helpers (`step.review`, `step.callCRM`, etc.) encode the domain-specific primitives from 002, 003, 009 in one place where they can be improved over time. The format is dead simple to extend — when a new pipeline pattern emerges, write a new helper. When a new metadata field becomes useful (e.g., `defaultModelTier: 'cheap'`), add it to the `definePipeline` schema. Migration of existing pipelines is mechanical because everything is typed.

Option B (declarative config) is wrong for v1 because non-engineer authoring isn't a real near-term need; it adds interpreter complexity and gives up TypeScript's type safety. Option C (builder DSL) is mostly aesthetic — same shape as A with more ceremony. Option D (sibling metadata) creates drift between two files that should be one.

**Concrete v1 deliverables:**

1. **`lib/pipelines/define.ts`** — exports `definePipeline(opts)`. Wraps the Inngest function constructor with our metadata schema. Validates metadata at module load time (via Zod).

2. **`lib/pipelines/helpers.ts`** — exports the domain-specific step helpers:
   - `step.review(name, { output, timeoutMs, ... })` — emits a `review-pending` event for the dashboard, calls `step.waitForEvent('verdict.captured', { match: 'data.runId' })`, returns the verdict (accepted/rejected + edited output if any). Audit logged.
   - `step.callCRM(name, callFn)` — wraps a CRM API call with proper auth, retries, and CRM-integration-mode checking (errors fast in standalone mode).
   - More helpers added as patterns emerge.

3. **`pipelines/` directory** — one file per pipeline. Each exports a default `definePipeline(...)` call. v1 starts with one (the north-star pipeline, exact choice TBD per [001](001-target-user-and-v1-scope.md)'s deferred sub-decision).

4. **`pipelines/registry.ts`** — auto-discovers and registers all pipelines in the `pipelines/` directory. Exposes them to (a) Inngest at startup, (b) the dashboard for "available pipelines" listing, (c) the routing layer per Q17.

5. **`PipelineMeta` schema (Zod)** captures the shared structured fields:
   ```ts
   const PipelineMeta = z.object({
     id: z.string(),
     description: z.string(),
     triggers: z.array(z.object({ event: z.string(), match: z.record(z.unknown()).optional() })),
     requiresCRMIntegration: z.boolean().default(false),
     outputs: z.array(z.object({
       id: z.string(),
       kind: z.string(),       // 'crm.calendar', 'crm.document', 'crm.lead', etc.
       reviewRequired: z.boolean().default(true), // default true per 003
     })),
     // ... future fields
   });
   ```

6. **Pipeline-availability check at dashboard render time** — when listing pipelines, the dashboard checks whether the current user's deployment context (standalone vs. CRM-integrated) supports each pipeline's requirements. CRM-required pipelines show as "Unavailable in standalone mode" rather than failing at runtime.

**Key reason it wins:** maximum power-to-ceremony ratio for engineer-authored pipelines on a TypeScript stack; encodes domain primitives (review, CRM-integration) once where they're easy to evolve; full type safety end-to-end; no interpreter to build.

**Main risk we're accepting:** pipelines are not "writable by non-engineers" — that's a deferred concern. If/when non-engineer pipeline authoring becomes a real need (likely v3+), we can build a config-on-top-of-helpers layer that compiles to `definePipeline` calls. The underlying architecture (helpers, primitives) is reusable; only the surface format changes.

## Decision

**Option A — TypeScript code with structured helpers (`definePipeline`, `step.review`).** Decided 2026-04-28.

Pipelines are TS files in `pipelines/` directory, each exporting a `definePipeline({...})` call. Domain helpers (`step.review`, `step.callCRM`, future `step.invokeAgent`) wrap Inngest primitives with our review/CRM/agent semantics. Pipeline metadata (id, triggers, requiresCRMIntegration, outputs) is structured TypeScript validated via a Zod schema at module load time.

**Note:** This is the *orchestration* layer. The *sub-task* layer (agents + tools + skills for open-ended LLM-driven work within pipeline steps) is a separate architectural concern, addressed in [016](016-agent-and-tool-architecture.md).

## Consequences

**Locks in:**
- `lib/pipelines/define.ts` exports `definePipeline(opts)`. Validates metadata at load time via Zod.
- `lib/pipelines/helpers.ts` exports domain step helpers: `step.review`, `step.callCRM`, future `step.invokeAgent`.
- `pipelines/` directory contains one file per pipeline. Auto-discovered and registered at startup.
- `PipelineMeta` Zod schema is the canonical structure: `id`, `description`, `triggers[]`, `requiresCRMIntegration` (default false), `outputs[]` (each with `id`, `kind`, `reviewRequired` default true per [003](003-primary-user-surface.md)).
- Dashboard checks deployment context (standalone vs. CRM-integrated) per pipeline at render time. CRM-required pipelines show as "Unavailable in standalone mode" rather than failing at runtime.

**Creates / constrains follow-up decisions:**
- **[016] (agent and tool architecture)** — defines the sub-task layer that pipelines invoke via `step.invokeAgent(...)`. Architecturally additive; doesn't reshape this format.
- **[017] (pipeline dispatch)** — routing dispatches to specific pipelines via the registry created here.
- **[018] (memory / retrieval)** — pipelines call into the retrieval layer (per [007](007-primary-database-and-vector-store.md)) at appropriate steps.

**Amended 2026-04-28** after the headless-backend reframe and project-entity model decision:
- Each output now declares: `id`, `kind` (e.g., `crm.lead`, `marketing.interaction-log`, `crm.calendar-event`), `reviewRequired` (default true), and a reference to the **webhook contract** for that kind (per [020](020-integration-contracts.md)). Output delivery happens via outbound webhook to the consuming app configured for that kind on the tenant.
- Outputs gain a `projectId` field (or `null` if not project-scoped or identification was inconclusive) per [021](021-project-entity-model.md).
- Pipelines no longer write directly to "native targets" (Calendar, Docs). They produce structured outputs; consuming apps render and handle delivery to user-facing native targets.

**Risks accepted:**
- Pipelines are not "writable by non-engineers" in v1. Mitigation: deferred to v3+ if/when it becomes a real need; can be built as a config-on-top-of-helpers layer that compiles to `definePipeline` calls at that point.
