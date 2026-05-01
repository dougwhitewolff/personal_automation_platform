---
number: 008
title: Multi-tenancy model
status: accepted
date: 2026-04-28
---

# 008 — Multi-tenancy model

**Status:** accepted
**Date:** 2026-04-28

> **Numbering note:** This decision is numbered 008 in sequence. Q8 in the original planning queue (vector store) was folded into [007](007-primary-database-and-vector-store.md). This 008 corresponds to Q9 in the queue (multi-tenancy model). The doc number and queue number are now offset by one and will continue to be — that's fine; the index resolves the mapping.

## Question

How is tenant isolation enforced in the system? V1 has only one tenant (the author per [001](001-target-user-and-v1-scope.md)), but the architecture must be structurally multi-tenant from day one. Specifically: where does the boundary between tenant A's data and tenant B's data get enforced — at the database layer, the application layer, or both?

## Why this matters now

Multi-tenancy is one of VISION's explicit non-negotiables. Picking the wrong enforcement model means either (a) shipping a system that *looks* multi-tenant but leaks data the moment a second tenant exists, or (b) over-engineering a v1 around a constraint that doesn't bite for years. The model also dictates how every query is written from day one — retrofitting tenant scoping into hundreds of queries later is the exact kind of refactor we want to avoid.

The choice ripples directly into:

- **Q10 (auth provider)** — RLS in Postgres needs a way to know "who is this user." Supabase Auth provides `auth.uid()` directly; Clerk/WorkOS require custom JWT verification setup to integrate with RLS.
- **Pipeline code (Inngest functions)** — pipelines run server-side and use service-role credentials that bypass RLS. They must manually scope by `tenant_id`, which is a pattern that needs to be established now.
- **Service-role queries** — admin tasks, cron jobs, system housekeeping. RLS doesn't help here; tenant scoping is on the developer.

## Options

### Option A — Postgres RLS with `tenant_id` columns

Every multi-tenant table has a `tenant_id` column. Row-level security policies on each table enforce `tenant_id = auth.tenant_id()` (or equivalent) at the database layer. The Supabase Auth JWT carries the user's identity; Postgres reads it via `auth.uid()` / `auth.jwt()` and applies RLS automatically. App code uses the user-scoped (anon-key) client for user-facing queries; service-role usage is reserved for explicit system tasks where developer is responsible for tenant scoping.

**Steel-manned reasoning:** RLS is the *correct* place for tenant isolation — at the data boundary itself. Every query, including ones a future-you forgets about, is automatically scoped. A bug in app code that omits a `WHERE tenant_id = ?` filter doesn't leak data because the database refuses to return rows from other tenants. This is defense at the layer that matters: even if the entire application logic is compromised, the database still enforces tenancy. Supabase has the most polished RLS-with-auth tooling in the ecosystem — `auth.uid() = user_id` policies, JWT-based row filtering, and excellent docs make the pattern easy to apply consistently. The performance overhead is real but bounded (RLS adds query-planner work that's typically <10% at our scale). And it sets the right precedent for the team-of-future-developers: "the database is the last line of defense for tenancy." That's a culture worth establishing now.

**Priors / assumptions this rests on:**
- Supabase RLS-with-auth tooling is best-in-class and well-documented — confidence: **high**
- RLS performance overhead is acceptable at v1/v2/v3 scale — confidence: **medium-high** (real overhead but not crippling; tunable with index design)
- The "DB is the last line of defense" pattern is the right cultural anchor — confidence: **high**
- Service-role usage discipline (manual scoping) can be enforced via code review and a small set of helper utilities — confidence: **medium-high**
- Auth choice (Q10) ends up being Supabase Auth or a JWT-compatible alternative — confidence: **medium-high** (this option assumes JWT-based identity threading; Clerk/WorkOS can integrate but require setup)

### Option B — App-layer enforcement only

