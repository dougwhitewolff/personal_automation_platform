---
number: 005
title: Backend framework
status: accepted-open-for-re-evaluation
date: 2026-04-28
---

# 005 — Backend framework

**Status:** accepted, **open for re-evaluation** (flagged 2026-04-28 after the headless-backend reframe in [003](003-primary-user-surface.md))
**Date:** 2026-04-28

> **Open question flag (2026-04-28):** Original decision was Next.js with App Router, predicated on voice-app being a Next.js app *with a dashboard* (Server Components + Server Actions + route handlers in one framework). After [003](003-primary-user-surface.md) was substantively rewritten — voice-app has zero user-facing UI in v1; super-admin is a separate Next.js app per [019](019-repo-structure.md) — Next.js's value proposition for `apps/voice-app/` collapsed to "Vercel deploy convenience and ecosystem familiarity," which is real but thin justification.
>
> Two reviewers (separate post-session reviews) independently flagged that **NestJS or Hono would be more idiomatic** for a pure backend service. NestJS specifically would also match 4tradesCRM's stack, sharing patterns and controller/module/DI conventions across products.
>
> Author's call (2026-04-28): "unsure." Decision left as-is for now (Next.js for `apps/voice-app/`); flagged for re-evaluation before serious implementation work begins. Super-admin stays Next.js regardless — that decision isn't in scope for the re-eval.
>
> **Re-evaluation criteria documented now to keep it concrete:**
> - **Framework idiomatic-ness for service-shaped code.** Does the framework's primitives (route handlers vs. controllers) feel natural for the work voice-app actually does (webhook receivers, REST APIs, Inngest function entry points)?
> - **Match with 4tradesCRM's stack.** Does shared framework family across products provide meaningful productivity benefit (shared patterns, shared utilities, less context-switching)?
> - **Vercel deployment ergonomics.** How much does single-vendor consolidation with CRM (per [011](011-hosting-and-deployment.md)) actually buy us in practice? Would Fly/Railway for voice-app be a meaningful drag?
> - **Inngest integration.** All three frameworks (Next.js, NestJS, Hono) have viable Inngest integrations; differences are stylistic.
>
> **Path to resolve:** before serious code is written, hello-world the same Plaud-ingestion-to-CRM-output flow in each candidate (Next.js, NestJS, Hono). Pick the framework that produces the cleanest service-shaped code for our actual workload. ~1 day of throwaway code; high-signal answer.

## Question

Which TypeScript-on-Node framework hosts the backend? The framework's job in v1: serve the web dashboard, handle inbound webhooks (email ingestion now, Plaud API later), expose API endpoints the dashboard consumes, and trigger durable workflow runs into the workflow engine (decided separately in Q6).

The architectural sub-question is whether to use a **full-stack framework** (one tool serving both backend and frontend) or a **decoupled stack** (lightweight API backend + separate React SPA frontend).

## Why this matters now

The framework choice shapes daily authoring experience for the solo dev, deploy topology, deployment count (one service vs. two), and how cleanly the workflow engine integration sits. It also locks in defaults around routing, data fetching patterns, server/client boundary, and rendering model. Most decisions downstream of this (hosting, observability, repo structure) are mildly constrained by the choice.

The dashboard from [003](003-primary-user-surface.md) is the dominant load. It's an internal, single-user, observability-first UI — not a public marketing site. SEO doesn't matter; SSR adds complexity we don't need for a logged-in dashboard. That weakens the case for full-stack frameworks that derive their value from SSR/SSG, and strengthens the case for "ship a clean SPA on top of a clean API."

But the solo-dev cost-benefit calculation pulls the other way: a full-stack framework means one deployment, one build, one config file set, one mental model. That's significant when you're shipping alone.

## Options

### Option A — Next.js (App Router)

Full-stack React framework. App Router with React Server Components for the dashboard; route handlers for webhooks and API endpoints; Server Actions for mutations. Single deploy. Ecosystem dominant in 2026 — every library, every hosting platform, every observability tool treats Next.js as a first-class target.

