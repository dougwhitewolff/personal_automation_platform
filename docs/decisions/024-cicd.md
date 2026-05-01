---
number: 024
title: CI/CD
status: accepted
date: 2026-04-28
---

# 024 — CI/CD

**Status:** accepted
**Date:** 2026-04-28

## Question

How do tests, type-checks, lint, security checks, and build verification run on every PR and on every merge to `main`? Vercel handles *deploy* automatically (per [011](011-hosting-and-deployment.md)) — this decision is about everything *before* deploy.

## Why this matters now

CI is what keeps the typed contracts (Zod schemas, RLS policies, webhook contract shapes per [020](020-integration-contracts.md)) honest as the codebase grows. Without it, the "structurally multi-tenant" guarantees from [008](008-multi-tenancy-model.md) decay; output schema drift between voice-app and consuming apps becomes silent corruption; pipeline-step type errors only surface in production. Bounded scope: two apps + shared packages in a monorepo per [019](019-repo-structure.md) means CI orchestrates Turborepo builds across both.

## Decision

**GitHub Actions, Turborepo-orchestrated builds.** Decided 2026-04-28.

GitHub Actions is the de facto default for monorepos hosted on GitHub in 2026, and the only realistic option that integrates cleanly with Turborepo's caching, Vercel's deploy workflow, and Sentry's source-map upload from [022](022-observability-stack.md).

### v1 pipeline (per PR)

1. **Install** — pnpm install with cache (~10s after first run)
2. **Lint** — ESLint across all packages and apps via `turbo lint`
3. **Type-check** — `tsc --noEmit` across all workspaces via `turbo typecheck`
4. **Unit tests** — `turbo test` runs Vitest across packages and apps
5. **RLS test suite** — dedicated step that creates two tenants in a test Postgres, verifies cross-tenant queries return zero rows for normal users (per [008](008-multi-tenancy-model.md)) and that super-admin bypass works
6. **Webhook contract validation** — verifies all output-kind Zod schemas in `packages/shared/contracts/output-kinds/` are valid; verifies version compatibility with the published `@platform/contracts` package consumed by 4tradesCRM (per [020](020-integration-contracts.md))
7. **Build** — `turbo build` builds both apps; cached per-package so unchanged packages skip
8. **Sentry source-map upload** (only on `main`) — uploads source maps via Sentry CLI per [022](022-observability-stack.md); deploys after via Vercel's automatic GitHub integration

### Branch-protection rules

`main` requires:
- All CI checks pass
- At least one approval (in v1 just for the discipline; solo dev still creates a PR rather than committing direct to main, even for self-review)
- No force-push, no direct pushes

### Caching

Turborepo's remote cache uses Vercel's free tier (matches our hosting choice). Cache hits are typical for unchanged packages — typical PR CI on a small change runs in ~2–3 minutes.

### Secrets in CI

GitHub Actions secrets store: `SUPABASE_TEST_DB_URL` (for RLS test suite), `SENTRY_AUTH_TOKEN` (for source-map upload), `VERCEL_TOKEN` (for cache + remote-cache auth). Production runtime secrets live in Vercel per [023](023-secrets-management.md), not in GitHub.

## Consequences

**Locks in:**
- GitHub Actions as v1's CI runner. `.github/workflows/ci.yml` orchestrates the pipeline.
- Turborepo remote cache for build artifact reuse across PR runs.
- Required CI checks gate `main` merges.
- Vercel's GitHub integration handles deploy after CI passes.
- Sentry source-map upload as part of the deploy step.
- RLS test suite is a first-class CI requirement, not an afterthought.

**Creates / constrains follow-up decisions:**
- **Q27 (compliance)** — CI is where security checks (dependency audit, secret scanning) live; complements compliance posture without driving it.

**Risks accepted:**
- GitHub Actions vendor concentration — same vendor as our git hosting. Mitigation: workflow YAML is portable to other CI runners (CircleCI, GitLab CI) if needed.
- Turborepo remote cache occasionally has staleness issues. Mitigation: documented `turbo run --force` escape hatch; rare in practice.

## Decision

_Awaiting decision._

## Consequences

_To be filled in after decision._
