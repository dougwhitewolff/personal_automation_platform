# Service Consumers and Interaction Contract

**Product:** Personal Automation Platform / Shared Automation Service
**Audience:** Engineering
**Status:** Draft for developer handoff
**Date:** 2026-05-17
**Companion docs:** [DEV_HANDOFF_PRD.md](DEV_HANDOFF_PRD.md) (source of truth), [VISION.md](VISION.md), [decisions/](decisions/)

## 1. Purpose

This document answers one question: **who consumes the shared automation service, and what are the interactions across that boundary.**

It exists so each consumer team knows exactly what to build against the service, and so the service team knows what surfaces it must expose. It does not redefine the internal pipeline (watcher, dispatcher, agents) — see the PRD for that.

## 2. Three roles — do not conflate them

The word "consumer" gets overloaded. There are three distinct roles, and an app can play more than one.

| Role | Definition | Examples |
|---|---|---|
| **Source** | Feeds raw signal/captures **into** the service. Does not query it back. | Plaud email, inbound webhooks/forms, Teams bot transcripts |
| **Consumer** | An app that **integrates over the service API/events**: submits requests, receives results, queries state. Owns its own domain records and UI. | 4tradesCRM, Trades Marketing app, Field Capture app |
| **Destination** | An external system the service **delivers to** via an output adapter. The service calls it; it never calls the service. | Google Workspace, Microsoft 365, Jobber, ServiceTitan |

Apps that wear two hats:

- **Field Capture app** is a Source (submits captures) *and* a Consumer (queries capture status).
- **4tradesCRM** is a Consumer *and* a dependency the Resolver reads from for entity resolution.
- **Tier-2 destinations** (CRM, Marketing app) are Consumers that also receive outbound adapter calls.

## 3. The feedback boundary rule — read this first

**This service does not own user-facing feedback or status UX. It owns state and events. Each consumer repo owns the experience of showing that state to its users.**

- The service **exposes** queryable state — capture status, review items, audit trail, delivery outcomes — and **emits** lifecycle events.
- Each consumer **renders** that state into its own UI. The Field Capture app shows the tech "your capture landed / is stuck / needs a re-shoot." The CRM shows the reviewer the queue and its backlog.
- The service ships at most a minimal internal/admin surface. It does not ship consumer-facing feedback screens.

So wherever this document says a consumer "receives status," it means the service makes status **available** (via query API or event). Building the screen that shows it is the consumer team's job, in the consumer's repo.

## 4. Interaction mechanisms

There are four ways anything crosses the service boundary.

1. **Inbound submission** — a source or consumer sends captures or automation requests to the service (or the service pulls, e.g. a mailbox).
2. **Query API (pull)** — a consumer reads tenant-scoped state: capture status, reviews, audit, deliveries.
3. **Events / webhooks (push)** — the service emits lifecycle events; a consumer subscribes to update its own UI without polling.
4. **Outbound adapter calls** — the service calls a consumer's or destination's write API to deliver a confirmed outcome.

Auth: every consumer is provisioned with a `ClientApp`, a `ServiceApiKey` (hashed, scoped, rotatable — PRD §12), and `Integration` rows. Events/webhooks should be signed so consumers can verify origin.

Push vs poll is a per-consumer decision the developer should make explicitly — see §10.

## 5. Consumers

### 5.1 4tradesCRM

Primary consumer and system of record for customer / lead / job identity.

| Direction | Interaction |
|---|---|
| CRM → service | Confirm or reject review items (`POST /reviews/:id/confirm`, `/reject`) |
| CRM → service | Query capture status, review queue, audit trail, delivery outcomes |
| CRM → service | *(Later)* submit app-originated automation requests (e.g. enrich a lead) |
| service → CRM | **CRM adapter delivery calls:** create lead, log interaction, create task, update lead fields, attach capture to existing project |
| service → CRM | **Entity-resolution lookups:** the Resolver reads CRM contacts/leads/projects to match a capture to an existing record (CRM is the identity authority) |
| service → CRM | Lifecycle events (`review.created`, `delivery.succeeded/failed`) so the CRM keeps its views current |

**Feedback ownership:** the CRM renders the review queue and capture status for CRM users.
**CRM must expose:** a read API for entity resolution, and a write API matching the agreed adapter contract (PRD §8.5 — currently `MockCrmAdapter`, contract still open per §15.3).

### 5.2 Trades Marketing / SEO Automation

Second consumer. Owns marketing content, assets, and approvals.

| Direction | Interaction |
|---|---|
| Marketing → service | Provide brand / trade / campaign context used for drafting |
| Marketing → service | Confirm consent gates (testimonial use — UC-5) |
| Marketing → service | Approve, reject, or revise generated drafts |
| Marketing → service | Query status of marketing-bound captures and drafts |
| service → Marketing | **Marketing adapter delivery:** content drafts, testimonial drafts, project/SEO page data, review-request triggers |
| service → Marketing | Gated deliveries held until consent is confirmed |
| service → Marketing | Lifecycle events |

