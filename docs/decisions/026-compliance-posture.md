---
number: 026
title: Compliance posture (PII, retention, security)
status: accepted
date: 2026-04-28
---

# 026 — Compliance posture (PII, retention, security)

**Status:** accepted
**Date:** 2026-04-28

## Question

Voice-app handles sensitive data: voice transcripts (potentially containing health, financial, family, business-confidential content), per-tenant project data synced from CRMs, integration secrets, and audit logs. What's the v1 compliance posture? Specifically: data retention policy, encryption story, PII handling in observability, right-to-deletion, and which compliance frameworks (SOC2, GDPR, HIPAA) we plan for vs. defer.

## Why this matters now

Compliance decisions made too late are hard to retrofit — retention policies must be implemented in code; PII redaction must be in span processors before traces ship; right-to-deletion must cascade through every table. Made too early, they over-constrain a v1 product without a regulatory driver. The right v1 posture is "good security defaults; framework certification deferred until a customer asks."

The original queue framing mentioned "audio is PII" — but per [013](013-transcript-source-adapter.md), v1 does not ingest audio (Plaud transcribes on-device; emails forward text only). Audio retention is therefore not a v1 concern. Text transcripts are still PII and the dominant compliance surface.

## Decision

**Good security defaults from day one; compliance framework certification deferred until a customer asks.** Decided 2026-04-28.

### Data retention (tiered by sensitivity, decided 2026-04-28)

The original draft used "indefinite" retention for transcripts and verdicts. Doug pointed out that 90 days is the standard B2B retention, and indefinite was over-indexing on learning at the expense of privacy. The policy was revised to a **tiered retention by data type** that preserves the learning loop while respecting standard privacy expectations: raw input is short-retention; structured learning signal is longer; distilled summaries persist indefinitely (but are scrubbed at write-time).