No RLS. Every query in app code explicitly filters by `tenant_id`. A small set of helper utilities (`tenantScoped()`, `withTenant(ctx)`) wraps queries to make scoping ergonomic. Service-role and user-facing queries use the same enforcement model — code discipline.

**Steel-manned reasoning:** RLS is more complexity than it's worth at our scale. It adds query-planner overhead, complicates debugging (queries return "no rows" for opaque reasons), and forces every developer to learn Postgres-specific RLS syntax in addition to the schema. App-layer enforcement is simpler: every query is a function call, every function call takes a tenant context, you can grep for missing scoping in code review. Modern ORMs like Drizzle and Prisma support tenant-scoping middleware that makes "every query must include tenant_id" automatic. And service-role queries don't get a free pass — they go through the same app-layer wrappers, so you can't accidentally bypass tenancy by switching credentials. For a TypeScript-strict codebase, this is the more idiomatic path.

**Priors / assumptions this rests on:**
- App-layer discipline is sufficient enforcement for our risk tolerance — confidence: **low** (single missed filter = data leak; humans and AI both miss things)
- Query-builder middleware can enforce scoping without bypass — confidence: **medium-high**
- The simplicity gain from skipping RLS outweighs the security loss — confidence: **low** (multi-tenant SaaS gets bitten by app-layer-only patterns repeatedly)
- Solo dev is the only one writing queries, so review-burden risk is bounded — confidence: **medium** (true now; not true at v2+ when contributors arrive)

### Option C — Hybrid: RLS + app-layer (defense in depth)

Both enforcement layers active. App code filters by tenant_id explicitly; RLS also enforces at the database. Maximum security, maximum redundancy, but you maintain two patterns.

**Steel-manned reasoning:** Defense in depth is the canonical security posture. If app-layer scoping is bypassed (a forgotten filter, a service-role query that should have been user-scoped), RLS catches it. If RLS is misconfigured (a missing policy, a bug in the JWT extraction), app-layer scoping catches it. For a system handling sensitive personal data — voice transcripts of someone's life — defense in depth is the responsible posture. The maintenance cost (keeping app-layer and RLS rules in sync) is real but bounded if both are derived from the same `tenant_id` schema convention.

**Priors / assumptions this rests on:**
- The two layers stay in sync without significant coordination overhead — confidence: **medium-low** (in practice they drift; one says yes, the other says no, debugging is painful)
- Sensitive personal data warrants defense-in-depth from v1 — confidence: **medium-high** (voice transcripts are real PII; conservative posture defensible)
- The added complexity is worth the marginal security gain over Option A alone — confidence: **low** (RLS alone is already strong; app-layer adds little if RLS is correctly applied)

### Option D — Schema-per-tenant

Each tenant gets a separate Postgres schema; tables are namespaced (`tenant_a.transcripts`, `tenant_b.transcripts`). App code routes queries to the right schema based on tenant context. Maximum logical isolation within a single Postgres instance.

**Steel-manned reasoning:** Schemas are a real Postgres feature, designed for exactly this. Tenant isolation is structural — there's no `tenant_id` column to forget; tables are physically separate within their schema. Migrations can be applied per-tenant or globally. Tenant data export/deletion is a single `DROP SCHEMA` away — a clean compliance story. For a small number of tenants where each has independent customizations or strong isolation requirements, schema-per-tenant is the right shape.

**Priors / assumptions this rests on:**
- Schema-per-tenant scales to our v3 target (~1,000 users) — confidence: **low** (Postgres performance degrades meaningfully past a few hundred schemas; not a fit for SaaS at scale)
- Per-tenant migrations are an acceptable operational pattern — confidence: **low-medium** (real pain at scale)
- The compliance benefit (clean tenant-deletion via DROP SCHEMA) outweighs the operational cost — confidence: **low** (RLS + cascade delete handles this fine)

## Recommendation

**Option A — Postgres RLS with `tenant_id` columns.**

