# Product Requirements Document

**Product:** Personal Automation Platform / Shared Automation Service  
**First feature:** Plaud-to-CRM  
**Status:** Current source of truth for dev handoff  
**Date:** 2026-05-04  
**Owner:** Product owner  
**Audience:** Engineering

## 1. Executive Summary

Build a fresh shared automation service that can serve multiple consuming applications. The first concrete feature is Plaud-to-CRM: Plaud sends transcript emails to a dedicated email account, this service ingests and normalizes them, creates auditable capture records, routes them through review, and sends confirmed outcomes to the CRM.

This is not a standalone CRM feature and not a continuation of the old Python prototype. It is a new service layer for reusable automation primitives that CRM, the Mason trades marketing generator, and future apps can consume through explicit APIs or events.

## 2. Problem

Automation work is currently at risk of becoming scattered across individual applications. If Plaud transcript processing is built directly into the CRM, and Mason marketing generation is built separately inside Mason, each app will need its own ingestion, parsing, workflow, review, audit, retry, and AI orchestration logic.

That would create duplicated infrastructure, weaker auditability, and a harder path to future automation features.

We need one shared service that owns the reusable automation layer while allowing each consuming app to keep ownership of its own domain records and UI.

## 3. Product Direction

The service should own cross-app automation primitives:

- ingestion from external sources such as Plaud emails, webhooks, uploads, forms, and app-originated requests
- normalization of captured content into structured events
- parsing, classification, extraction, summarization, and drafting
- durable workflow execution with retries and idempotency
- review queues and confidence-gated human approval
- audit trails for what was received, proposed, reviewed, committed, edited, or discarded
- tenant-aware configuration and feature flags
- app adapters that let CRM, Mason, and future apps receive results without sharing service database internals

Client apps should consume the service through APIs/events. They should not read or write the service database directly.

## 4. Users And Stakeholders

### Primary Slice 1 Users

- Field/user who records interactions with Plaud.
- CRM user or operator who reviews and confirms proposed CRM actions.
- Developer/operator who needs traceability, retries, and debuggability.

### Consuming Apps

- CRM: first consumer, receives confirmed actions from Plaud captures.
- Mason trades marketing generator: later consumer, uses shared automation/review/drafting primitives.
- Future internal tools or product surfaces.

## 5. Goals

- Create a clean NestJS service foundation.
- Model tenant-aware automation primitives from the first migration.
- Implement Plaud-to-CRM as the first review-first workflow.
- Keep CRM/Mason-specific behavior in adapters rather than in the service core.
- Preserve auditability for each meaningful state transition.
- Make duplicate Plaud emails/idempotent retries safe.
- Avoid storing raw transcript text as CRM records.
- Leave room for later AI classification, contact/lead resolution, confidence routing, and Mason workflows.

## 6. Non-Goals For Slice 1

- Public SaaS signup.
- Billing.
- Full Mason implementation.
- Direct Plaud API integration.
- Autonomous CRM writes for new contacts.
- Standalone service user auth.
- Full service admin UI unless needed for implementation.
- Postgres RLS enforcement in Slice 1.
- Fully autonomous AI classification or auto-commit.

## 7. First Feature: Plaud To CRM

### 7.1 User Story

As a field user, I record a site visit or customer interaction on Plaud. Plaud emails the transcript to a dedicated email account. The automation service detects the Plaud email, parses the useful content, creates a capture record, routes it to review, and after human confirmation sends the appropriate action to the CRM.

### 7.2 Slice 1 Flow

1. Plaud sends a transcript email to a dedicated email account. For dev purposes, use `doug@4trades.ai` unless/until a separate mailbox is provisioned.
2. The service ingests the email through the chosen mailbox ingestion implementation.
3. The service detects whether the email is Plaud-originated.
4. The service parses summary/transcript content from the email body.
5. The service resolves tenant/app/actor context by looking up an `Integration` row that maps the receiving mailbox address to `(tenantId, appId)`. The inbox owner is treated as the actor when no other actor is provided.
6. The service creates a tenant-scoped capture event.
7. The service creates an auditable review item.
8. A human reviews and confirms the intended CRM action.
9. The service sends the confirmed action to the CRM adapter/API.
10. The service records audit events throughout the flow.