| Data | Retention | Rationale |
|---|---|---|
| **Raw transcripts** (`memory_items` where `kind='transcript'`) | **90 days** | High PII risk — voice memos can contain anything. Standard B2B retention. Daily cleanup job purges items older than 90 days. |
| **Pipeline outputs** (`memory_items` where `kind='output'`) | **90 days** | Mid PII risk. Once delivered to a consuming app, the consuming app owns its own retention. We don't need duplicates. |
| **Verdicts** (`memory_items` where `kind='verdict'`) | **1 year** | Structured learning signal ("user accepted draft, edited X to Y"). Less sensitive than raw transcripts. The primary learning data. |
| **Pipeline-run summaries** (`memory_items` where `kind='pipeline_run_summary'`) | **Indefinite, but scrubbed at write-time** | Low PII risk *if written carefully*. Pipelines write these at completion as PII-minimized one-paragraph summaries that reference IDs, not quotes ("Drafted Q3 follow-up for contact `<contactId>` with revenue context" — not "Drafted a follow-up about Sarah's sick father..."). Lint rule flags summaries containing long strings or apparent names/emails. |
| **Audit logs** (`super_admin_audit`, `agent_runs`, `tool_calls`, `routing_audit`, `project_identification_runs`, `verdicts` table) | **1 year minimum** | Compliance + ops norm. Necessary for incident investigation. |
| **Dead-lettered webhooks** (`webhook_dead_letters` per [020](020-integration-contracts.md)) | **30 days** | Operational data; short retention is fine. |
| **Sentry traces / OTel data** | **90 days** (Sentry's free-tier default; matches the transcript policy) | PII redaction already enforced; 90 days aligns with everything else. |
| **Vercel logs** | **Per Vercel retention** (~3 days on Hobby; longer on Pro) | Operational; structurally never contains PII (lint rule); short retention is fine. |

**The pattern in plain English:** the actual things people said disappear in 90 days. What the system learned from how they reacted persists longer, but in scrubbed/structured form, not as raw quotes.

**Customer override (v2+):** a tenant can explicitly extend transcript retention beyond 90 days if their use case requires it — **opt-in to longer retention, not opt-out of the default**. Default stays at 90 days for new tenants.

**Right-to-deletion still works:** tenant offboarding cascades regardless of retention timer — all data deleted immediately on tenant deletion, not subject to the 90-day or 1-year clocks.

### Encryption

- **At rest**: Supabase Postgres encrypts at rest natively. Supabase Storage (audio if/when added; future scope) encrypts at rest. No additional encryption in v1.
- **Per-tenant runtime secrets** (HMAC signing per integration destination per [020](020-integration-contracts.md)): envelope-encrypted in DB using a master key from Vercel env per [023](023-secrets-management.md).
- **In transit**: HTTPS-only enforced everywhere. HMAC-SHA256 on integration webhooks. JWTs signed RS256 by 4tradesCRM and verified via JWKS per [010](010-auth-provider.md).
- **CSRF / XSS**: standard Next.js mitigations + CSP headers configured in `apps/super-admin/middleware.ts` (voice-app has no UI so no XSS concern beyond admin views).

### PII handling in observability

OTel SpanProcessor (per [022](022-observability-stack.md)) **redacts PII from spans before export**. Specifically:

- Transcript text — never in spans. `transcript.id` and length-only allowed.
- Verdict edited artifacts — never in spans. `outputId` and verdict type only.
- LLM prompts and responses — content redacted in production; full content in development. Tag-based: spans tagged `pii=true` are scrubbed by the production exporter.
- User identifiers (`userId`, `tenantId`) — allowed in spans (needed for debugging); never user names, emails, or contact info.

Sentry breadcrumbs follow the same redaction. Vercel logs include only structured data (no raw transcript text in `console.log`); a lint rule enforces this on `transcripts.text` field references in logging contexts.

### Right-to-deletion

Tenant deletion cascades through every multi-tenant table (transcripts, verdicts, outputs, memory_items, agent_runs, tool_calls, routing_audit, super_admin_audit, project_identification_runs, tenant_destinations, projects, webhook_dead_letters). RLS scoping in [008](008-multi-tenancy-model.md) makes this straightforward — every relevant table has `tenant_id`; `DELETE FROM <table> WHERE tenant_id = ?` purges everything. Foreign-key constraints + ON DELETE CASCADE enforce referential integrity.

A `tenant_offboarding` admin endpoint (in `apps/super-admin/`) executes the cascade after appropriate confirmation steps (typed tenant slug confirmation; 7-day soft-delete grace period; hard-delete after).

For v2+ when GDPR-style requests apply, a per-user (vs. per-tenant) deletion is also exposed: scrub identifiable fields while preserving aggregate corpus where lawful. Detailed pattern decided when first GDPR request arrives.

### Compliance frameworks

| Framework | v1 posture | Plan |
|---|---|---|
| **SOC 2** | Not certified | Begin Type 1 prep when first enterprise customer asks; ~6 months from kickoff to report. We're already implementing many SOC2 controls (RLS, audit logs, encryption at rest, access control) by virtue of architectural decisions. |
| **GDPR** | Compliant where applicable, not certified | If any tenant has EU end-users, design implications already accounted for: data minimization (PII redaction in observability), right-to-deletion (cascade), data residency (Supabase region selectable). Formal compliance review when first EU customer signs. |
| **HIPAA** | Out of scope | Voice memos may incidentally contain health info, but voice-app is not a HIPAA-covered service in v1. If a healthcare customer wants this, signing a BAA + implementing additional controls (encryption keys we control vs. Supabase-managed, longer audit retention) is a v3+ scoped effort. |
| **CCPA** | Compliant by virtue of GDPR alignment | No specific work needed in v1. |

### Documentation surfaces

- **Public privacy policy / terms** — owned by consuming apps in v1 (4tradesCRM and marketing app each have their own). Voice-app's data handling disclosed in their policies.
- **Internal data-handling spec** — `docs/COMPLIANCE.md` (separate doc, drafted post-v1-launch) documents what's stored, where, and for how long.
- **DPA / sub-processor disclosures** — when an enterprise customer asks; voice-app discloses Supabase (database, region), OpenAI (LLM), Anthropic (LLM fallback), Inngest (workflow engine), Vercel (hosting), Resend (email), Sentry (observability) as sub-processors.

## Consequences

**Locks in:**
- Indefinite retention for transcripts and corpus data in v1; configurable in v2.
- 30-day retention for dead-lettered webhooks.
- OTel SpanProcessor redacts PII before export; lint rule prevents raw `transcript.text` in logging contexts.
- HTTPS-only enforced; HMAC-SHA256 on all webhook integrations.
- Tenant-deletion cascade across all multi-tenant tables; soft-delete grace period.
- Per-tenant runtime secrets envelope-encrypted in DB.
- No SOC2/GDPR certification effort in v1. Architectural decisions already align with most controls — the gap to certification is process documentation, not code.

**Creates / constrains follow-up decisions:**
- **v2 work**: configurable per-tenant retention; tenant-offboarding admin flow; PII-redaction lint rules.
- **v2.x work**: GDPR-aligned per-user deletion patterns (when first EU customer signs).
- **v3+ work**: SOC2 Type 1 certification effort (when first enterprise customer asks); HIPAA BAA + controls (when first healthcare customer asks).

**Risks accepted:**
- 90-day transcript retention loses the "exact words" memory of long-ago interactions. Mitigation: pipeline-run summaries (scrubbed at write-time) preserve the structural memory indefinitely; verdicts (1-year) preserve the learning signal; the system's behavior degrades gracefully as raw transcripts age out rather than catastrophically.
- PII redaction in observability is a discipline, not an automatic guarantee. A new span tag missed in code review could leak PII. Mitigation: lint rule on logging contexts; PR review checklist for new spans; periodic audit (quarterly) of span content samples.
- Compliance frameworks not certified means we can't sell to enterprise customers who require them. Mitigation: deferred until customer demand justifies the cost; architectural decisions already align so the gap is bounded.
- Pipeline-run-summary scrubbing is a write-time discipline; a poorly-written summary could leak content. Mitigation: lint rule on summary writes flagging long strings, apparent names/emails, or quoted content; pattern documented for pipeline authors.

## Consequences

**Locks in:**
- Tiered retention policy as detailed above. Daily cleanup job purges expired items per kind.
- 90-day default for raw transcripts and pipeline outputs; 1-year for verdicts and audit logs; indefinite for scrubbed pipeline-run summaries.
- Pipeline-run-summary writes are PII-minimized at write-time; lint rule enforces this for `kind='pipeline_run_summary'` writes.
- OTel SpanProcessor redacts PII before export; lint rule prevents raw `transcript.text` in logging contexts.
- HTTPS-only enforced; HMAC-SHA256 on all webhook integrations.
- Tenant-deletion cascade across all multi-tenant tables (immediate, not subject to retention timers); 7-day soft-delete grace period.
- Per-tenant runtime secrets envelope-encrypted in DB.
- No SOC 2 / GDPR certification effort in v1. Architectural decisions already align with most controls — the gap to certification is process documentation, not code.
- v2+ adds per-tenant override to extend transcript retention beyond 90 days (opt-in only).

**Creates / constrains follow-up decisions:**
- **v2 work**: per-tenant retention override; tenant-offboarding admin flow; daily retention cleanup job (Inngest scheduled function); summary-scrubbing lint rule.
- **v2.x work**: GDPR-aligned per-user deletion patterns (when first EU customer signs).
- **v3+ work**: SOC 2 Type 1 certification (when first enterprise customer asks); HIPAA BAA + extra controls (when first healthcare customer asks).
