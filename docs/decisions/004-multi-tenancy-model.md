---
number: 004
title: Multi-tenancy model
status: accepted
date: 2026-05-01
---

# 004 - Multi-tenancy model

**Status:** accepted
**Date:** 2026-05-01

## Question

How should the service enforce tenant isolation across data, workflows, review queues, app adapters, audit logs, and future auth?

## Why this matters now

Tenancy affects every Prisma model, every query, every workflow event, every review item, and every integration callback. If tenant isolation is not foundational from the first migration, retrofitting it later becomes security-sensitive and tedious.

## Options

### Option A - App-layer tenant enforcement

Every tenant-owned table has `tenantId`. All service methods require tenant context and include tenant filters in queries. Authorization lives in NestJS guards/services rather than Postgres RLS.

**Steel-manned reasoning:** This is the fastest and cleanest option with Prisma. It is easy to test, easy to understand, and works well for a service where access goes through backend APIs/workers rather than direct database clients. Business rules stay in TypeScript where the app logic already lives.

**Priors / assumptions this rests on:**
- All access goes through this service, not direct DB clients - prior probability: 85%
- Prisma remains the primary data-access layer - prior probability: 90%
- We can enforce repository/service patterns consistently - prior probability: 75%

### Option B - Postgres Row-Level Security

Every tenant-owned table has `tenantId`, and Postgres RLS policies enforce tenant isolation at the database layer.

**Steel-manned reasoning:** This is the strongest safety boundary. Even if application code forgets a tenant filter, the database blocks cross-tenant reads/writes. It is excellent for multi-tenant SaaS where security posture matters and multiple clients/tools may touch the database.

**Priors / assumptions this rests on:**
- Defense-in-depth is worth extra complexity now - prior probability: 65%
- We will eventually have direct reporting/admin/database access risks - prior probability: 45%
- The team is comfortable debugging RLS issues - prior probability: 45%

### Option C - Hybrid: app-layer first, RLS-ready schema

Use `tenantId` everywhere and enforce tenant isolation in NestJS now. Design schema, indexes, and access patterns so RLS can be added later without redesign.

**Steel-manned reasoning:** This is the best balance for a fresh build. We get speed and Prisma simplicity now, but tenancy is still part of the data model from day one. The service can later add RLS as a defense-in-depth layer if outside-customer production, direct reporting, or compliance pressure justifies it.

**Priors / assumptions this rests on:**
- Early velocity matters, but tenant boundaries are non-negotiable - prior probability: 90%
- RLS may become necessary later, but not for Slice 1 - prior probability: 70%
- We can write tenant-scoped repositories/services consistently - prior probability: 75%

### Option D - Schema-per-tenant

Each tenant gets its own Postgres schema. Same tables, isolated namespace.

**Steel-manned reasoning:** This provides strong logical separation. Tenant-level backups, exports, deletes, and restore operations can be cleaner than shared-table tenancy. It can fit enterprise tenants that require stricter isolation.

**Priors / assumptions this rests on:**
- Tenants will require strong physical/logical separation soon - prior probability: 20%
- Tenant count stays low enough to manage schemas safely - prior probability: 25%
- Prisma migrations across tenant schemas are acceptable - prior probability: 20%

### Option E - Database-per-tenant

Each tenant gets a separate database.

**Steel-manned reasoning:** This gives maximum isolation and the cleanest enterprise security story. Tenant restore/delete/export is straightforward, and noisy-neighbor effects can be easier to contain.

**Priors / assumptions this rests on:**
- Enterprise-grade isolation is needed immediately - prior probability: 10%
- Operational complexity is acceptable now - prior probability: 10%
- Cross-tenant operations are rare or unnecessary - prior probability: 25%

## Recommendation

Choose **Option C - Hybrid: app-layer first, RLS-ready schema**.

This fits the accepted stack and repo structure. Prisma is simplest when tenant scoping lives in service/repository code, and CRM/Mason should consume this service through APIs/events rather than direct database access. At the same time, tenancy must be foundational from the first migration, so every tenant-owned model should include `tenantId` and supporting indexes.

## Decision

Accepted by the user on 2026-05-01.

Use app-layer tenant enforcement first, with an RLS-ready schema:

- every tenant-owned model gets `tenantId`
- all service methods accept explicit tenant context
- tenant-scoped repository/service helpers are preferred over raw Prisma access
- indexes should include `tenantId` where tenant-scoped lookup/filtering is expected
- cross-tenant isolation tests are required for critical services
- RLS is not enabled for Slice 1
- revisit RLS before outside-customer production, direct DB/reporting access, or stronger compliance requirements

## Consequences

- The first Prisma schema must include tenancy in core models from the beginning.
- Capture events, review items, integration configs, workflow jobs, audit events, and app adapter records must be tenant-scoped.
- NestJS request/workflow context should carry tenant identity explicitly.
- Raw Prisma use should be kept narrow and obvious.
- Future RLS remains possible because schema and access patterns are designed with tenant scoping already in place.
