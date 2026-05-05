---
number: 003
title: Repo structure
status: accepted
date: 2026-05-01
---

# 003 - Repo structure

**Status:** accepted
**Date:** 2026-05-01

## Question

How should we structure this fresh automation service repository so we can build quickly now while keeping a clean path for CRM, Mason, and future app integrations?

## Why this matters now

The repo structure determines where the NestJS scaffold, Prisma schema, tests, app adapters, and future client contracts live. It also determines whether we pay monorepo complexity immediately or defer it until there is a real second package.

## Options

### Option A - Single NestJS service package

One deployable service package at repo root with `src/`, `prisma/`, `test/`, and `package.json`.

**Steel-manned reasoning:** This is the fastest path to a real service. It has the least ceremony and fits the current reality: CRM and Mason are expected consumers, not necessarily packages inside this repo. NestJS modules can still keep strong internal boundaries: tenants, apps, integrations, captures, reviews, workflows, and app adapters.

**Priors / assumptions this rests on:**
- This repo starts as one deployable service - prior probability: 85%
- CRM and Mason are separate apps/repos - prior probability: 75%
- Speed matters more than future package elegance today - prior probability: 80%

### Option B - Monorepo now with one app

A workspace structure such as `apps/service`, `packages/shared`, and `packages/client`.

**Steel-manned reasoning:** This gives clean expansion paths immediately. The service can live in `apps/service`, shared types can go in `packages/shared`, and future SDK/client code can go in `packages/client`. This fits a service that multiple apps will consume and reduces future migration work.

**Priors / assumptions this rests on:**
- We will need generated/shared client types soon - prior probability: 70%
- Mason/CRM integration code benefits from shared packages - prior probability: 65%
- Extra scaffold complexity will not slow us much - prior probability: 60%

### Option C - Monorepo with service and admin UI from day one

A workspace structure such as `apps/service`, `apps/admin`, `packages/shared`, and `packages/client`.

**Steel-manned reasoning:** Review queues, tenant settings, audit views, and admin tools likely need UI eventually. Starting with an admin app avoids bolting it on later and makes the service operable from the beginning.

**Priors / assumptions this rests on:**
- Admin/review UI is needed in this repo immediately - prior probability: 35%
- The UI shape is known enough to scaffold now - prior probability: 25%
- Early UI velocity matters more than service-only focus - prior probability: 35%

### Option D - Single service now, generated SDK/client later

Start with one service package, but treat the API contract as the integration boundary and leave room to generate typed clients later from OpenAPI or another contract format.

**Steel-manned reasoning:** This keeps the repo simple while preserving a path for CRM and Mason to consume typed APIs later. It avoids premature package structure and makes the API contract, not shared database internals, the boundary between the service and its consumers.

**Priors / assumptions this rests on:**
- API contract matters more than shared code early - prior probability: 80%
- We can add SDK generation later without major pain - prior probability: 70%
- A single service package will be enough for the first Plaud slice - prior probability: 85%

### Option E - Separate repos for service, SDK, and admin

Separate repositories for each deployable artifact or published client.

**Steel-manned reasoning:** This creates strong boundaries and independent lifecycles. It is useful once the platform is mature, multiple teams own different surfaces, and versioned SDKs/admin tools need to move independently from the service runtime.

**Priors / assumptions this rests on:**
- We need independent versioning/deploy cycles immediately - prior probability: 20%
- Multiple teams are already working independently - prior probability: 15%
- Coordination overhead is worth paying now - prior probability: 15%

## Recommendation

Choose **Option D in practice, implemented as Option A initially**: start with a single NestJS service package, but design it as an API-first service with DTOs/OpenAPI so client SDKs can be generated later.

This gets us building immediately while preserving the right future boundary. We avoid monorepo ceremony until there is a real second package, but the service still treats CRM, Mason, and future apps as external consumers rather than database roommates.

## Decision

Accepted by the user on 2026-05-01.

Use a single service package at repo root for now:

```text
src/
  app.module.ts
  main.ts
  tenants/
  apps/
  integrations/
  captures/
  reviews/
  workflows/
  adapters/
    crm/
    mason/
  common/
prisma/
test/
docs/
```

Keep the structure API-first and monorepo-ready. Add workspace packages only when a real second package exists, such as a generated client SDK, admin UI, or shared package with enough substance to justify its own lifecycle.

## Consequences

- The first scaffold should live at the repository root, not under `apps/service`.
- NestJS modules become the primary boundary mechanism for now.
- OpenAPI/DTO discipline matters because generated clients may come later.
- CRM and Mason integrations should be modeled as adapters and API/event consumers, not shared database access.
- A future monorepo migration remains available, but it is deliberately deferred.