**Steel-manned reasoning:** For a solo dev, the cheapest source of productivity is "the framework just handles it." Next.js does — routing, bundling, SSR/CSR, API endpoints, data fetching, deployment, image optimization, all in one package with sane defaults. Server Components and Server Actions dramatically reduce the API-layer boilerplate that decoupled stacks require: you can write a dashboard page that fetches data on the server with zero API endpoint to maintain. Vercel deployment is one-click; self-hosting is also well-supported. Inngest and Trigger.dev (likely workflow-engine candidates) ship Next.js helpers that integrate as route handlers in two lines. The ecosystem advantage is real and compounds — every "how do I do X" question has a known answer. The downside (opinionated, ties you to React/Vercel patterns) is mild for a dashboard that doesn't need to fight the framework.

**Priors / assumptions this rests on:**
- Server Components + Server Actions meaningfully reduce API boilerplate vs. decoupled stacks — confidence: **high**
- Next.js ecosystem advantage is the biggest single productivity multiplier for solo dev — confidence: **high**
- The dashboard does not need patterns Next.js makes hard (e.g., complex realtime, exotic rendering) — confidence: **high**
- One deploy is meaningfully simpler than two for solo dev — confidence: **medium-high**
- Workflow-engine SDK integration with Next.js is best-in-class — confidence: **medium-high**

### Option B — Hono + Vite/React SPA (decoupled, lightweight)

