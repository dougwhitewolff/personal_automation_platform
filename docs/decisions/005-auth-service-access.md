---
number: 005
title: Auth and service access
status: accepted
date: 2026-05-01
---

# 005 - Auth and service access

**Status:** accepted
**Date:** 2026-05-01

## Question

How should client apps, users, and future service UIs authenticate with the automation service?

## Why this matters now

The first Plaud-to-CRM slice needs a secure way for trusted apps and workers to call the service and carry tenant/user context. The decision affects NestJS guards, API contracts, tenant context, audit records, app adapters, and future review/admin UI.

## Options

### Option A - Clerk for users plus Clerk M2M/API keys for service calls

Use Clerk for human authentication if/when this service has admin or review UI, and Clerk machine auth/API keys for CRM/Mason service-to-service calls.

**Steel-manned reasoning:** Clerk is fast to integrate and has strong developer experience. It supports user auth, organizations, backend request verification, and machine authentication patterns. This gives one vendor for humans and machines, and it fits a TypeScript/NestJS service well.

**Priors / assumptions this rests on:**
- We will need user-facing admin/review UI later - prior probability: 60%
- We want fast implementation over enterprise auth depth today - prior probability: 75%
- CRM/Mason can call this service with dedicated machine credentials - prior probability: 85%
- One auth vendor for user and machine auth is valuable - prior probability: 65%

### Option B - WorkOS for users/organizations plus M2M/API credentials for apps

Use WorkOS AuthKit for users/orgs and WorkOS M2M/API keys for programmatic access from CRM/Mason.

**Steel-manned reasoning:** WorkOS is built for B2B SaaS. Organizations, memberships, SSO, directory sync, RBAC, audit-log posture, and M2M access are central concepts. If this service eventually serves trade businesses with multiple users, teams, roles, and enterprise-ish needs, WorkOS is the cleanest long-term identity foundation.

**Priors / assumptions this rests on:**
- This service will become B2B/multi-org infrastructure - prior probability: 75%
- Enterprise SSO/RBAC/audit posture will matter later - prior probability: 55%
- It is worth paying more setup cost now for cleaner B2B primitives - prior probability: 55%
- CRM/Mason service access should use standard M2M credentials - prior probability: 85%

### Option C - Service-issued API keys first, defer human auth

The service issues its own app-level API keys for CRM/Mason. Human auth is deferred. Review/admin UI either lives inside CRM initially or is protected by CRM auth. Add Clerk/WorkOS later when this service needs its own user surface.

**Steel-manned reasoning:** This matches the immediate architecture. The first consumer is CRM, then Mason. The service does not need to log humans in on day one; it needs to authenticate trusted app callers and attach tenant context to requests. API keys are simple, testable, cheap, and avoid premature identity-vendor lock-in.

**Priors / assumptions this rests on:**
- Slice 1 has no standalone service UI - prior probability: 80%
- CRM/Mason already know the acting user and tenant - prior probability: 75%
- App-to-service auth is the immediate need - prior probability: 90%
- We can implement API key hashing/scoping safely - prior probability: 75%

### Option D - Supabase Auth

Use Supabase Auth for users, JWTs, and possibly organization/team modeling in our own tables.

**Steel-manned reasoning:** Supabase Auth works well with Postgres and JWTs, supports common login methods, and can integrate with RLS if we later go that route. It is pragmatic if we also host Postgres on Supabase.

**Priors / assumptions this rests on:**
- We host Postgres on Supabase - prior probability: 35%
- We want Auth tightly coupled to Postgres/RLS later - prior probability: 35%
- DIY organization modeling is acceptable - prior probability: 55%

### Option E - Custom JWT/OIDC trust from client apps

CRM and Mason authenticate users themselves, then issue signed JWTs to this service. The service verifies tokens using each app's JWKS/shared secret and trusts claims like `tenantId`, `actorId`, `appId`, and scopes.

**Steel-manned reasoning:** This creates a clean service boundary where client apps remain the source of human identity. The automation service only verifies trusted app-issued claims. This can be elegant if CRM and Mason already have mature auth.

**Priors / assumptions this rests on:**
- CRM/Mason already have mature auth and can issue service JWTs - prior probability: 55%
- We want client apps to remain the authority for human identity - prior probability: 80%
- We can standardize claims across apps cleanly - prior probability: 60%

## Recommendation

Choose **Option C now, with a path toward Option E and possibly WorkOS later**.

The service should authenticate client apps using service-issued API keys for the first build. CRM and Mason can pass actor context with requests, and the service can trust that context only when it comes from an authenticated app credential. This keeps Slice 1 moving, avoids premature auth-vendor lock-in, and still creates a strong service boundary.

## Decision

Accepted by the user on 2026-05-01.

Use service-issued API keys first:

- API keys are app-level credentials for trusted client apps/workers
- API keys are stored hashed, not plaintext
- API keys are tenant/app-bound, scoped, rotatable, and auditable
- requests carry explicit tenant/app/actor context
- actor context is trusted only when it comes from an authenticated app credential
- no standalone human login is required for Slice 1
- future human auth provider is deferred until the service owns a real admin/review UI
- future app-issued JWT trust remains a likely evolution path

## Consequences

- The first scaffold needs an API key guard and credential model.
- Core request context should include `tenantId`, `appId`, `actorUserId`, optional `actorEmail`, and scopes.
- Review queue and audit records should preserve both the authenticated app and acting user context.
- CRM/Mason remain the authority for human identity during Slice 1.
- Clerk/WorkOS/Supabase Auth are not required for the first implementation slice.
