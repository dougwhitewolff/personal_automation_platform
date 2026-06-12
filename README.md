# Personal Automation Platform

A shared automation service for apps that need AI-assisted ingestion, classification, workflow execution, and tool actions.

The first concrete consumer is the CRM via the Plaud voice-capture integration. Other expected consumers include the Mason trades marketing generator and future internal apps or tools.

## Status

Fresh build. This checkout is currently documentation-first; there is no current `backend/`, `frontend/`, Prisma schema, or service implementation code in `main`.

The active direction is not a standalone CRM repo and not a single Plaud feature repo. It is a service layer that can sit behind multiple products.

Accepted stack: TypeScript + Node.js + NestJS, Postgres, Prisma, and Inngest for initial durable workflows. See [docs/decisions/002-service-stack.md](docs/decisions/002-service-stack.md).

Accepted repo structure: single NestJS service package at the repository root for now, API-first and monorepo-ready later. See [docs/decisions/003-repo-structure.md](docs/decisions/003-repo-structure.md).

Accepted multi-tenancy model: app-layer tenant enforcement first, with an RLS-ready schema. See [docs/decisions/004-multi-tenancy-model.md](docs/decisions/004-multi-tenancy-model.md).

Accepted auth/service access model: service-issued API keys first, human auth deferred until the service owns a real UI. See [docs/decisions/005-auth-service-access.md](docs/decisions/005-auth-service-access.md).

## Service Role

This service should own cross-app automation primitives:

- ingestion from external sources such as Plaud emails, webhooks, uploads, forms, or app-originated requests
- normalization of captured content into structured events
- AI classification, extraction, summarization, and drafting
- durable workflow execution and retries
- review queues and confidence-gated human approval
- audit trails for what was received, proposed, committed, edited, or discarded
- tenant-aware configuration and feature flags
- app adapters that let client products receive results without hardcoding their domain logic into the service core

The CRM, Mason, and future apps should consume the service through explicit APIs/events rather than sharing database internals.

## First Use Case: Plaud To CRM

Plaud-to-CRM is the first implementation target:

- Plaud sends auto-transcription emails to a dedicated email account.
- The service detects Plaud-origin emails and parses summary/transcript content.
- Slice 1 routes every capture to review for manual confirmation.
- Slice 2 adds AI classification, contact/lead resolution, confidence routing, and optional auto-commit.
- The CRM receives confirmed actions such as log interaction, create lead, update lead fields, create task, or associate with existing lead.
- Raw transcript text is not stored as a CRM record.

## Other Expected Consumers

Mason trades marketing generator:

- submit business/customer/project context
- generate marketing copy, ads, landing-page sections, emails, or campaign variants
- route drafts through review/approval
- keep reusable prompt and brand context outside the Mason UI

Future apps and tools:

- send work requests into the service
- receive structured results, status updates, and audit records
- opt into shared review, workflow, and AI orchestration primitives

## Legacy Code

The previous Python implementation was wiped from `main`. It is preserved at:

- Git tag: `legacy-python-v1`
- Git branch: `legacy-python-v1`

To inspect the legacy code: `git checkout legacy-python-v1`.

## Local database (PostgreSQL)

- **Docker:** `docker compose up -d` — Postgres on port **5434**, database `personal_automation` (see [docker-compose.yml](docker-compose.yml)).
- **Env:** set `DATABASE_URL` in `.env` (see [.env.example](.env.example)), then `npx prisma migrate deploy` and optionally `npm run prisma:seed`.
- **GUI:** [docs/DATABASE_GUI.md](docs/DATABASE_GUI.md) — Prisma Studio and other tools.

## Documentation

- [docs/DEV_HANDOFF_PRD.md](docs/DEV_HANDOFF_PRD.md) - concise developer handoff PRD and current source of truth
- [docs/PRD.md](docs/PRD.md) - current repo-local product/service summary
- [docs/VISION.md](docs/VISION.md) - service vision and first use cases
- [docs/decisions/002-service-stack.md](docs/decisions/002-service-stack.md) - accepted stack decision
- [docs/decisions/003-repo-structure.md](docs/decisions/003-repo-structure.md) - accepted repo structure decision
- [docs/decisions/004-multi-tenancy-model.md](docs/decisions/004-multi-tenancy-model.md) - accepted multi-tenancy decision
- [docs/decisions/005-auth-service-access.md](docs/decisions/005-auth-service-access.md) - accepted auth/service access decision
