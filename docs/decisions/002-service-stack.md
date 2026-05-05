---
number: 002
title: Service stack
status: accepted
date: 2026-05-01
---

# 002 - Service stack

**Status:** accepted
**Date:** 2026-05-01

## Question

What stack should we use for the fresh shared automation service that will serve the CRM, the Mason trades marketing generator, and future apps/tools?

## Why this matters now

The stack choice determines the shape of the first scaffold: API framework, module boundaries, data model, workflow runtime, testing strategy, and how app adapters are organized. The service needs to support Plaud-to-CRM first, but the architecture should not collapse into a one-off CRM feature.

## Options

### Option A - NestJS + Prisma + Postgres + Inngest

A TypeScript/Node service using NestJS for the API/application framework, Prisma for schema and database access, Postgres for persistence, and Inngest for durable background workflows.

**Steel-manned reasoning:** This is the grown-up TypeScript service option. NestJS gives modules, dependency injection, services, guards, config, validation, queues, testing patterns, and a natural place to put adapters. Prisma and Postgres give a clear, type-safe data layer for tenants, captures, review items, jobs, and audit events. Inngest gives durable workflows and retries without forcing us to operate a full workflow engine before the product shape is proven.

**Priors / assumptions this rests on:**
- We want TypeScript as the main language - prior probability: 80%
- Service boundaries and adapters will matter soon - prior probability: 85%
- We need durable workflows, but not Temporal-level complexity on day one - prior probability: 75%
- Developer productivity matters more than raw framework minimalism - prior probability: 80%

### Option B - Fastify + Prisma + Postgres + Temporal

A lean TypeScript API on Fastify with Prisma/Postgres for data and Temporal as the workflow engine.

**Steel-manned reasoning:** This is the lean API plus serious workflow engine option. Fastify is fast, direct, and less abstract than NestJS. Temporal is the strongest long-term answer if workflows become mission-critical, long-running, failure-prone, and complex. This stack is excellent if the automation service itself becomes the operational brain of multiple apps.

**Priors / assumptions this rests on:**
- Our workflows will become complex enough to justify Temporal early - prior probability: 45%
- The team is comfortable operating and modeling work in Temporal now - prior probability: 40%
- We prefer explicit lightweight HTTP architecture over framework conventions - prior probability: 50%
- Long-running workflows are central, not just background jobs - prior probability: 60%

### Option C - Hono + Prisma or Drizzle + Postgres + Inngest

A lightweight TypeScript service using Hono, Postgres, a TypeScript ORM, and Inngest.

**Steel-manned reasoning:** This is the modern lightweight service option. Hono is small, fast, Web Standards-based, and portable across runtimes. It is appealing if we want simple handlers, low ceremony, and edge/serverless optionality. Paired with Inngest, it can still handle durable workflows without much infrastructure.

**Priors / assumptions this rests on:**
- This service stays relatively small/simple for a while - prior probability: 35%
- The team prefers lightweight framework composition - prior probability: 55%
- Edge/runtime portability matters materially - prior probability: 30%
- We can maintain clean boundaries without Nest-style structure - prior probability: 50%

### Option D - Next.js App + Route Handlers + Prisma + Inngest

A full-stack Next.js application where the API lives in route handlers and service UI can live alongside backend code.

**Steel-manned reasoning:** This is the fastest route to visible product if the service also needs an admin UI, review queue UI, tenant config UI, and internal dashboard immediately. Next.js gives API handlers plus frontend in one repo, and Inngest fits well with web-app deployments.

**Priors / assumptions this rests on:**
- We need substantial UI in this repo immediately - prior probability: 35%
- Speed to visible product matters more than clean service separation - prior probability: 40%
- CRM and Mason can tolerate a web-app-centered service boundary - prior probability: 30%
- The review/admin UI is first-class in this repo from the start - prior probability: 45%

### Option E - Supabase-centered stack

A managed-platform approach using Supabase Postgres/Auth/RLS/Edge Functions, plus Inngest or lightweight workers for background work.

**Steel-manned reasoning:** This is the managed platform option. Supabase gives Postgres, Auth, RLS, storage, edge functions, scheduled function patterns, and admin tooling quickly. It is compelling if we want to avoid building auth/tenant plumbing from scratch and get productive fast.

**Priors / assumptions this rests on:**
- Managed auth/RLS is a major accelerator - prior probability: 60%
- Workflows remain short or are delegated elsewhere - prior probability: 45%
- The team is comfortable with Supabase conventions - prior probability: 50%
- Avoiding infrastructure matters more than custom service control - prior probability: 45%

## Recommendation

Choose **Option A - NestJS + Prisma + Postgres + Inngest**.

It gives the service the right shape without overpaying complexity on day one. NestJS fits the adapter/module structure we already know we need: CRM adapter, Mason adapter, Plaud ingestion, review queue, workflow, tenant settings, and audit. Prisma/Postgres gives a clean data model, and Inngest gives durable workflow primitives now while leaving room to move specific workflows to Temporal later if they become heavy enough.

## Decision

Accepted by the user on 2026-05-01.

Use:

- Runtime/API: TypeScript + Node.js + NestJS
- Database: Postgres
- ORM/migrations: Prisma
- Workflows: Inngest initially
- Testing: decide during scaffold, with Jest or Vitest as the likely options
- Validation: decide during scaffold, with Zod or class-validator as the likely options

## Consequences

- The first scaffold should be a service-first NestJS app, not a Next.js product UI.
- Domain boundaries should be module-oriented from the beginning: tenants, apps, integrations, captures, review queue, workflows, audit, and app adapters.
- CRM and Mason should consume the service through APIs/events rather than shared database internals.
- Inngest is the initial durable workflow runtime. Temporal remains a future option if workflow complexity justifies the added operational weight.
- Postgres/Prisma schema design becomes one of the next blocking decisions.
