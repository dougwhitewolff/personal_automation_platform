---
number: 010
title: Auth verifier (v1)
status: accepted
date: 2026-04-28
---

# 010 — Auth verifier (v1)

**Status:** accepted
**Date:** 2026-04-28

> **History note:** Originally drafted as "Auth provider" with options for Supabase Auth / Clerk / WorkOS / Auth.js. After [009](009-crm-integration-shape.md) resolved the CRM-integration shape as loose federation, this doc was rewritten with a "standalone sign-up + federated verifier" framing. Doug then correctly observed that v1 has no standalone customers — all v1 users come through 4tradesCRM. The standalone sign-up question is therefore deferred. This is the third (and correct) framing: v1 only needs a JWT verifier. Original drafts preserved in git history.

## Question

Given [001](001-target-user-and-v1-scope.md) (v1 serves the author + two confirmed CRM-integrated customer companies, no standalone customers in scope) and [009](009-crm-integration-shape.md) (loose federation with 4tradesCRM via RS256/JWKS), what library and configuration handles JWT verification in voice-app's auth middleware for v1?

## Why this matters now

Every authenticated request to voice-app carries a JWT issued by 4tradesCRM. Voice-app must verify it (signature, expiration, issuer, audience), extract domain claims (`tenantId`, `role`, `isInternalStaff`), and attach them to the request context so RLS policies and pipeline code can use them. This is the entry point for every user-facing path. The library choice and the trusted-issuers configuration are small but consequential — they're the security perimeter.

This decision is intentionally narrow. Standalone sign-up is *not* in scope for v1; deferred to v1.x or v2 when an actual standalone customer materializes. At that point we'll pick a sign-up provider (Supabase Auth, Lucia, Auth.js, Clerk) with real evidence rather than speculation.

## Options

### Option A — `jose` + trusted-issuers config

Use the `jose` library (modern, well-maintained, panva-authored, industry-standard in 2026 for RS256/JWKS in Node). A `TRUSTED_ISSUERS` config maps issuer URL → JWKS endpoint. Middleware:

```ts
import { jwtVerify, createRemoteJWKSet } from 'jose';

const TRUSTED_ISSUERS = {
  'https://4trades.io': createRemoteJWKSet(new URL('https://4trades.io/.well-known/jwks.json')),
  // v2+: additional CRMs added here
};

export async function verifyAuthHeader(authHeader: string) {
  const token = authHeader.replace(/^Bearer\s+/i, '');
  const unverified = decodeProtectedHeader(token); // get kid for diagnostics
  const payload = decodeJwt(token); // get iss to look up issuer
  const jwks = TRUSTED_ISSUERS[payload.iss];
  if (!jwks) throw new UnauthorizedError('Unknown issuer');
  const { payload: verified } = await jwtVerify(token, jwks, {
    audience: 'voice-app',
    issuer: payload.iss,
  });
  return {
    userId: verified.sub,
    tenantId: verified.tenantId,
    role: verified.role,
    isInternalStaff: !!verified.isInternalStaff,
  };
}
```

**Steel-manned reasoning:** `jose` is the obviously correct choice for RS256 + JWKS verification in modern Node. Maintained, ESM-native, edge-runtime compatible (works on Vercel Edge / Cloudflare Workers if we ever deploy there). Built-in JWKS caching with TTL. Excellent TypeScript types. The trusted-issuers config is a few lines that grow naturally as we add more CRMs in v2. No dependencies, no vendor relationship, no per-MAU cost. This is plumbing — pick the standard library and move on.

**Priors / assumptions this rests on:**
- `jose` is the standard JWT library for Node in 2026 — confidence: **high**
- JWKS-based verification with the right options (audience, issuer, signature) is sufficient security perimeter for v1 — confidence: **high**
- Trusted-issuers config scales naturally to v2 multi-CRM federation — confidence: **high**
- Edge-runtime compatibility may matter eventually — confidence: **medium** (not v1 concern; nice-to-have)

### Option B — `jsonwebtoken` + manual JWKS fetch

The older, more familiar `jsonwebtoken` library (auth0-maintained). Mature, lots of examples, but CommonJS-first and less ergonomic for JWKS.

**Steel-manned reasoning:** Battle-tested. Many existing tutorials and Stack Overflow answers reference it. If you've written Node auth in the last decade, you've used it. Familiar API.

