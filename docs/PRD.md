# Product Requirements Document

> **Superseded.** The current source of truth for engineering is [DEV_HANDOFF_PRD.md](DEV_HANDOFF_PRD.md). This file is kept for context only; do not implement against it.

**Status:** Active service-level direction. Plaud-to-CRM is the first concrete feature slice to implement against this service.

## Product Frame

Build a shared automation service that serves multiple client apps:

- CRM
- Mason trades marketing generator
- future internal tools and product surfaces

The service provides reusable automation infrastructure rather than embedding one-off AI workflows inside each app.

Accepted implementation stack: TypeScript + Node.js + NestJS, Postgres, Prisma, and Inngest for initial durable workflows. See [decisions/002-service-stack.md](decisions/002-service-stack.md).

Accepted repo structure: single NestJS service package at the repository root for now, API-first and monorepo-ready later. See [decisions/003-repo-structure.md](decisions/003-repo-structure.md).

Accepted multi-tenancy model: app-layer tenant enforcement first, with an RLS-ready schema. See [decisions/004-multi-tenancy-model.md](decisions/004-multi-tenancy-model.md).

Accepted auth/service access model: service-issued API keys first, human auth deferred until the service owns a real UI. See [decisions/005-auth-service-access.md](decisions/005-auth-service-access.md).

## Core Responsibilities

The service owns:

- ingestion adapters for emails, app requests, webhooks, uploads, and future external sources
- content parsing and normalization
- AI classification, extraction, summarization, drafting, and routing
- durable background workflows with retries and idempotency
- tenant-aware configuration, feature flags, and per-app settings
- review queues for low-confidence or human-required actions
- audit/event history for all automation work
- app adapters that translate generic automation outcomes into CRM, Mason, or future-app actions

## Client Boundaries

Client apps should call the service through APIs or events. They should not depend on the service database directly.

The service should not hardcode one consumer's entire domain model into its core. Consumer-specific behavior belongs in adapters:

- CRM adapter: contacts, leads, interactions, tasks, activity logs
- Mason adapter: brand context, campaign assets, generated copy, approvals
- future adapters: app-specific action execution and status callbacks

## First Feature: Plaud To CRM

Plaud-to-CRM is the first implementation slice.

Build a Plaud integration that:

- receives Plaud transcript emails delivered to a dedicated email account
- detects Plaud-origin emails in that mailbox
- treats the receiving inbox owner as the recorder of record
- parses summary and transcript content from the email body
- creates a capture audit event for every processed email
- routes Slice 1 captures to a review queue with manual record creation
- later adds AI classification, contact/lead resolution, confidence routing, and optional auto-commit
- returns confirmed actions to the CRM adapter
- avoids storing raw transcript text as a CRM record

## Service Boundaries

- email ingestion belongs to this service as an ingestion adapter or integration worker
- Plaud processing belongs to this service as a workflow
- Plaud review should be exposed through service APIs and may be rendered by the CRM or a minimal service-owned surface
- CRM record creation should happen through a CRM adapter/API contract, not direct writes into CRM internals
- tenant settings need a service-owned shape, with app-specific config nested under app/integration keys

## Initial Build Plan

1. Scaffold the NestJS service application, Prisma/Postgres data layer, and Inngest runtime structure.
2. Define tenant, app, integration, capture event, review item, and workflow job primitives.
3. Implement Plaud email detection and parsing.
4. Implement review-only Plaud Slice 1.
5. Add the CRM adapter needed to create/log confirmed records.
6. Add AI classification and confidence routing in Slice 2.
7. Add Mason as the second consumer once the shared primitives are proven.

## Non-Goals For The First Slice

- A public SaaS signup flow
- Billing
- Full Mason implementation
- Direct Plaud API integration
- Autonomous CRM writes for new contacts
- Raw transcript storage as CRM notes