Slice 1 routes every Plaud capture to review. It does not auto-commit.

### 7.3 Plaud Email Shape

> **TODO before parser implementation.** Document the actual shape of a Plaud transcript email so the parser can be implemented and unit-tested:
>
> - From-address pattern(s) used by Plaud (e.g., `noreply@plaud.ai`).
> - Subject pattern(s) (any stable prefix/suffix that signals a Plaud capture).
> - Body format: HTML, plaintext, or both. Where the summary section starts/ends. Where the full transcript starts/ends. Any structural markers (headings, separators) the parser can anchor on.
> - Save 2-3 redacted real Plaud emails as fixtures under `docs/fixtures/plaud/` so the parser tests can run against ground truth. The product owner will pass a real Plaud email to Faiyaz when needed for dev purposes.
>
> Until this section is filled in, section 8.2 (Plaud detection and parsing) should be scaffolded behind fixtures/stubs rather than treated as final parser logic.

### 7.4 Later Slice 2 Flow

Add AI-assisted classification, extraction, contact/lead resolution, confidence scoring, and optional auto-commit for high-confidence/low-risk actions.

Potential CRM actions:

- log interaction
- create lead
- update lead fields
- create task
- associate capture with existing lead/contact/project

## 8. Functional Requirements

### 8.1 Email Ingestion

- The system must ingest Plaud transcript emails delivered to a dedicated email account.
- For dev purposes, Plaud emails can be sent to `doug@4trades.ai` unless/until a separate mailbox is provisioned.
- The mailbox access mechanism can be chosen during implementation. Candidates: IMAP polling, Microsoft Graph subscription, inbound-email webhook (Postmark/SendGrid/Mailgun), or a forwarding rule into a webhook. This should be hidden behind an email ingestion adapter so the downstream Plaud workflow does not depend on the mechanism.
- Regardless of mechanism, the ingestion layer normalizes incoming email into a single internal shape `{messageId, from, to, subject, headers, bodyText, bodyHtml, receivedAt, rawSourceRef}` and hands it to the Plaud workflow.
- The ingestion layer must preserve enough email metadata for dedupe, tracing, and audit.

### 8.2 Plaud Detection And Parsing

- The system must identify Plaud-originated emails.
- The parser must extract useful summary/transcript content from the email body.
- Parser behavior should be implemented as a pure, well-tested module.
- Parser failures must create auditable failed/needs-attention states rather than silently dropping input.

### 8.3 Capture Events

- Every processed Plaud email must create or resolve a tenant-scoped capture event.
- Capture events must be idempotent for duplicate emails/retries.
- Capture events must preserve source metadata, processing status, and audit references.
- Idempotency key for Slice 1 is the RFC 5322 `Message-ID` of the source email, scoped per `tenantId` (unique index on `(tenantId, sourceMessageId)`). If `Message-ID` is missing, fall back to a SHA-256 of `(fromAddress, toAddress, normalizedSubject, normalizedBody)`.

### 8.4 Review

- Slice 1 must create a review item for every valid Plaud capture.
- Review items must support manual confirmation before CRM action.
- For Slice 1 the review surface is service-owned REST endpoints: `GET /reviews`, `GET /reviews/:id`, `POST /reviews/:id/confirm`, `POST /reviews/:id/reject`. The CRM or a future admin UI consumes them. (See section 15.2.)
- Review records must preserve who/what confirmed, edited, rejected, or discarded an item.

### 8.5 CRM Adapter

- The service must send confirmed actions to the CRM through an explicit adapter/API contract.
- The service must not write directly into CRM internals unless both applications intentionally share a backend later.
- CRM delivery attempts and outcomes must be auditable.
- The first adapter can be stubbed/mocked until the real CRM contract is agreed.

### 8.6 Audit

- The system must record meaningful state transitions:
  - email received
  - Plaud detected or rejected
  - parsing succeeded or failed
  - capture created
  - review item created
  - review confirmed/rejected/edited
  - CRM delivery attempted
  - CRM delivery succeeded/failed
- Audit records must be tenant-scoped.

### 8.7 Tenant And App Context

- Requests and workflow events must carry explicit tenant/app/actor context where known.
- Tenant-owned data must include `tenantId`.
- CRM and Mason remain the authority for human identity during Slice 1.

