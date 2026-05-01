---
number: 004
title: Language and runtime
status: accepted
date: 2026-04-28
---

# 004 — Language and runtime

**Status:** accepted
**Date:** 2026-04-28

## Question

What language and runtime do we build the v1 backend on? Options narrow to TypeScript (on Node or Bun), Go, or Python — with Python heavily disfavored by the VISION doc's explicit non-goal ("Python … suboptimal for a product that needs durable workflows, strong typing across many integrations, and a long-lived hosted service").

## Why this matters now

Language choice is one of the highest-cost decisions to revisit later — it locks in tooling, library ecosystem, hiring/community pool, workflow-engine SDK ergonomics, deployment patterns, and the cognitive overhead of context-switching. Several downstream decisions hang directly on this:

- **Q5 (backend framework)** — framework options are language-scoped (Hono/Fastify/Next.js for TS; Echo/Chi for Go; FastAPI for Python).
- **Q6 (workflow engine)** — engines vary widely in SDK quality per language. Inngest and Trigger.dev are TS-first; Temporal is strong in TS, Go, Java, Python; BullMQ is Node-only; Hatchet supports TS, Go, Python.
- **Q11 (hosting)** — all major platforms support all candidates, but Node is most universally first-class.

The dashboard requirement from [003](003-primary-user-surface.md) is the dominant constraint: the frontend will almost certainly be TypeScript (no realistic alternative in 2026). Sharing the backend language reduces context-switching for a solo author, enables shared types between client and server, and concentrates the library ecosystem.

## Options

### Option A — TypeScript on Node

Mature, ubiquitous runtime. Every cloud platform supports it as a first-class citizen. Every workflow engine has a TS SDK. Anthropic's TS SDK is excellent. Next.js, Remix, or Hono for the dashboard side. End-to-end type safety via tRPC or shared zod schemas. Strict TypeScript with `noUncheckedIndexedAccess` and runtime validation (zod) gives strong correctness guarantees.

**Steel-manned reasoning:** This is the path of least resistance for a TypeScript-first product in 2026, and "least resistance" is exactly what a solo author should optimize for. Every library, every workflow engine, every LLM SDK, every hosting platform, every observability tool treats Node as a first-class target. There are essentially zero "does this work?" moments in the stack. TS type safety with strict mode and zod for runtime boundaries is more than sufficient for a system whose primary correctness risk is in prompt construction and integration plumbing, not raw type bugs. Performance is gated by LLM call latency (hundreds of milliseconds to seconds), so any runtime speed difference is invisible in practice. And the dashboard, the backend, and any pipeline-definition DSL can share types via a single `@platform/shared` package — a meaningful productivity multiplier for a solo dev.

**Priors / assumptions this rests on:**
- TS ecosystem maturity covers every integration we'll need — confidence: **high**
- Solo author benefits significantly from single-language stack — confidence: **high**
- TS strict mode + zod is strong enough type safety for this product — confidence: **high**
- Performance is gated by LLM call latency, not runtime — confidence: **high**
- Node remains the most universally supported TS runtime in 2026 — confidence: **high**

### Option B — TypeScript on Bun

Same TypeScript codebase, but on the Bun runtime instead of Node. Bun ships with a built-in bundler, test runner, package manager, faster module resolution, faster HTTP server, native SQLite, and meaningfully faster cold starts. By 2026 Bun 1.x has been stable for ~2 years, hosting platforms (Fly, Railway, Vercel, Render) support it natively, and most Node-package edge cases are resolved.

**Steel-manned reasoning:** Bun delivers the same TypeScript end-to-end story as Node, but with materially better tooling integration. For a solo author, the difference between "install one tool and it does test, bundle, dependency, runtime" vs. "wire up jest/vitest, esbuild/swc, npm/pnpm, node" is meaningful — fewer config files, fewer version-skew bugs, fewer mental tabs open. Bun's startup speed matters concretely for serverless deployments (cold starts are noticeable to users on edge functions) and for local dev iteration speed. Bun's TypeScript-native execution removes the build step in dev. By 2026, the maturity story is solid: the platforms support it, the major libraries work on it, the gotchas are documented. Choosing Node in 2026 is the more conservative call, but conservatism has a cost — you're paying for compatibility you don't need.

**Priors / assumptions this rests on:**
- Bun maturity in 2026 is sufficient for production hosting on a real workflow engine — confidence: **medium-high**
- Bun's tooling integration is a meaningful daily productivity gain for a solo dev — confidence: **medium**
- Bun-specific edge cases are bounded and documented — confidence: **medium**
- Hosting platforms treat Bun as first-class, not second-tier — confidence: **medium-high**
- Workflow engine SDKs (Inngest, Trigger.dev, Temporal, etc.) work on Bun without surprises — confidence: **medium** (some have Node-specific assumptions; risk of hitting one mid-development)

### Option C — Go

Strong static typing, excellent concurrency, single static binary deploy, fast runtime, stable semantics. Workflow engines like Temporal have first-class Go SDKs. Anthropic has a Go SDK. The dashboard remains TypeScript; the backend is Go.

**Steel-manned reasoning:** Go's compile-time guarantees and runtime stability are genuinely best-in-class for a long-lived hosted service. The deployment story (single static binary, no runtime to manage, no node_modules) eliminates an entire category of production headaches. Concurrency primitives (goroutines, channels) make some pipeline patterns more natural to express than they would be in Node's event-loop model. Temporal-on-Go is widely considered the strongest workflow-engine integration in any language. And Go's "boring" reputation is exactly what a long-lived backend benefits from — the language doesn't change much, the patterns stay stable, the bugs are fewer.