Hono as a lightweight TS-first API framework on the backend. Vite + React for the frontend, deployed as a static SPA. Type sharing between backend and frontend via shared zod schemas (or Hono's built-in RPC client, which gives end-to-end typed API calls without codegen).

**Steel-manned reasoning:** Decoupling backend from frontend produces a cleaner architectural boundary that ages well. The backend's job (HTTP, webhooks, workflow integration, business logic) is meaningfully different from the frontend's job (UI, state, rendering), and forcing them into one framework conflates concerns that benefit from separation. Hono is delightful to use — TS-native, edge-runnable, small, fast, with first-class middleware patterns and excellent type inference on routes. The dashboard is internal and single-user, so SSR adds nothing — a Vite-built SPA loads in <1 second once cached and gives you a much simpler frontend mental model. Two deploys is a real overhead, but for a single-author project where both deploys are tiny, the cost is bounded. And the long-run benefit is huge: if you ever want to add a mobile client, a CLI, or another frontend, the API is already there as a clean contract.

**Priors / assumptions this rests on:**
- Hono's RPC client provides end-to-end type safety as good as Server Actions — confidence: **medium-high**
- Two deploys for a solo dev is bounded overhead, not a meaningful drag — confidence: **medium**
- The "future client" optionality (mobile, CLI) is worth paying for in v1 — confidence: **medium-low** (Q1 explicitly punts on mobile; speculative future clients are YAGNI)
- The SPA model is sufficient for an internal dashboard's UX — confidence: **high**
- Hono's ecosystem and integrations match Next.js's for the things we'll actually do — confidence: **medium** (Hono is excellent but smaller; some workflow-engine helpers may not have first-class Hono adapters)

### Option C — Remix / React Router 7

Full-stack React framework, "web fundamentals" philosophy — embraces nested routes, loaders, actions, and progressive enhancement. By 2026, Remix has merged into React Router 7, with the same primitives (loaders/actions) but unified APIs. Single deploy, similar developer experience to Next.js but with a different design philosophy.

**Steel-manned reasoning:** Remix's design embodies a coherent philosophy — let the platform do its job, lean into HTTP, embrace forms and progressive enhancement — that produces simpler code than Next.js's evolving server-component model. Loaders and actions are dead-simple primitives: a loader fetches data for a route, an action mutates it. No magic, no bundler-time inference of what runs where. For an internal dashboard where the rendering model doesn't need to be fancy, Remix's clarity is a real advantage. And the merger with React Router unifies the React routing ecosystem under one set of primitives, which suggests the API surface is settling rather than churning.

**Priors / assumptions this rests on:**
- Remix's philosophy produces simpler code than Next.js for our use case — confidence: **medium** (genuinely depends on developer preference)
- React Router 7 is mature and stable in 2026 — confidence: **medium-high**
- The ecosystem advantage of Next.js doesn't materially hurt Remix for our needs — confidence: **medium-low** (Next has a meaningful lead in integration coverage)
- Solo dev productivity on Remix matches Next.js — confidence: **medium**

### Option D — NestJS + Vite/React SPA (decoupled, opinionated)

NestJS as an opinionated, decorator-driven TS backend framework — modules, providers, dependency injection, controllers. Frontend is a separate Vite/React SPA. NestJS's structure is enterprise-style: heavy on patterns, organized via modules.

**Steel-manned reasoning:** NestJS imposes discipline. For a long-lived hosted service that needs to grow into multi-tenancy, multiple integrations, and eventually multi-user, NestJS's module structure and DI container pay off — testability is excellent, code organization is clear, and patterns scale gracefully when the codebase grows. The "productizable from day one" non-negotiable in VISION.md pulls in this direction: enterprise-style architecture from v1 means fewer refactors at v2/v3. The decorator-heavy style is a learning curve but pays back in maintainability.

**Priors / assumptions this rests on:**
- NestJS's structure pays off for v1 scope — confidence: **low** (NestJS shines at team scale; solo dev pays the ceremony cost without the team-coordination benefit)
- DI and module patterns produce testability worth the boilerplate — confidence: **medium-low** (testability is achievable with simpler patterns)
- The codebase will grow large enough for NestJS structure to matter in v1 — confidence: **low** (premature for the scope)
- Decorator-driven style is a productivity gain, not a cost — confidence: **low** (most devs find it heavyweight)

## Recommendation

**Option A — Next.js (App Router).**

For a solo dev with a single-deploy budget, internal-dashboard requirements, and a need to ship reliably, Next.js wins on every dimension: maximum ecosystem support (every workflow engine, every hosting platform, every observability tool ships first-class Next.js helpers), Server Components/Actions eliminate large amounts of API-layer boilerplate, and the framework handles every pattern we need with sensible defaults. The downside (opinionated, tied to React) doesn't bite because we're building a React dashboard either way. Hono + SPA (Option B) is genuinely cleaner architecturally but pays a real cost in two deployments, two builds, and "future optionality" that VISION explicitly defers (mobile is out of scope per Q1). Remix (Option C) is a defensible alternative if Next.js's evolving server-component model feels uncomfortable, but the ecosystem advantage of Next.js is meaningful at solo-dev scale. NestJS (Option D) is over-engineered for v1.

**Key reason it wins:** ecosystem leverage. Every "how do I integrate X" question has a known answer with Next.js. For a solo dev, every saved hour of integration spelunking is an hour spent on the actual product.

**Main risk we're accepting:** lock-in to Next.js patterns and Vercel-adjacent deployment defaults. Mitigation: the workflow engine choice (Q6) is the load-bearing piece for durable execution; Next.js is the dashboard host, not the business logic owner. If we ever outgrow Next.js, the workflow engine has the durable state, and we can migrate the dashboard layer independently.

## Decision

**Option A — Next.js (App Router).** Decided 2026-04-28.

Next.js with App Router serves as the unified framework: React Server Components for the dashboard, route handlers for inbound webhooks (email ingestion, future Plaud), Server Actions for dashboard mutations, and integration points for the workflow engine (Q6) via route handlers.

## Consequences

**Locks in:**
- Single deploy unit for backend + frontend in v1.
- React as the UI library (ecosystem-coupled).
- App Router patterns (Server Components + Server Actions + route handlers) as the v1 default. No Pages Router unless a specific need surfaces.
- Server Components handle data fetching for the dashboard; Server Actions handle mutations. API endpoints exist only for webhooks and external callers (workflow engine, future mobile/CLI clients).

**Creates / constrains follow-up decisions:**
- **Q6 (workflow engine)** — engines with first-class Next.js integration are favored. Inngest and Trigger.dev both ship Next.js helpers; Temporal works via its standalone Worker model.
- **Q11 (hosting)** — Next.js-native platforms (Vercel, Netlify) are first-class candidates; Node-friendly alternatives (Fly, Railway, Render) also viable.
- **Q17 (repo structure)** — the dashboard, backend route handlers, and shared types co-locate naturally in the same Next.js app. Pipeline definitions and workflow-engine workers may be separate packages in a monorepo.

**Risks accepted:**
- Lock-in to Next.js patterns. Mitigation: business logic lives in framework-agnostic services and is invoked from route handlers / Server Actions; the workflow engine (Q6) owns durable state independently. Migrating the dashboard layer is a bounded change.
- Server Components + Server Actions are still evolving in the React ecosystem; some patterns may require revisiting as the framework matures. Acceptable cost for the ecosystem leverage gained.