This is the canonical Supabase + multi-tenant SaaS pattern, and it's canonical for good reasons. Tenant isolation belongs at the data boundary itself, not in app code, because the data boundary is the layer that catches bugs the app layer doesn't. Supabase's RLS-with-auth tooling is best-in-class — the `auth.uid() = user_id` pattern is straightforward to apply consistently — and the performance overhead is bounded at our scale.

App-layer-only (Option B) underestimates the risk of a single missed filter; multi-tenant SaaS systems get bitten by this pattern repeatedly. Hybrid (Option C) adds maintenance cost for a marginal security gain when RLS alone is already strong. Schema-per-tenant (Option D) doesn't fit "scales to many tenants."

Service-role pattern: server-side code (Inngest pipelines, cron jobs, admin tasks) uses Supabase's service-role key, which bypasses RLS by design. We commit to a small set of helper utilities (`withTenant(tenantId, fn)`, etc.) that scope service-role queries explicitly. RLS is defense for the user-facing query path; the helper utilities are defense for the server-side path. Together they cover both paths.

**Key reason it wins:** tenant isolation belongs at the data layer, full stop. Supabase makes RLS the cheapest correct path; everything else either underdefends (B) or over-complicates (C, D).

**Main risk we're accepting:** RLS adds query-planner overhead and can produce confusing "no rows" responses when policies are misconfigured during development. Mitigation: invest in good RLS-policy testing as part of CI (a test suite that creates two tenants and verifies cross-tenant queries return zero rows), and document the helper utilities for service-role queries clearly. We also commit to *not* using Option C (hybrid) — RLS is the source of truth; app-code filters are not added "for safety." That keeps the model coherent.

## Decision

**Option A — Postgres RLS with `tenant_id` columns, plus a super-admin role.** Decided 2026-04-28.

- Every multi-tenant table has a `tenant_id` column. RLS policies enforce tenant scoping at the data layer.
- User-facing queries use the anon-key client (RLS active). Service-role usage is reserved for explicit system tasks (Inngest pipelines, cron jobs, admin automation), and goes through helper utilities that scope queries explicitly: `withTenant(tenantId, fn)`.
- **Super-admin role** is a first-class concept from v1. The pattern is JWT-claim-based with full audit logging.

### Super-admin pattern

> **Amended 2026-04-28** after exploration of `C:\Development\4tradesCRM` revealed an existing super-admin pattern (`isInternalStaff` flag + impersonation endpoint) that the voice-app should mirror for cross-product consistency. The original draft used a `super_admins` table + `app_role: 'super_admin'` JWT claim; the amended version below uses `isInternalStaff: boolean` to match the CRM's claim shape exactly. Audit logging is retained (the CRM doesn't have it; voice-app data is more sensitive and warrants the addition).

A super-admin is a human user (initially: the author and 4Trades internal staff) who can read across all tenants for ops, support, and debugging. The mechanism:

1. **JWT carries an `isInternalStaff: boolean` claim.** Default `false`. Set to `true` for users marked as internal staff in the user record. Claim shape exactly matches 4tradesCRM's existing JWT shape, so a single JWT can grant super-admin access in both products when issued by either system.
2. **RLS policies on multi-tenant tables include an OR condition for internal staff.** Pattern:
   ```sql
   create policy "tenant_or_internal_staff" on transcripts
   for select using (
     tenant_id = (auth.jwt() ->> 'tenantId')::uuid
     or (auth.jwt() ->> 'isInternalStaff')::boolean = true
   );
   ```
