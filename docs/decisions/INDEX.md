# Decision Index

Running list of architecture and product decisions. Each entry is a self-contained doc capturing the question, options, reasoning, priors, recommendation, and final choice.

## Format

See [000-template.md](000-template.md).

## Decisions

| #   | Title | Status | Date |
|-----|-------|--------|------|
| 000 | Template | template | 2026-04-28 |
| 001 | [Target user and v1 scope](001-target-user-and-v1-scope.md) | accepted | 2026-04-28 |
| 002 | [Learning model and feedback architecture](002-learning-model-and-feedback-architecture.md) | accepted | 2026-04-28 |
| 003 | [Primary user surface](003-primary-user-surface.md) | accepted (substantively amended 2026-04-28: voice-app has zero UI; consuming-app-canonical review; verdicts via inbound webhooks) | 2026-04-28 |
| 004 | [Language and runtime](004-language-and-runtime.md) | accepted | 2026-04-28 |
| 005 | [Backend framework](005-backend-framework.md) | accepted, **open for re-evaluation** before serious build (flagged 2026-04-28: Next.js choice was made when voice-app had a UI; post-reframe, NestJS or Hono may be more idiomatic) | 2026-04-28 |
| 006 | [Workflow / job engine](006-workflow-engine.md) | accepted | 2026-04-28 |
| 007 | [Primary database and vector store](007-primary-database-and-vector-store.md) | accepted | 2026-04-28 |
| 008 | [Multi-tenancy model](008-multi-tenancy-model.md) | accepted (amended 2026-04-28 to mirror 4tradesCRM `isInternalStaff` pattern) | 2026-04-28 |
| 009 | [CRM integration shape and federation model](009-crm-integration-shape.md) | accepted (generalized 2026-04-28 to consuming-app pattern; 4tradesCRM and marketing app are v1 consumers) | 2026-04-28 |
| 010 | [Auth verifier (v1)](010-auth-provider.md) | accepted (amended 2026-04-28 to add service-to-service API keys alongside JWT federation; HMAC for webhooks per 020 unchanged) | 2026-04-28 |
| 011 | [Hosting and deployment](011-hosting-and-deployment.md) | accepted (amended 2026-04-28: migration trigger documented; Edge Runtime for hot webhooks) | 2026-04-28 |
| 012 | [Email vendor (inbound + outbound)](012-email-vendor.md) | accepted (outbound scope amended 2026-04-28: system-to-system alerts only; user-facing notifications now in consuming apps) | 2026-04-28 |
| 013 | [Transcript source adapter interface](013-transcript-source-adapter.md) | accepted | 2026-04-28 |
| 014 | [LLM provider strategy](014-llm-provider-strategy.md) | accepted | 2026-04-28 |
| 015 | [Pipeline definition format](015-pipeline-definition-format.md) | accepted (amended 2026-04-28: outputs gain `webhookContract` ref + `projectId` field) | 2026-04-28 |
| 016 | [Agent and tool architecture](016-agent-and-tool-architecture.md) | accepted | 2026-04-28 |
| 017 | [Pipeline dispatch](017-pipeline-dispatch.md) | accepted | 2026-04-28 |
| 018 | [Memory and retrieval strategy](018-memory-and-retrieval-strategy.md) | accepted | 2026-04-28 |
| 019 | [Repo structure](019-repo-structure.md) | accepted (Option B' — monorepo with `apps/voice-app` + `apps/super-admin` + `packages/shared` + `packages/auth`) | 2026-04-28 |
| 020 | [Integration contracts (consuming-app webhooks)](020-integration-contracts.md) | accepted | 2026-04-28 |
| 021 | [Project entity model and identification](021-project-entity-model.md) | accepted | 2026-04-28 |
| 022 | [Observability stack](022-observability-stack.md) | accepted | 2026-04-28 |
| 023 | [Secrets management](023-secrets-management.md) | accepted | 2026-04-28 |
| 024 | [CI/CD](024-cicd.md) | accepted | 2026-04-28 |
| 025 | [Billing — when and how](025-billing.md) | accepted | 2026-04-28 |
| 026 | [Compliance posture (PII, retention, security)](026-compliance-posture.md) | accepted | 2026-04-28 |

## Planning queue

Questions to work through, in roughly the order they should be resolved (later questions often depend on earlier ones):

1. ~~**Target user & v1 scope**~~ — resolved by [001](001-target-user-and-v1-scope.md): author-only, single deep north-star pipeline.
2. ~~**Learning model and feedback architecture**~~ — resolved by [002](002-learning-model-and-feedback-architecture.md): in-context learning + structured data collection in v1; fine-tuning deferred to v2.
3. ~~**Primary user surface**~~ — resolved by [003](003-primary-user-surface.md): per-output-type routing (default `review_required: true`), dashboard-canonical, native targets as downstream delivery, email notifications.
4. ~~**Language / runtime**~~ — resolved by [004](004-language-and-runtime.md): TypeScript on Node.
5. ~~**Backend framework**~~ — resolved by [005](005-backend-framework.md): Next.js with App Router. **Flagged 2026-04-28 as open for re-evaluation** before serious build starts: the original choice assumed voice-app had a dashboard, which the [003](003-primary-user-surface.md) reframe removed. NestJS or Hono may be more idiomatic for a pure backend service. Re-eval criteria documented in 005.
6. ~~**Workflow / job engine**~~ — resolved by [006](006-workflow-engine.md): Inngest (hosted; self-host as escape hatch).
7. ~~**Primary database**~~ — resolved by [007](007-primary-database-and-vector-store.md): Supabase (managed Postgres), with `RetrievalStore` abstraction for retrieval calls.
8. ~~**Vector store**~~ — resolved by [007](007-primary-database-and-vector-store.md): pgvector inside Supabase Postgres, HNSW index. Migration trigger documented (>10M vectors AND latency SLO breach).
9. ~~**Multi-tenancy model**~~ — resolved by [008](008-multi-tenancy-model.md): Postgres RLS with `tenant_id` columns. Super-admin pattern amended 2026-04-28 to mirror 4tradesCRM's existing `isInternalStaff` flag + impersonation endpoint, with audit logging added (CRM doesn't have it; voice-app does).
10. ~~**CRM integration shape and federation model**~~ — resolved by [009](009-crm-integration-shape.md): loose federation (own subdomain, RS256/JWKS-verified JWT pass-through, REST API integration). 4tradesCRM-side work tracked separately (HS256→RS256 migration, JWKS endpoint, one-time-code SSO entry point, REST API audit).
11. ~~**Auth verifier (v1)**~~ — resolved by [010](010-auth-provider.md): three auth paths in v1 — (a) end-user JWT verified via `jose` + JWKS (4tradesCRM-issued tokens for super-admin users), (b) **service-to-service API keys** in `service_api_keys` table (consuming-app backends calling voice-app's APIs; per-app, scoped, bcrypt'd) (added 2026-04-28 amendment), (c) HMAC-SHA256 signed webhooks per [020](020-integration-contracts.md) (already covered).
12. ~~**Hosting / deployment**~~ — resolved by [011](011-hosting-and-deployment.md): Vercel (4tradesCRM also on Vercel — single-vendor consolidation).
13. ~~**Email vendor (inbound + outbound)**~~ — resolved by [012](012-email-vendor.md): Resend (inbound parse webhook + outbound transactional via React Email). Migration trigger to Postmark documented if deliverability degrades.
14. ~~**Transcript source adapter interface**~~ — resolved by [013](013-transcript-source-adapter.md): thin source-specific Inngest handlers emit `transcript.normalized`; shared `dedupe-and-persist` step writes to `transcripts` table; emits `transcript.ingested` for routing. **V1 ingests text only** — Plaud transcribes on-device; audio ingestion is explicitly out of scope with a documented future-extension pattern.
15. ~~**LLM provider strategy**~~ — resolved by [014](014-llm-provider-strategy.md): Vercel AI SDK + OpenAI primary + Anthropic fallback (error-based). Cost-based fallback deferred.
16. ~~**Pipeline definition format**~~ — resolved by [015](015-pipeline-definition-format.md): TS code with `definePipeline()` + structured step helpers (`step.review`, `step.callCRM`, future `step.invokeAgent`). Engineer-authored, full type safety, metadata validated via Zod at load time.
17. ~~**Agent and tool architecture**~~ — resolved by [016](016-agent-and-tool-architecture.md): three-layer architecture (pipelines / agents / tools). TS-defined agents and tools, Zod-typed I/O, tenant-scoped tools by construction, `step.invokeAgent` wrapping Vercel AI SDK's tool-calling, hard execution limits, audit-logged. SKILL.md export deferred to v2.
18. ~~**Pipeline dispatch (originally "Keyword routing strategy")**~~ — resolved by [017](017-pipeline-dispatch.md): dispatcher-based architecture (centralized `routeToPipeline`); v1 trivial classifier (one pipeline). **Expected evolution: rules+embedding fast-path → LLM classifier on ambiguous cases → multi-pipeline fan-out → agent-as-dispatcher.** LLM-based dispatch is the explicit expected endstate.
19. ~~**Memory / retrieval strategy**~~ — resolved by [018](018-memory-and-retrieval-strategy.md): single `memory_items` table with `kind` discriminator (transcript / verdict / output / pipeline_run_summary); whole-item embeddings via OpenAI `text-embedding-3-small`; HNSW index; recency-weighted rerank optional; explicit `recallMemory` tool for LLM context insertion; citation-anchored output.
20. ~~**Repo structure**~~ — resolved by [019](019-repo-structure.md): monorepo with `apps/voice-app/` (service) + `apps/super-admin/` (ops UI) + `packages/shared/` + `packages/auth/`. pnpm + Turborepo. Two Vercel projects from the same repo.
21. ~~**Integration contracts (consuming-app webhooks)**~~ *(NEW — added 2026-04-28 after the headless-backend reframe)* — resolved by [020](020-integration-contracts.md): `pipeline.output.proposed` outbound webhook + `verdict.captured` inbound webhook; per-output-kind Zod-typed artifact schemas in `packages/shared/contracts/`; tenant→destination mapping table; HMAC-SHA256 signing both directions; retry + dead-letter via Inngest `step.fetch`.
22. ~~**Project entity model and identification**~~ *(NEW — added 2026-04-28 after the marketing-app + multi-project clarification)* — resolved by [021](021-project-entity-model.md): projects synced from consuming apps (4tradesCRM owns canonical project list); `identifyProject` Inngest step pre-dispatch; embedding fast-path with thresholds + LLM fallback for ambiguous cases (per Doug's explicit override). `projectId` flows through pipelines and outputs.
23. ~~**Observability stack**~~ — resolved by [022](022-observability-stack.md): OpenTelemetry as the instrumentation layer + Sentry as the v1 backend (errors + traces). Vercel Analytics for HTTP metrics; Vercel native logs in v1; Inngest run inspector for pipeline observability; super-admin views over audit tables for domain-specific debugging. Migration triggers documented for Honeycomb/Grafana (traces) and Axiom (logs) at v2+ scale.
24. ~~**Secrets management**~~ — resolved by [023](023-secrets-management.md): Vercel env vars (per-environment scoped, encrypted at rest); per-tenant runtime secrets envelope-encrypted in DB. Migration trigger to Doppler documented.
25. ~~**CI/CD**~~ — resolved by [024](024-cicd.md): GitHub Actions, Turborepo-orchestrated builds. Pipeline includes lint, type-check, unit tests, RLS isolation suite, webhook contract validation, build, Sentry source-map upload (main only). Vercel handles deploy after CI passes via its GitHub integration.
26. ~~**When to wire in billing**~~ — resolved by [025](025-billing.md): no voice-app-level billing in v1; v2 bills through consuming apps' existing subscription models; voice-app exposes per-tenant usage metrics via admin APIs. v3+ standalone billing deferred.
27. ~~**Compliance posture**~~ — resolved by [026](026-compliance-posture.md): tiered retention (90-day raw transcripts and outputs; 1-year verdicts and audit logs; indefinite scrubbed pipeline-run summaries); HTTPS + HMAC + RLS + envelope encryption; PII redaction in observability via OTel SpanProcessor + lint rules; tenant-offboarding cascade; SOC 2 / GDPR / HIPAA certifications deferred until customer demand. Note: original framing "audio is PII" no longer applies — v1 ingests text only per [013](013-transcript-source-adapter.md).

### Open before serious build

- **[005] Backend framework re-evaluation** — Next.js currently; NestJS and Hono are realistic alternatives for the pure backend service. Resolution path: hello-world the same Plaud-ingestion-to-CRM-output flow in each candidate; pick the one that produces the cleanest service-shaped code. ~1 day of throwaway work. Resolve before substantial implementation.

### Deferred (v1.x / v2)

- **Eval harness build-out** (v1.x, post-launch when corpus is stable) — added by [002](002-learning-model-and-feedback-architecture.md).
- **Fine-tuning mechanism** (v2) — added by [002](002-learning-model-and-feedback-architecture.md). Gated on (a) corpus volume threshold, (b) eval harness in place, (c) demonstrated regression in in-context-only baseline.
- **Standalone sign-up flow** (v1.x or v2 when first standalone customer materializes) — pick a sign-up provider (Supabase Auth, Lucia, Auth.js, Clerk) at that point with real evidence. Will need to mint same-shape JWTs as the CRM federation path (see [010](010-auth-provider.md)).
- **Multi-CRM federation broker** (v2 when ~3+ third-party CRMs need to federate) — evaluate WorkOS as a single broker vs. direct per-CRM federation. Trusted-issuers config in [010](010-auth-provider.md) is already designed to extend; this is about whether to consolidate brokerage.

This list will be refined as decisions are made — some questions will spawn sub-questions, others may be merged or deferred.
