---
number: 019
title: Repo structure
status: accepted
date: 2026-04-28
---

# 019 — Repo structure

**Status:** accepted
**Date:** 2026-04-28

> **Scope amended 2026-04-28:** Original options compared single-package vs. monorepo with one app. After the headless-backend reframe (voice-app has no UI; super-admin is a separate Next.js app per Doug's call), the realistic options shifted to monorepo-with-two-apps vs. two-separate-repos. Accepted option is **B' — monorepo with two apps + shared packages**. Original options preserved for historical context; the decided shape is in the Decision section.

## Question

Single-package Next.js repository, or a monorepo (pnpm + Turborepo) with one app and shared internal packages? A third option exists but is bigger: combining voice-app and 4tradesCRM into a single monorepo.

## Why this matters now

The repo shape affects daily authoring (where files live, how imports resolve), build-time orchestration (one `next build` vs. multiple), CI/CD (Q22), and the path to extracting shared packages (e.g., the `@4trades/tools` package mentioned as a v2 possibility in [016](016-agent-and-tool-architecture.md)).

The decided constraints narrow this: [005](005-backend-framework.md) says Next.js with App Router as the single deploy unit; [011](011-hosting-and-deployment.md) confirms one Vercel project; [016](016-agent-and-tool-architecture.md)'s three-layer architecture (`pipelines/`, `agents/`, `tools/`) lives somewhere — those directories can sit at the root of a Next.js app or in shared packages of a monorepo.

## Options

### Option A — Single-package Next.js repo

One `package.json`. All code in one Next.js app:

```
voice-app/
├── package.json
├── next.config.ts
├── app/                  ← Next.js App Router
├── pipelines/            ← per [015]
├── agents/               ← per [016]
├── tools/                ← per [016]
├── lib/                  ← shared utilities (auth, db, llm, memory, etc.)
├── components/           ← React components for the dashboard
├── emails/               ← React Email templates per [012]
├── prisma/ (or supabase/)← schema migrations
└── tests/
```

**Steel-manned reasoning:** Simplest possible structure. One `package.json` to maintain, one `tsconfig.json`, one set of scripts, one CI configuration. Imports resolve via path aliases (`@/lib/...`). Vercel deploys it natively with no monorepo config. For a solo dev with one deploy unit, this is the right shape. The cost of a monorepo (workspace config, build orchestration, dependency hoisting quirks) doesn't pay off until there are multiple deployable apps or genuinely shared packages with independent versioning needs.

**Priors / assumptions this rests on:**
- One deploy unit in v1 + v2 — confidence: **high** (Next.js as backend + frontend per [005](005-backend-framework.md); no separate worker service)
- Shared `@platform/shared` package idea (mentioned in [004](004-language-and-runtime.md)) is satisfiable via internal directory imports — confidence: **high**
- Future extraction to a monorepo is bounded if it ever becomes worth it — confidence: **medium-high** (move directories into `packages/<name>/`, add workspaces, adjust imports — bounded)
- Solo dev productivity is meaningfully higher with single-package — confidence: **medium-high**

### Option B — Monorepo (pnpm + Turborepo) with one app + shared internal packages

```
voice-app-monorepo/
├── pnpm-workspace.yaml
├── turbo.json
├── apps/
│   └── web/              ← the Next.js app
└── packages/
    ├── shared/           ← types shared across packages
    ├── pipelines/
    ├── agents/
    ├── tools/
    └── llm/              ← LLM client wrapping Vercel AI SDK
```

**Steel-manned reasoning:** Monorepo enforces clean module boundaries. Each package has its own `package.json`, its own dependencies, its own tests, its own contracts. Refactoring one package can't accidentally break another. When v2 brings the `@4trades/tools` shared package idea from [016](016-agent-and-tool-architecture.md), it's a natural addition. Turborepo caches build artifacts so unchanged packages don't rebuild. For a long-lived hosted service that may grow into multiple deployable units (a CLI, a worker process, a third-party-CRM-specific shim), monorepo is the natural foundation.

**Priors / assumptions this rests on:**
- Module-boundary enforcement is meaningfully valuable in v1 — confidence: **low** (one deploy unit; one author; benefits compound at scale, not v1)
- Turborepo caching saves real time — confidence: **medium** (real but solo dev rarely re-runs partial builds)
- Future deployable units (CLI, worker, etc.) materialize — confidence: **low** (no v1 evidence)
- Workspace config overhead is bounded — confidence: **medium-high** (real but tractable)

### Option C — Combined monorepo with 4tradesCRM

Bring voice-app and 4tradesCRM into one monorepo. Shared packages for tools, types, design tokens. Single repo, multiple deployable apps.

**Steel-manned reasoning:** Maximum sharing potential. `@4trades/tools` exists from day one. Type sharing for CRM-API contracts is automatic. Refactors that span both products happen in one PR. For a multi-product company building tightly-coupled products on the same stack, this is the natural shape.

**Priors / assumptions this rests on:**
- 4tradesCRM is ready to be moved into a monorepo — confidence: **low** (real disruption to a working product; meaningful migration effort)
- Voice-app and 4tradesCRM share enough code to justify combined repo — confidence: **low** (CRM is NestJS + Prisma; voice-app is Next.js. Different stacks, limited shared code in v1)
- Cross-product refactor velocity is meaningfully better than two-repo coordination — confidence: **medium** (real but not v1 critical)
- Combined CI / deploy / dependency-update overhead is bounded — confidence: **low-medium** (large monorepos accumulate operational complexity)

## Recommendation

**Option A — Single-package Next.js repo.**

For a solo dev with one deploy unit and a Next.js stack, single-package is the right shape. Simpler tooling, fewer moving parts, faster iteration, native Vercel deploy. Monorepo (Option B) pays for module-boundary enforcement and future deployable units we don't yet have evidence for. Combined repo (Option C) requires disrupting a working CRM for benefits that don't materialize until v2+.

**Future-extension path documented:** if/when v2 requires extracting shared packages (e.g., `@4trades/tools` per [016](016-agent-and-tool-architecture.md)) or adding deployable units beyond the Next.js app (a separate worker, a CLI, etc.), migrating to Option B is bounded engineering — move `pipelines/`, `agents/`, `tools/`, `lib/` into `packages/<name>/`, add `pnpm-workspace.yaml`, adjust import aliases. Roughly one to two days of work, well-precedented.

**v1 deliverables:**
1. Single `package.json` at repo root.
2. TypeScript path aliases configured: `@/lib`, `@/pipelines`, `@/agents`, `@/tools`, `@/components`, `@/emails`.
3. Strict TypeScript (`strict: true`, `noUncheckedIndexedAccess: true`) per [004](004-language-and-runtime.md).
4. Vercel deploys this repo's `main` branch as production; PR branches as previews per [011](011-hosting-and-deployment.md).

**Key reason it wins:** simplest structure that satisfies all constraints; future-extension to monorepo is bounded and only paid for when needed.

**Main risk we're accepting:** if multiple deployable units materialize sooner than expected, we pay the monorepo migration cost at that point rather than upfront. Mitigation: this is a known bounded migration; we accept the deferral.

## Decision

**Option B' — Monorepo with two Next.js apps + shared packages.** Decided 2026-04-28.

After the headless-backend reframe (voice-app has zero user-facing UI; super-admin is a separate Next.js app per Doug's explicit choice not to embed admin views in 4tradesCRM), the v1 codebase has two distinct deployable units. Monorepo with shared packages is the right shape — type sharing across apps is intense (every audit-log shape, every webhook contract, every Zod schema is consumed by both), and atomic refactors matter for solo dev productivity.

```
voice-app-monorepo/
├── pnpm-workspace.yaml
├── turbo.json
├── apps/
│   ├── voice-app/           ← Next.js service (API routes, webhook receivers, Inngest functions, no React UI)
│   └── super-admin/         ← Next.js app with React UI for ops/super-admin views; reads voice-app's admin APIs
└── packages/
    ├── shared/              ← types, Zod schemas, audit-log shapes, webhook contracts, event-name constants
    └── auth/                ← jose-based JWT verifier shared by both apps (per [010](010-auth-provider.md))
```

Both apps deploy as separate Vercel projects from the same repo (well-supported). ESLint rule prevents cross-app imports outside `packages/` — apps consume each other only via API, never via direct imports.

## Consequences

**Locks in:**
- Two deployable Next.js apps in v1: `apps/voice-app/` (the service) and `apps/super-admin/` (ops UI).
- Shared packages in `packages/`: `shared` (types, schemas, contracts) and `auth` (JWT verifier).
- pnpm + Turborepo as the workspace tooling. `pnpm-workspace.yaml` declares workspaces; `turbo.json` orchestrates builds.
- Two Vercel projects from the same monorepo — `voice-app` deploys to `voice.4trades.io` (or chosen subdomain); `super-admin` deploys to its own subdomain (e.g., `voice-admin.4trades.io`).
- ESLint rule (`@nx/enforce-module-boundaries` or equivalent) prevents `apps/voice-app/**` from importing `apps/super-admin/**` and vice-versa. Cross-app communication only via voice-app's admin APIs.
- TypeScript path aliases inside each app: `@/lib/...` resolves locally; `@platform/shared` and `@platform/auth` resolve to the workspace packages.

**Creates / constrains follow-up decisions:**
- **Q22 (CI/CD)** — single CI runs both apps' builds in parallel via Turborepo; deploys both Vercel projects on `main` push.
- **Q21 (observability)** — both apps emit telemetry to the same observability stack; super-admin's UI surfaces voice-app's traces.
- **Future v2 work**: extract more shared packages (`@platform/llm`, `@platform/agents`, etc.) if cross-app reuse warrants. Possibly extract a shared `@4trades/tools` package for reuse with 4tradesCRM (per [016](016-agent-and-tool-architecture.md)) if cross-product patterns emerge.

**Risks accepted:**
- Workspace setup learning curve if anyone joins who hasn't used pnpm + Turborepo. Bounded — half-day orientation.
- Cross-app dep creep risk (super-admin imports from voice-app directly). Mitigation: ESLint rule enforces boundaries.
- Bigger checkout than separate repos. Negligible at this scale.
