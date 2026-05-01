---
number: 022
title: Observability stack
status: accepted
date: 2026-04-28
---

# 022 — Observability stack

**Status:** accepted
**Date:** 2026-04-28

## Question

What handles errors, traces, metrics, and logs across `apps/voice-app` and `apps/super-admin`? Voice-app already has substantial structurally-captured observability via audit tables (`agent_runs`, `tool_calls`, `routing_audit`, `super_admin_audit`, `project_identification_runs`, `webhook_dead_letters` per [008](008-multi-tenancy-model.md)/[016](016-agent-and-tool-architecture.md)/[017](017-pipeline-dispatch.md)/[020](020-integration-contracts.md)) and Inngest's run inspector for pipeline-level workflows. The remaining gap: errors, latency traces, runtime metrics, and centralized logs.

## Why this matters now

The instrumentation layer is hard to change after-the-fact — every span-emission point in the codebase is touched. Picking the wrong shape means re-instrumenting weeks of work later. Affects Q24 (CI/CD — observability tools often integrate with deploy pipelines), Q27 (compliance — log retention is part of the data-handling story), and the super-admin UX (telemetry surfaces drive the debug views).

## Decision

**OpenTelemetry (OTel) as the instrumentation layer + Sentry as the v1 backend.**

Decided 2026-04-28, after pressure-testing a "Sentry SDK direct" recommendation. The honest balance favored OTel: ~4–8 extra setup hours buys vendor-neutrality at the instrumentation layer, which means future backend swaps (Honeycomb for traces, Grafana for self-hosted, etc.) are config changes rather than re-instrumentation projects.

### Stack

| Concern | v1 implementation | Future evolution |
|---|---|---|
| **Instrumentation** | OpenTelemetry via `instrumentation.ts` in each Next.js app | Stays — vendor-neutral by design |
| **Errors** | Sentry (free tier; ingests OTel) | Stays unless Sentry pricing changes |
| **Traces** | Sentry (v1) | Honeycomb / Grafana Cloud at v2+ when latency analysis becomes a daily driver |
| **Request metrics** | Vercel Analytics (free, native) + custom OTel metrics to Sentry | Add Prometheus/Grafana when SLO dashboards become real concerns |
| **Logs** | Vercel native logs (searchable in dashboard) | Add Axiom (or Logflare/Better Stack) when Vercel-log search becomes a bottleneck |
| **Pipeline observability** | Inngest run inspector (built-in, already there) | Stays |
| **Audit-data queries** | Postgres tables, queried from super-admin | Stays — audit data is intentionally in our DB, not in observability vendor |

### v1 deliverables

1. **`apps/voice-app/instrumentation.ts`** — OTel SDK init. Auto-instrumentation for: HTTP server, fetch (outbound), Postgres (`pg`), Vercel AI SDK, Inngest function context propagation. Sentry exporter for errors and traces.
2. **`apps/super-admin/instrumentation.ts`** — same OTel stack.
3. **`packages/observability/`** — shared utilities:
   - OTel resource attributes (service name, deployment env, version)
   - `tenantContext.ts` — helper that propagates `tenantId` into the active span via `OTEL_RESOURCE_ATTRIBUTES` or per-span attributes; downstream queries by tenant become possible
   - `pipelineRunContext.ts` — correlates Inngest run IDs with traces; clicking a trace in Sentry/Honeycomb leads to the corresponding Inngest run inspector view
4. **Sentry project (free tier)** for both apps. OTel exporter target. Source maps uploaded automatically via Vercel-Sentry integration.
5. **Vercel Analytics enabled** on both apps.
6. **Super-admin views** over audit tables (`agent_runs`, `tool_calls`, `routing_audit`, `super_admin_audit`, `project_identification_runs`, `webhook_dead_letters`) with search/filter — these are the domain-specific observability surfaces that complement the generic OTel/Sentry views.

### Migration triggers (documented now to avoid reactive decisions later)

- **Add Honeycomb (or Grafana Cloud) for traces** when:
  - p95-latency analysis becomes a daily driver (multiple debugging sessions per week)
  - Sentry's trace UI feels insufficient for query needs ("show me all spans where tenant X had >500ms p95 over the last week")
- **Add Axiom (or similar) for logs** when:
  - "Where did this transcript end up?" queries take >2 minutes regularly
  - Log volume from a single Inngest run exceeds Vercel's view limits
  - Cross-app correlation in logs becomes a frequent debug pattern
- **Add Datadog (or similar full-platform)** if/when ops scope outgrows the per-tool stitching — generally only at 1,000+ tenants

## Consequences

**Locks in:**
- OpenTelemetry as the instrumentation layer for the lifetime of the codebase. Backend swaps don't require re-instrumentation.
- Sentry as the v1 errors+traces backend. Free-tier coverage is sufficient.
- `packages/observability/` shared utilities for tenant + pipeline-run context propagation.
- Vercel Analytics for native HTTP-level metrics.
- Inngest run inspector for pipeline-level observability (already there).
- Super-admin's domain-specific audit views complement (rather than duplicate) generic OTel telemetry.

**Creates / constrains follow-up decisions:**
- **Q24 (CI/CD)** — Sentry-Vercel integration uploads source maps on deploy; CI builds need to support this.
- **Q27 (compliance)** — log retention policy applies; PII in spans (transcripts, drafts) needs scrubbing — OTel SpanProcessor with PII redaction; documented in compliance work.

**Risks accepted:**
- OTel auto-instrumentation occasionally breaks across Next.js/runtime upgrades. Mitigation: pin OTel SDK + auto-instrumentation library versions; upgrade deliberately; community support is strong in 2026.
- Sentry free tier has volume limits (5K errors/mo, 10K traces/mo as of 2026). Mitigation: at v1 scale fine; upgrade to paid Sentry or migrate trace backend if we hit ceilings.
- Tenant context propagation requires care — a missed attribute on one span loses the breadcrumb. Mitigation: `tenantContext.ts` helper called via middleware on every request; lint rule warns on Inngest functions that don't establish context.