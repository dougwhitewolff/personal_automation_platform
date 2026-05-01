---
number: 023
title: Secrets management
status: accepted
date: 2026-04-28
---

# 023 — Secrets management

**Status:** accepted
**Date:** 2026-04-28

## Question

Where do secrets live (Supabase service role key, Inngest signing key, OpenAI/Anthropic API keys, Resend API key, Sentry DSN, JWT signing keys, HMAC secrets per integration destination per [020](020-integration-contracts.md), 4tradesCRM JWKS URL)? How do they reach `apps/voice-app` and `apps/super-admin` at runtime, and how are they rotated?

## Why this matters now

Secrets touch every integration we've decided on. Picking the wrong tool means either (a) over-engineering operational scope for a solo dev or (b) spreading credentials across so many places that rotation becomes painful when it's needed. Should be cheap to set up and not require a new vendor relationship.

## Options

### Option A — Vercel environment variables (native)

Vercel's per-project env vars, segmented by environment (production / preview / development). Set via Vercel UI or `vercel env` CLI. Both apps in the monorepo get their own scoped env vars per project.

**Steel-man.** Zero new tools, zero new bills, zero new auth surfaces. Vercel's env-var UI handles per-environment scoping (different secrets for production vs. preview). CLI access for scripted updates. Encrypted at rest. For solo dev with one deployment platform and minimal rotation needs, this is the path of least resistance and doesn't introduce operational tax that doesn't pay off until real team scale.

**Priors:**
- Solo dev productivity gain from "no extra vendor" is real — confidence: **high**
- Vercel env-var UX is sufficient for v1 needs — confidence: **high**
- Rotation is rare in v1 (a few times per year for credential hygiene) — confidence: **medium-high**
- Migration to Doppler/1Password later is bounded — confidence: **high** (well-precedented)

### Option B — Doppler (third-party secrets manager)

Doppler stores secrets in its dashboard; integrations push them to Vercel automatically. Adds a centralized vault, audit log, easier rotation workflow.

**Steel-manned reasoning:** Centralized secrets across multiple platforms (Vercel for hosting, but also any local dev, CI, future workers). Better rotation UX — change in Doppler, propagates everywhere. Audit log of who accessed what. For teams that grow past solo dev, the canonical answer.

**Priors:**
- Doppler's UX is meaningfully better than Vercel's for v1 needs — confidence: **low** (real but small at solo-dev scale)
- The audit-log benefit matters in v1 — confidence: **low** (one author; theoretical)
- Adding a vendor is bounded operational cost — confidence: **medium** (free tier exists; new login/auth to manage)

### Option C — 1Password Connect / HashiCorp Vault / cloud-native (AWS Secrets Manager, etc.)

Heavyweight enterprise-ish options.

**Steel-manned reasoning:** Maximum security posture; deep audit trails; secret-rotation automation; service-account integrations. The right call for regulated industries or large teams.

**Priors:**
- Required for v1 compliance posture — confidence: **very low** (no enterprise customers asking; no regulatory driver)
- Solo dev productivity acceptable — confidence: **very low** (real ops surface)

## Recommendation

**Option A — Vercel environment variables.**

For solo dev with one hosting platform and a small set of integration secrets, Vercel's native env-var management is the right shape. No new vendor, no new bill, no new login. Per-environment scoping (production vs. preview vs. development) handles the multi-environment story. CLI access (`vercel env pull`) supports local development with the same secrets.

**v1 deliverables:**
1. All secrets configured in Vercel for both `apps/voice-app` and `apps/super-admin` projects, segmented by environment.
2. `.env.example` files in each app's directory listing required keys (without values) so contributors know what to set.
3. Local development uses `vercel env pull .env.local` to sync secrets from Vercel — never commit `.env.local`.
4. HMAC signing secrets per integration destination (per [020](020-integration-contracts.md)) are stored as environment variables in voice-app, named like `WEBHOOK_SIGNING_SECRET_<destination_id>`. Encrypted at rest by Vercel.
5. Per-tenant secrets that vary at runtime (e.g., per-tenant webhook signing secrets stored in `tenant_destinations` per [020](020-integration-contracts.md)) are encrypted in the database using a master encryption key stored in Vercel env. The master key encrypts/decrypts row-level secrets — standard envelope encryption.

**Migration trigger documented:** add Doppler when (a) team grows past 2–3 contributors and secret-access audit becomes a real need, (b) secret rotation becomes frequent enough that Vercel UI clicking is a bottleneck, or (c) we add another deployment surface beyond Vercel that needs the same secrets.

**Key reason it wins:** zero operational scope add; Vercel handles encryption, rotation, and per-environment scoping natively.

**Main risk we're accepting:** Vercel env-var UI doesn't have an audit trail of *who* accessed *which secret*. Mitigation: solo dev; not a v1 concern.

## Decision

**Option A — Vercel environment variables.** Decided 2026-04-28.

## Consequences

**Locks in:**
- Vercel env-var UI / CLI as the v1 secrets surface for both `apps/voice-app` and `apps/super-admin`.
- `.env.example` files in each app listing required keys.
- Per-tenant runtime secrets (HMAC signing per destination per [020](020-integration-contracts.md)) stored in `tenant_destinations` table, encrypted with a master encryption key from Vercel env (envelope encryption).
- `vercel env pull .env.local` for local-dev secret sync.

**Migration trigger documented:** add Doppler when team >2–3 contributors, rotation becomes frequent, or a deployment surface beyond Vercel needs the same secrets.

**Risks accepted:**
- No audit trail of who accessed which secret. Solo-dev scope; revisit when team grows.