## 9. Non-Functional Requirements

- **Durability:** workflows should survive retries/failures through Inngest.
- **Idempotency:** duplicate email deliveries or retries must not create duplicate CRM actions.
- **Tenant isolation:** critical reads/writes must be tenant-scoped.
- **Observability:** failures should be traceable through logs/audit records/workflow run IDs.
- **Security:** API keys must be hashed, scoped, rotatable, and auditable.
- **Extensibility:** Plaud email ingestion should be one source adapter; future Plaud API support should not require rewriting downstream workflows.
- **Testability:** parser, tenant isolation, idempotency, and review flow require automated tests.

## 10. Accepted Technical Direction

Use:

- TypeScript + Node.js
- NestJS
- Postgres
- Prisma
- Inngest for durable workflows
- Service-issued API keys for trusted app/service callers

Start as a single NestJS service package at the repository root:

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

Design APIs and DTOs cleanly enough that generated clients or a monorepo structure can be added later, but do not start with monorepo ceremony.

Accepted decision docs:

- `docs/decisions/002-service-stack.md`
- `docs/decisions/003-repo-structure.md`
- `docs/decisions/004-multi-tenancy-model.md`
- `docs/decisions/005-auth-service-access.md`

## 11. Data Model Direction

Every tenant-owned model should include `tenantId`. The schema should be RLS-ready, but tenant isolation is enforced in application code for Slice 1.

Initial models should likely include:

- `Tenant`
- `ClientApp`
- `ServiceApiKey`
- `Integration`
- `CaptureEvent`
- `ReviewItem`
- `AuditEvent`
- `WorkflowRun` - a thin reference table linking Inngest run IDs to capture/review rows. Inngest owns durable workflow state; do not model a full job queue.
- CRM adapter delivery/outcome records as needed

Implementation requirements:

- service methods receive explicit tenant/app/actor context
- indexes include `tenantId` where tenant-scoped lookup/filtering is expected
- API keys are stored hashed, not plaintext
- API keys are tenant/app-bound, scoped, rotatable, and auditable
- cross-tenant isolation tests should cover critical services

## 12. Auth And Context

For Slice 1, use service-issued API keys.

Requests from trusted client apps/workers should carry:

- `tenantId`
- `appId`
- `actorUserId` when known
- optional `actorEmail`
- scopes/permissions as needed

Actor context is trusted only when it comes from an authenticated app credential. Future app-issued JWT trust or a human auth provider can be added when the service owns a real admin/review UI.

## 13. Suggested First Build Pass

1. Scaffold NestJS service at repo root. Use **Zod** for validation and **Vitest** for tests (recommended; either Zod/class-validator and Jest/Vitest is acceptable, but pick during scaffold and stick with it).
2. Add Prisma/Postgres setup and initial tenant-aware schema.
3. Add API key authentication guard and request context. For Slice 1, API keys are issued via a `prisma db seed` script and a `pnpm key:create` CLI script; no admin endpoint required yet.
4. Add core modules: tenants, apps, integrations, captures, reviews, workflows, audit.
5. Add Inngest runtime structure and a first Plaud capture workflow.
6. Implement Plaud email detection/parsing as a pure, well-tested module.
7. Implement review-only Plaud flow. Slice 1 review surface is REST endpoints on the service (`GET /reviews`, `GET /reviews/:id`, `POST /reviews/:id/confirm`, `POST /reviews/:id/reject`); the CRM or a future admin UI consumes them.
8. Implement CRM adapter interface in TypeScript first, ship a `MockCrmAdapter` that records calls in `AuditEvent`, then wire real CRM endpoints later.
9. Add tests for parser behavior, tenant isolation, idempotency, and review flow.

### 13.1 Bootstrap

For local development the seed script must create:

- one `Tenant` (the operator)
- one `ClientApp` representing the CRM
- one `ServiceApiKey` bound to that tenant+app
- one `Integration` row mapping the dedicated Plaud mailbox address to `(tenantId, appId)`

This avoids any chicken-and-egg problem where the service has no callers on first boot.

## 14. Acceptance Criteria For Slice 1