**Priors / assumptions this rests on:**
- Polyglot stack (Go backend + TS frontend) is an acceptable cost for solo author — confidence: **low** (real productivity hit; mental context switching is high)
- Go's runtime stability advantage over Node is material in production — confidence: **medium** (true in extreme cases; mostly invisible at our scale)
- Shared types between client and server via codegen (protobuf, OpenAPI) is workable — confidence: **medium-low** (works but adds toolchain complexity)
- Go's LLM ecosystem is mature enough for our needs — confidence: **medium** (Anthropic SDK exists; AI SDK ecosystem is much more developed in TS)
- Go workflow engine support is a tipping factor — confidence: **low-medium** (TS support is also strong; not a deciding factor)

### Option D — Python

Best ML/data ecosystem, mature LLM-specific tooling (LangChain, LlamaIndex, Instructor, etc.), modern Python with Pydantic + FastAPI provides reasonable type safety. The previous prototype was Python.

**Steel-manned reasoning:** Python remains the lingua franca of AI. New LLM techniques typically appear in Python first; the library ecosystem (DSPy, Instructor, Pydantic-AI) is genuinely ahead of TypeScript on some dimensions. Modern Python with strict Pydantic and good typing discipline can be quite robust. Reusing patterns from the prototype is a small but real benefit — some prompts and schemas can be lifted directly.

**Priors / assumptions this rests on:**
- Python's LLM ecosystem advantage is material — confidence: **low** (was true 2 years ago; TS has caught up significantly with AI SDK, Instructor-TS, Mastra, etc.)
- Python type safety is sufficient for an integration-heavy hosted service — confidence: **low-medium** (still behind TS on practice, despite Pydantic improvements)
- The VISION's "Python is suboptimal" bar can be revisited — confidence: **low** (explicit non-goal; reopening it weakens the design framework)

## Recommendation

**Option A — TypeScript on Node.**

The solo-author cost-benefit calculus tips toward maximum predictability and minimum "does this work?" friction. Node is the path of least resistance for every downstream choice — workflow engine, hosting, observability, deployment, framework, library compatibility — and the TS type-safety story is strong enough for this product (the correctness risks live in prompt construction and integration plumbing, not raw type bugs, and zod handles boundary validation cleanly). Bun's tooling advantages (Option B) are real and tempting, but the risk of hitting a Bun-specific edge case in a workflow-engine SDK or hosting integration mid-development is meaningful, and the upside (faster cold starts, integrated tooling) doesn't materially change product velocity for a solo author who'd configure Node tooling once and forget it. Go (Option C) sacrifices the shared-language benefit for runtime advantages that don't matter in an LLM-bound system. Python (Option D) is explicitly disfavored by the VISION doc.

**Key reason it wins:** for a solo author shipping a long-lived product, the cheapest source of productivity is "every library, every platform, every SDK just works." Node is uniquely positioned to deliver that in 2026.

**Main risk we're accepting:** giving up Bun's genuinely better tooling ergonomics. Mitigation: this decision is reversible at the runtime layer alone — the same TypeScript codebase can move from Node to Bun later if the tooling delta becomes a meaningful daily friction. Reopen if Bun's lead grows or if Node-specific tooling friction starts costing real time.

## Decision

**Option A — TypeScript on Node.** Decided 2026-04-28.

Backend and frontend both written in TypeScript on Node.js. Strict TypeScript config (`strict: true`, `noUncheckedIndexedAccess: true`). Runtime validation at boundaries via zod. Shared types between backend, dashboard, and pipeline definitions live in a shared package.

## Consequences

**Locks in:**
- Single-language stack (TypeScript) across backend, frontend, and pipeline definition layer.
- Node.js as the runtime — packages, hosting, observability, and SDK choices all assume Node-first compatibility.
- Strict TypeScript + zod is the v1 type-safety story. No additional runtime type system (no io-ts, runtypes, etc.) unless a specific need surfaces.
- Shared `@platform/shared` (or equivalent) package for types crossing the backend/frontend boundary.

**Creates / constrains follow-up decisions:**
- **Q5 (backend framework)** — narrows to TS-on-Node options: Next.js, Hono, Fastify, NestJS, Remix/React Router, etc.
- **Q6 (workflow engine)** — TS SDK quality is now the primary criterion. Inngest, Trigger.dev, Temporal-TS, Hatchet-TS all viable; BullMQ is Node-native; Go-only or Python-only options are out.
- **Q11 (hosting)** — Node-first platforms preferred (Fly, Railway, Vercel, Render all support; AWS Lambda/ECS also fine).
- **Q14 (LLM provider strategy)** — Anthropic TS SDK and Vercel AI SDK both first-class candidates.
- **Q17 (repo structure)** — TS monorepo (pnpm + turborepo) becomes the default candidate for sharing types across packages.

**Risks accepted:**
- Bun's tooling ergonomics are forgone in v1. Mitigation: this decision is reversible at the runtime layer alone — the same TS codebase can move Node→Bun later if Bun's lead in tooling becomes a meaningful daily friction.
- No catastrophic forgetting risk here — TS-on-Node is the most compatibility-rich path forward, not a niche choice.