**Priors / assumptions this rests on:**
- `jsonwebtoken` familiarity is a real productivity gain over `jose` — confidence: **low** (`jose`'s API is straightforward; the modest learning cost is paid back the first time you need a feature `jsonwebtoken` lacks)
- CommonJS-first style is acceptable in 2026 — confidence: **medium-low** (Next.js 15 / Node 22 ecosystem is increasingly ESM-first; CJS adapters cause subtle issues)
- Manual JWKS fetching with `jwks-rsa` adds bounded complexity — confidence: **medium** (works but is more code than `jose`'s built-in)

### Option C — Custom verifier (pure crypto)

Roll our own RS256 verifier using Node's built-in `crypto` module. Maximum control, zero dependencies.

**Steel-manned reasoning:** No dependencies, full control, every byte we ship is ours. For paranoid security-sensitive systems, owning the verifier means owning the audit trail.

**Priors / assumptions this rests on:**
- Solo dev should own crypto code in 2026 — confidence: **very low** (auth bugs from rolling your own crypto are how systems get pwned; libraries exist for a reason)
- `jose` and `jsonwebtoken` have meaningful security risk we'd avoid — confidence: **very low** (both are extensively audited; rolling your own is *more* risky)
- Maintenance cost of a custom verifier is bounded — confidence: **very low** (every edge case in JWKS rotation, algorithm negotiation, token introspection is now ours to handle)

## Recommendation

**Option A — `jose` + trusted-issuers config.**

`jose` is the standard library for RS256 + JWKS verification in modern Node. Built-in JWKS caching, ESM-native, edge-compatible, excellent TypeScript types. The verifier is ~30 lines of middleware. Trusted-issuers config grows to multiple entries when we add more CRMs in v2. No vendor relationship, no per-MAU cost.

`jsonwebtoken` (B) works but is worse on every dimension that matters in 2026 — ESM, JWKS ergonomics, edge-runtime compatibility. Custom verifier (C) is a security anti-pattern we shouldn't entertain.

**Concrete v1 deliverables:**
1. `npm install jose` (zero other auth deps).
2. `lib/auth/verifier.ts` containing the verifier middleware (sketched above).
3. `TRUSTED_ISSUERS` config with one entry: `https://4trades.io` (URL TBD pending Q12 — hosting). Loaded from env vars; not hardcoded.
4. Next.js middleware (`middleware.ts`) that runs the verifier on protected routes and redirects to a "sign in via 4tradesCRM" page (basically a static page with a link back to the CRM) if no valid JWT is present.
5. Audit logging hook on every successful verification — records `userId`, `tenantId`, `iss`, `endpoint` to the audit trail (pairs with the super-admin audit pattern from 008).

**What's explicitly NOT in v1:**
- Standalone sign-up flow. No Supabase Auth, no Lucia, no Clerk. Deferred to v1.x or v2 when a real standalone customer materializes.
- OAuth provider integration (Google, GitHub, etc.). Deferred.
- MFA enrolment, password reset, email verification. Deferred. CRM-integrated users handle all of this through the CRM.
- WorkOS or other multi-CRM brokers. Deferred to v2 when we onboard a third-party CRM customer.

**Key reason it wins:** correct level of YAGNI. v1 only needs to verify JWTs from one issuer; we use the standard library and ship.

**Main risk we're accepting:** none significant. `jose` is the well-trodden path; the trusted-issuers config is trivial to extend; standalone sign-up will be a real decision when there's a real customer.

## Decision

**Option A — `jose` + trusted-issuers config.** Decided 2026-04-28.

`jose` is the v1 JWT verifier. Trusted-issuers config has one entry in v1 (`https://4trades.io`); designed to extend as more CRMs federate in v2+.

## Consequences

**Locks in:**
- `jose` is the only auth library in v1. No `jsonwebtoken`, no `passport`, no Auth.js.
- Auth middleware lives at `lib/auth/verifier.ts` (or equivalent). Next.js `middleware.ts` invokes it on protected routes.
- `TRUSTED_ISSUERS` config is loaded from env vars, not hardcoded. v1: one issuer (`https://4trades.io`).
- Audit logging on every successful verification (`userId`, `tenantId`, `iss`, `endpoint`) — pairs with the super-admin audit trail from [008](008-multi-tenancy-model.md).
- Voice-app does not include any sign-up flow in v1. Unauthenticated users hitting protected routes are redirected to a static "Sign in via 4tradesCRM" page that links back to the CRM.

**Creates / constrains follow-up decisions:**
- **Standalone sign-up** (deferred to v1.x or v2 — see deferred list in INDEX) will need to mint same-shape JWTs verifiable via the same `jose` middleware. The shape must match: `sub`, `tenantId`, `role`, `isInternalStaff`.
- **Q12 (hosting)** — `jose` works on every Node runtime including edge runtimes; doesn't constrain hosting choice.

**Risks accepted:**
- None significant. `jose` is the well-trodden path.

---

## Amendment 2026-04-28 — service-to-service API key authentication

**Trigger:** post-session review identified that the original 010 covered only end-user JWT verification, leaving service-to-service authentication implicit (and partly conflated with HMAC-signed webhooks from [020](020-integration-contracts.md)). This amendment formalizes a clean three-axis auth model.

### Three authentication paths in v1

The reframe to "voice-app is a backend service consumed by other apps" surfaces three distinct authentication scenarios. Each has its own mechanism.

| Scenario | Mechanism | Why |
|---|---|---|
| **End-user identity** — an internal-staff user in `apps/super-admin/` calls voice-app's admin APIs | RS256 JWT verified via `jose` against `TRUSTED_ISSUERS` (4tradesCRM JWKS in v1) | The user is identified; `tenantId`/`role`/`isInternalStaff` claims drive RLS and authorization decisions per [008](008-multi-tenancy-model.md). |
| **Service-to-service** — 4tradesCRM's backend or the marketing app's backend calls voice-app's API endpoints (e.g., `/api/internal/projects/sync` per [021](021-project-entity-model.md), `/api/admin/usage-metrics` per [025](025-billing.md), or any non-webhook integration call) | Per-app API key sent in `X-Voice-App-Service-Key` header; voice-app validates against a `service_api_keys` table | No end user is involved — it's a backend pushing data on behalf of *all its tenants* (or admin-scoped operations). API keys are the idiomatic mechanism, not user JWTs. |
| **Inbound webhooks** — consuming app's backend POSTs `verdict.captured` to voice-app per [020](020-integration-contracts.md) | HMAC-SHA256 signature with per-destination `signing_secret` | Already specified in [020](020-integration-contracts.md). Webhooks aren't authenticated calls — they're authenticated *messages*. Different shape from API auth. |

### `service_api_keys` table

```
service_api_keys/
  id (uuid PK)
  consuming_app_name (text)        — '4tradesCRM' | 'marketing-app' | future
  key_hash (text)                  — bcrypt'd; never store the plaintext key
  scopes (text[])                  — e.g., ['projects.sync', 'usage.read', 'admin.tenant.read']
  tenant_scope (text)              — 'all' for app-level keys, or specific tenant_id for tenant-scoped (rare)
  created_at, last_used_at, revoked_at
```

Keys are issued via `apps/super-admin/` admin UI (only `isInternalStaff` users can mint/rotate). Plaintext shown once at creation; afterward only the hash is stored.

### Key distinctions from 020's HMAC webhook auth

- **API keys** authenticate *the caller* (the CRM backend) for ongoing API access. Long-lived (months); rotated explicitly.
- **HMAC signing secrets** authenticate *individual webhook messages* (proving "this POST really came from voice-app and wasn't tampered with in transit"). Per-destination secret. Same vehicle, different role from API keys.

A consuming app uses *both*: an API key for outbound API calls *to* voice-app, and an HMAC signing secret for inbound webhooks *from* voice-app (per 020). They're not redundant.

### Verifier middleware update

The auth middleware in `lib/auth/verifier.ts` becomes:

```ts
export async function authenticateRequest(req): Promise<AuthContext> {
  const auth = req.headers.get('authorization');
  const serviceKey = req.headers.get('x-voice-app-service-key');

  if (auth?.startsWith('Bearer ')) {
    // End-user JWT path — existing logic
    return verifyJwtAndExtractUser(auth.slice(7));
  }

  if (serviceKey) {
    // Service-to-service path
    return verifyServiceKey(serviceKey);
  }

  throw new UnauthorizedError('No authentication provided');
}
```

Returns a discriminated-union `AuthContext`:
- `{ kind: 'user', userId, tenantId, role, isInternalStaff }` from JWT
- `{ kind: 'service', appName, scopes }` from API key (no `tenantId` — service-level keys typically operate across tenants; route handlers enforce per-call tenant scoping based on request body)

Route handlers receive the typed context and guard accordingly. Admin endpoints accept `kind: 'user'` with `isInternalStaff: true` *or* `kind: 'service'` with the appropriate scope.

### Consequences (additional)

**Locks in:**
- `service_api_keys` table with bcrypt'd keys, scopes, optional tenant scoping.
- `lib/auth/verifier.ts` returns a discriminated-union `AuthContext` (`'user' | 'service'`).
- API key issuance / rotation UI lives in `apps/super-admin/` (internal-staff-only).
- Three distinct auth paths in production: end-user JWT, service-to-service API key, HMAC-signed webhook (per [020](020-integration-contracts.md)).

**Risks accepted:**
- API key rotation requires coordination with consuming apps. Mitigation: support a brief overlap window where both old and new keys validate; consuming apps update during the rotation window. Same pattern as 020's HMAC secret rotation.
- Service-level keys (`tenant_scope: 'all'`) are powerful — a leak would compromise all tenants. Mitigation: scopes restrict damage (e.g., a `projects.sync`-only key can't read transcripts); audit log every key use; rotate proactively at any sign of compromise.