**Feedback ownership:** the Marketing app renders the draft review/approval UX.

### 5.3 Field Capture App ("Assistant in your pocket")

The capture client and the status surface for the field user. Post-Slice-1, but the contract should be designed for it now.

| Direction | Interaction |
|---|---|
| App → service | Submit captures: voice transcript, photos, location, structured form fields, plus capture metadata for multi-modal correlation |
| App → service | Submit self-directed intents (tasks, actions — UC-3) |
| App → service | Query capture status by capture ID or by actor/day |
| service → App | Capture acknowledgment (capture ID, received) |
| service → App | Status transitions: parsed / segmented / in-review / delivered / needs-attention |
| service → App | Completeness feedback ("missing drip-edge photo") so the tech can re-capture |
| service → App | Lifecycle events |

**Feedback ownership:** the Field Capture app owns the screen that tells the tech their capture landed, is stuck, or needs a re-shoot. The service supplies the capture-status API and events; the app builds the UX. This is the capture-side acknowledgment loop — it lives in the app repo, not in the service.

> **Slice 1 note:** today captures arrive via Plaud email ingestion (a Source, see §6). The Field Capture app as a first-class Consumer comes later; it is documented here so the service contract is designed for it from the start.

## 6. Sources (not consumers)

These feed captures in. They do not integrate with the service API and do not query state.

- **Plaud** — transcript emails delivered to a dedicated mailbox; the service ingests via the mailbox ingestion adapter (PRD §8.1). The Slice-1 source.
- **4t-teams-bot (Meeting Companion)** — meeting transcripts as an ingestion source; a potential future Consumer if it ever surfaces status to users.
- **Inbound webhooks / web forms** — future capture sources.

## 7. Destinations (not consumers)

The service delivers to these via output adapters; they never call the service. Full breakdown in the tier inventory.

| Tier | Destinations |
|---|---|
| 0 | Service-rendered documents (PDF/DOCX), outbound email |
| 1 | Google Workspace, Microsoft 365 |
| 2 | The consumer apps above (CRM, Marketing) — Tier-2 destinations are also Consumers |
| 3 | Jobber, ServiceTitan, Housecall Pro, HubSpot, Salesforce, etc. |
| 4 | Closed platforms via email/CSV/webhook bridge/browser automation/manual handoff |

## 8. Consumer interaction matrix

| Consumer | Submits in | Receives via adapter | Queries / subscribes to | Owns feedback UX for |
|---|---|---|---|---|
| 4tradesCRM | Review confirm/reject; later automation requests | Lead/interaction/task/project actions | Capture status, review queue, audit, deliveries; lifecycle events | Review queue, capture status (CRM users) |
| Trades Marketing | Brand context, consent confirmations, draft approvals | Content/testimonial drafts, project pages, review-requests | Draft + capture status; lifecycle events | Draft review/approval (marketing users) |
| Field Capture app | Captures (voice/photos/location/form), self-directed intents | Status + completeness feedback | Capture status by ID/actor/day; lifecycle events | Capture acknowledgment + needs-attention (field techs) |

## 9. Service surfaces consumers depend on

The service must expose, and consumers will build against:

- **Ingestion** — capture submission endpoint(s) for app-originated captures; mailbox/webhook adapters for sources.
- **Review API** — `GET /reviews`, `GET /reviews/:id`, `POST /reviews/:id/confirm`, `POST /reviews/:id/reject` (PRD §8.4).
- **Query API** — capture status (`GET /captures/:id`, `GET /captures?actor=&date=`), audit (`GET /audit`), delivery outcomes (`GET /deliveries`). All tenant-scoped, API-key auth.
- **Events** — a published set of lifecycle events: `capture.received`, `capture.status.changed`, `capture.needs_attention`, `review.created`, `review.resolved`, `delivery.attempted`, `delivery.succeeded`, `delivery.failed`.

Each consumer must expose, for the service to call:

- **CRM** — an entity-resolution read API and a write adapter API.
- **Marketing** — a context API and a draft-approval API.
- **Field Capture app** — either a signed webhook receiver, or it polls the Query API.

## 10. Open items for the developer

1. **CRM adapter contract** — exact endpoints/events for delivery and for entity resolution (PRD §15.3, open).
2. **Push vs poll, per consumer** — decide events/webhooks vs Query API polling for each consumer; webhooks need a signing scheme.
3. **Capture-status state machine** — define the shared status values (`received → parsed → segmented → in-review → delivered` / `needs-attention` / `discarded`) so all consumers render the same vocabulary.
4. **Field Capture submission contract** — the multi-modal capture shape (voice + photos + metadata) and the correlation window for inputs that arrive separately.
5. **Auth provisioning** — one `ClientApp` + `ServiceApiKey` per consumer; confirm scopes per consumer.
