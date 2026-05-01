---
number: 020
title: Integration contracts (consuming-app webhooks)
status: accepted
date: 2026-04-28
---

# 020 — Integration contracts (consuming-app webhooks)

**Status:** accepted
**Date:** 2026-04-28

## Question

After the headless-backend reframe (per [003](003-primary-user-surface.md) amendment), voice-app delivers proposed outputs to consuming apps via outbound webhooks; consuming apps return verdicts via inbound webhooks. What are the contracts? Specifically:

1. **Outbound webhook shape** — `pipeline.output.proposed` event sent to consuming apps. Per output kind.
2. **Inbound webhook shape** — `verdict.captured` event received from consuming apps.
3. **Tenant → destination mapping** — how a tenant configures which consuming app receives which output kind.
4. **Authentication** — HMAC signing pattern for both directions.
5. **Reliability** — retry policy, dead-letter handling, replay capability.

## Why this matters now

These webhooks are the *integration boundary* — the documented surface that 4tradesCRM, the marketing app, and any future third-party CRM consumer integrates against. Voice-app's internal architecture can change freely; the webhook contracts cannot, without coordinated work in every consuming app. This decision is "stable contract" territory.

## Decision

### 1. Outbound: `pipeline.output.proposed` webhook

Voice-app POSTs to the consuming app's configured URL when a pipeline produces an output marked `reviewRequired: true` (or directly delivers if `reviewRequired: false`). Body:

```ts
type OutputProposedEvent = {
  eventType: 'pipeline.output.proposed';
  eventId: string;            // UUID; idempotency key for the consuming app
  occurredAt: string;          // ISO8601

  tenantId: string;
  pipelineId: string;
  pipelineRunId: string;       // Inngest run reference for traceability
  outputId: string;            // unique per (pipelineRunId, outputs[].id)
  outputKind: string;          // 'crm.lead' | 'marketing.interaction-log' | etc.

  projectId: string | null;    // per [021](021-project-entity-model.md); null if no project applies or identification was inconclusive

  reviewRequired: boolean;     // mirrors pipeline declaration; consuming app may still show it for visibility even when false
  artifact: unknown;           // the actual output, shape determined by outputKind's contract (see kind registry)

  citations?: Array<{ memoryItemId: string; kind: string; excerpt: string }>; // per [018](018-memory-and-retrieval-strategy.md), if any

  context: {
    transcriptId: string;
    capturedAt: string;
    sourceTranscriptExcerpt?: string; // short snippet for consuming app to display alongside the artifact
  };
};
```

The `artifact` shape varies per `outputKind`. Voice-app maintains a **kind registry** in `packages/shared/contracts/output-kinds.ts` defining each kind's Zod schema. Consuming apps subscribe with the kinds they handle and validate against the same schemas (consumed via the shared package or generated TypeScript types if the consuming app is in a different repo).

### 2. Inbound: `verdict.captured` webhook

Consuming apps POST to voice-app's `/api/verdict/captured` (Edge Runtime per [011](011-hosting-and-deployment.md)) when a user takes action. Body:

```ts
type VerdictCapturedEvent = {
  eventType: 'verdict.captured';
  eventId: string;             // UUID; idempotency key
  occurredAt: string;

  tenantId: string;
  outputId: string;            // matches the OutputProposedEvent
  pipelineRunId: string;       // for Inngest correlation

  verdict: 'accepted' | 'edited' | 'rejected';
  editedArtifact?: unknown;    // present only when verdict === 'edited'; same shape as outputKind's artifact schema
  reason?: string;             // optional user-supplied reason
  reviewerUserId: string;      // who took the action
  reviewedAt: string;
};
```

Voice-app's webhook handler:
1. Verifies the HMAC signature (next section)
2. Confirms `outputId` exists and matches `tenantId`
3. Persists the verdict to the `verdicts` table (per [002](002-learning-model-and-feedback-architecture.md))
4. Emits an Inngest event `verdict.captured` matching the paused pipeline step (per [006](006-workflow-engine.md))
5. Adds a `verdict` item to the memory corpus (per [018](018-memory-and-retrieval-strategy.md))
6. Returns 200; processing happens async via Inngest

### 3. Tenant → destination mapping