3. **Super-admin actions are logged unconditionally.** A `super_admin_audit` table records: `actor_user_id`, `action_type`, `target_tenant_id`, `target_resource`, `query_summary`, `timestamp`. The dashboard's super-admin views write to this table on every read; mutations write before-and-after diffs.
4. **Impersonation flow** (mirrors 4tradesCRM's `/auth/impersonate/{tenantId}` endpoint): an internal staff user can request a tenant-scoped JWT for any tenant; the issued JWT carries `tenantId = <target>` and `isInternalStaff: true`. Standard RLS policies then apply — the user can act *as* the target tenant for support/debugging purposes — but every action is captured by audit logging because of the `isInternalStaff` flag.
5. **The dashboard exposes super-admin views only when `isInternalStaff = true`.** A "super admin mode" toggle in the dashboard surfaces cross-tenant lists, individual tenant views, and pipeline-debug tools. The toggle is a UX affordance — the actual authorization is the JWT claim, enforced in RLS.
6. **Service-role bypass is reserved for non-human system tasks.** Inngest pipelines, cron, scheduled jobs use service-role and scope explicitly via `withTenant(tenantId, fn)`. Service-role is *not* used for super-admin operations — those go through the user-scoped client with the elevated JWT, so they're caught by audit logging and consistent with the dashboard code path.

This keeps super-admin in the same code path as normal user access (just with elevated privileges via JWT), aligns with the CRM's existing pattern, and gives us audit logging for free.

## Consequences

**Locks in:**
- `tenant_id` is a first-class column on every multi-tenant table. Required for RLS policies.
- All user-facing queries use the anon-key Supabase client; RLS is the authoritative tenancy enforcement.
- Service-role queries (Inngest pipelines, cron, automation) go through `withTenant(tenantId, fn)` helper utilities. No raw service-role queries in business code.
- Super-admin role is a v1 product concept, not a v2 add. Implementation (amended 2026-04-28 to match 4tradesCRM's existing pattern) includes:
  - `is_internal_staff: boolean` column on the user record (matching CRM's `isInternalStaff` field)
  - JWT issued for that user carries `isInternalStaff: true` claim (matching CRM's claim shape exactly)
  - RLS policies on every multi-tenant table include an OR clause: `(auth.jwt() ->> 'isInternalStaff')::boolean = true`
  - Impersonation endpoint mirroring `/auth/impersonate/{tenantId}` — internal staff can mint a tenant-scoped JWT for any tenant
  - `super_admin_audit` table; every internal-staff query/mutation writes an audit record (the CRM does not have this; voice-app adds it because of more sensitive data)
  - Dashboard "super admin mode" toggle surfacing cross-tenant views (only available when JWT has the role)
- CI test suite includes a multi-tenant RLS test (creates two tenants; verifies cross-tenant queries return zero rows for normal users; verifies super-admin sees both; verifies audit log records the access).

**Creates / constrains follow-up decisions:**
- **Q10 (auth provider)** — must support custom JWT claims (`app_role`, `tenant_id`) cleanly. Supabase Auth supports this via JWT hooks; Clerk supports via session token customization; Auth.js supports via callback.
- **Q19 (observability stack)** — should surface super-admin actions distinctly (audit log views, alerting on unusual access patterns).
- **Q23 (compliance posture)** — super-admin access to user data is a privacy concern; retention policy on the audit log is a piece of the compliance story.

**Anti-patterns we explicitly reject:**
- Hybrid RLS + app-layer scoping (Option C from above). RLS is the source of truth; app-code filters are not added "for safety." Keeps the model coherent.
- Schema-per-tenant. Doesn't fit our scale target.
- App-layer-only enforcement. Single missed filter = data leak.
- Service-role bypass for super-admin operations. Goes through user-scoped client with elevated JWT instead, so audit logging and dashboard code path stay consistent.

**Risks accepted:**
- RLS adds query-planner overhead and can produce confusing "no rows" responses when policies are misconfigured during dev. Mitigation: CI-level RLS test suite (creates two tenants, verifies isolation), clear documentation of helper utilities, error-message conventions that distinguish "no rows because of RLS" from "no rows because of empty data."
- Super-admin role is itself a security concern — a compromised super-admin account sees everything. Mitigation: audit log of every super-admin action; future enhancement to require step-up auth (re-prompting for password or MFA) before entering super-admin mode in the dashboard. Not v1, but reserve the design space.
- Super-admin access patterns must be audited and reviewed. We commit to surfacing the audit log in the dashboard from v1 (super-admin can see their own audit trail) and in observability tooling for unusual patterns later.