- A Plaud email payload can be submitted to the service in dev/test.
- The service identifies it as a Plaud capture.
- The service parses useful summary/transcript content.
- The service creates a tenant-scoped capture event.
- The service records an audit trail.
- The service creates a review item instead of committing automatically.
- A confirmed review action calls the CRM adapter.
- Duplicate email/input handling is idempotent.
- Critical reads/writes are tenant-scoped.
- Tests cover Plaud parsing, review item creation, idempotency, and cross-tenant isolation for core records.

## 15. Open Decisions

### 15.1 Needed before final parser behavior

1. **Plaud email format spec + sample fixtures:** real example Plaud emails (PII scrubbed) saved under `docs/fixtures/plaud/`, plus section 7.3 describing From-address pattern, Subject pattern, and where summary vs. transcript live in the body. The product owner will pass a real Plaud email to Faiyaz when needed for dev purposes.
2. **Mailbox ingestion implementation:** how the service accesses the dedicated Plaud transcript email account. Default dev mailbox is `doug@4trades.ai`; the mechanism can be selected during implementation and should be isolated behind the ingestion adapter.

### 15.2 Resolvable during scaffold (defaults set, dev may override)

3. **Validation library:** **Zod** (recommended). Override only with reason.
4. **Testing library:** **Vitest** (recommended).
5. **Review surface for Slice 1:** **REST endpoints on the service** (recommended). CRM or a future admin UI consumes them.
6. **API key issuance flow for Slice 1:** **`prisma db seed` + a small `pnpm key:create` CLI script** (recommended). No admin endpoint yet.

### 15.3 Genuinely deferable

7. **CRM adapter contract:** exact endpoints/events. Stub with `MockCrmAdapter` first; finalize during Phase 3.
8. **Deployment target:** not blocking until the service needs to leave localhost.
9. **Retention policy:** raw emails/transcripts, summaries, review items, audit records.
10. **LLM provider strategy for Slice 2:** OpenAI only, Anthropic only, or multi-provider abstraction.
11. **Operational baseline:** observability, secrets management, CI/CD.

## 16. Risks

- **Mailbox ingestion uncertainty:** implementation depends on the email provider/account setup. Mitigation: use `doug@4trades.ai` for dev purposes if needed and keep the adapter boundary clean so the mailbox mechanism can change later.
- **CRM contract uncertainty:** confirmed actions need a clear target API. Mitigation: build a stub adapter first and finalize the CRM contract early.
- **Review surface ambiguity:** review could live in CRM or the service. Mitigation: expose service endpoints that can support either path.
- **Tenant leakage risk:** app-layer enforcement depends on discipline. Mitigation: tenant-scoped helpers and cross-tenant tests.
- **Overbuilding risk:** this is a shared service, but Slice 1 should stay conservative. Mitigation: scaffold only what Plaud-to-CRM needs while preserving module boundaries.

## 17. Rollout Plan

### Phase 1: Foundation

- Scaffold service.
- Add database schema and migrations.
- Add API key auth/context.
- Add audit and workflow foundation.

**Done when:** the service boots, an API key authenticates a request, and an `AuditEvent` row can be written and read tenant-scoped.

### Phase 2: Plaud Review Slice

- Add mailbox ingestion path.
- Add Plaud parser.
- Add capture and review flow.
- Add CRM adapter stub.
- Add tests.

**Done when:** a fixture Plaud email submitted to the ingestion endpoint produces a `CaptureEvent`, a `ReviewItem`, full `AuditEvent` trail, and a confirmed review calls `MockCrmAdapter` exactly once (idempotent on retry). All Slice 1 acceptance criteria in section 14 pass.

### Phase 3: CRM Integration

- Finalize CRM adapter contract.
- Wire confirmed review actions to CRM.
- Add delivery audit and retry behavior.

**Done when:** confirmed reviews produce real CRM records via the live adapter, with delivery outcomes recorded in audit and retried on transient failure.

### Phase 4: Intelligence

- Add AI classification/extraction.
- Add contact/lead resolution.
- Add confidence routing and optional auto-commit where safe.

### Phase 5: Second Consumer

- Add Mason workflows after shared primitives are proven.

## 18. Existing Repo State

This repository is currently documentation-first. The old Python implementation was removed from `main` and preserved on the `legacy-python-v1` branch/tag. Current implementation code should be built fresh.