A `tenant_destinations` table:

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | |
| `tenant_id` | uuid | RLS-scoped per [008](008-multi-tenancy-model.md) |
| `output_kind_pattern` | text | exact (`crm.lead`) or wildcard (`crm.*`, `marketing.*`); first-match wins |
| `webhook_url` | text | the consuming app's `pipeline.output.proposed` receiver |
| `signing_secret` | text | per-destination HMAC secret (encrypted at rest) |
| `enabled` | boolean | for graceful disable |
| `created_at` | timestamptz | |

A tenant in both 4tradesCRM and the marketing app has at least two rows: one for `crm.*` pointing at CRM, one for `marketing.*` pointing at the marketing app. Output dispatch looks up matching destinations and POSTs to each.

Multiple destinations matching the same output is supported (e.g., `crm.lead` could fan out to two systems). Order of POSTs is not guaranteed; each is independent.

### 4. Authentication: HMAC-SHA256, both directions

Both directions sign the JSON request body with the destination's `signing_secret` and include the signature in `X-Voice-App-Signature` (or `X-Consumer-App-Signature` inbound). The receiving side recomputes and compares. Standard pattern.

Headers:
- `X-Voice-App-Signature: sha256=<hex>` — HMAC of the raw body bytes
- `X-Voice-App-Timestamp: <unix-seconds>` — included in HMAC input to prevent replay; rejected if older than 5 minutes
- `X-Voice-App-Event-Id: <uuid>` — duplicate of body's `eventId` for fast deduplication at edge

Per-destination `signing_secret` allows revocation/rotation without affecting other destinations.

### 5. Reliability: retries, dead-lettering, replay

**Outbound delivery:**
- Wrapped in an Inngest step (`step.fetch` with retry policy)
- Retry on 5xx, 408, 429, network errors. No retry on 4xx (consuming app rejected the event for a reason it considers fatal).
- Backoff: exponential, max 5 retries, total ceiling ~10 minutes
- After ceiling: dead-letter to the `webhook_dead_letters` table; super-admin UI surfaces these for manual investigation/replay
- Replay endpoint: super-admin can re-emit any dead-lettered event (creates a new `eventId` for downstream idempotency)

**Inbound delivery:**
- Voice-app responds 200 fast (just signature verification + queue the work via Inngest)
- Idempotency by `eventId` — duplicate events are recorded and ignored
- If processing fails downstream (Inngest function errors), Inngest's own retry semantics apply

## Consequences

**Locks in:**
- `packages/shared/contracts/` is the canonical source of truth for outbound and inbound webhook shapes.
- Per-output-kind Zod schemas in `packages/shared/contracts/output-kinds/` — adding a new kind = adding one schema file plus a registry entry.
- `tenant_destinations` table with the schema above. RLS-scoped.
- `webhook_dead_letters` table for outbound failures; surfaced in super-admin UI.
- HMAC-SHA256 signing standard for both directions; per-destination secrets.
- Replay endpoint in super-admin for dead-lettered events.

**Creates / constrains follow-up decisions:**
- **Q21 (observability)** — outbound webhook delivery success/failure rate, inbound verdict-receipt latency, dead-letter rate are first-class metrics.
- **Q23 (compliance)** — webhook payloads contain user data; transit security (HTTPS-only enforced) and at-rest retention (dead-letters expire after 30 days?) are part of the broader compliance decision.
- **Future v2 work**: webhook subscription self-service (consuming apps configure their own destinations rather than admin-managed) when productization warrants.

**Risks accepted:**
- Schema drift between voice-app and consuming apps when consuming apps are in different repos. Mitigation: publish typed contracts as a small npm package; consuming apps depend on it; CI verifies schema versions match. For 4tradesCRM (separate repo, already exists), contracts are imported via npm. For super-admin (same monorepo), via workspace package directly.
- Multiple destinations for the same output kind could result in duplicate user-visible artifacts (e.g., a Lead created in two CRMs). Mitigation: configuration choice per tenant; voice-app warns at config time but doesn't enforce single-destination.
- HMAC secret rotation requires coordination with the consuming app. Mitigation: support a brief overlap period where both old and new secrets validate; consuming apps update during a rotation window.