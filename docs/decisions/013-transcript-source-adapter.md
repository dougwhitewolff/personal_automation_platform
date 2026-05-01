---
number: 013
title: Transcript source adapter interface
status: accepted
date: 2026-04-28
---

# 013 — Transcript source adapter interface

**Status:** accepted
**Date:** 2026-04-28

> **Scope clarification (2026-04-28):** Original draft assumed v1 might receive audio attachments and need server-side transcription. Doug clarified that Plaud transcribes on-device and forwards email with transcript text — voice-app v1 receives **text only**. Audio ingestion is intentionally out of scope, with the architecture leaving a clean insertion point for it later. This rewrite reflects that simpler reality.

## Question

When a transcript arrives (email forwarded from Plaud today; Plaud API later; future sources after that), how does it get into voice-app's system as a canonical, deduped, tenant-scoped entity ready for the routing layer to consume? VISION explicitly requires Plaud API integration to be an **adapter swap, not a refactor** — so the seam between "source-specific input" and "uniform downstream pipeline" is the load-bearing decision.

## Why this matters now

- VISION's non-negotiable: adapter swap, not refactor.
- Multiple sources are realistically in scope (email v1; Plaud API v1.x; potentially 4tradesCRM voice-capture handoff if a customer wants it; future direct REST API uploads).
- Each source has wildly different raw input shapes (email body + headers, Plaud webhook payload, REST upload, etc.) but the *downstream* work — dedup, persistence, tenant scoping, emitting a "ready for routing" event — is uniform.
- Inngest's event-driven model (per [006](006-workflow-engine.md)) fits this naturally: source-specific Inngest functions emit normalized events; downstream functions consume them.

## Discussion

The fork is whether to share downstream plumbing across sources or duplicate it per-source.

**Shared downstream pipeline (chosen):** Each source has its own small Inngest function (`handleEmailReceived`, future `handlePlaudTranscriptReady`, etc.) that parses its source-specific input and emits a normalized `transcript.normalized` event. A single shared `dedupe-and-persist-transcript` Inngest function consumes those events, enforces `(source, external_id)` uniqueness via DB constraint, persists to the `transcripts` table, and emits `transcript.ingested` for the routing layer (Q17).

Adding a new source = one new event handler. Dedup, persistence, tenant scoping, and routing are inherited.

**Per-source pipelines (rejected):** Each source has its own end-to-end pipeline duplicating dedup, persistence, and event emission. This explicitly fails VISION's "adapter swap, not refactor" requirement — adding Plaud means copying the email pipeline and replacing the parsing step, which is a refactor.

## Decision

**Thin source adapters + shared downstream pipeline.** Decided 2026-04-28.

### v1 architecture

```
[email.received]              ← Resend webhook delivers Plaud-forwarded email
    ↓ handleEmailReceived (parses, extracts transcript text, scopes to tenant)
[transcript.normalized]
    ↓ dedupeAndPersistTranscript (enforces (source, external_id) uniqueness; writes row)
[transcript.ingested]         ← consumed by routing layer (Q17)
```

### Normalized event shape

```ts
type TranscriptNormalizedEvent = {
  type: 'transcript.normalized';
  source: 'email' | 'plaud-api' | '4trades-voice-capture' | 'direct-api';
  externalId: string;            // source-specific dedup key
  tenantId: string;
  text: string;                  // the canonical transcript
  capturedAt: string;            // ISO datetime
  metadata: Record<string, unknown>; // source-specific fields, kept for debugging/audit
};
```

### `transcripts` table (Supabase Postgres)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid (PK) | voice-app's UUID |
| `external_id` | text | source-specific dedup key |
| `source` | text | discriminator |
| `tenant_id` | uuid | RLS scoping (per [008](008-multi-tenancy-model.md)) |
| `captured_at` | timestamptz | when the user actually said it |
| `ingested_at` | timestamptz | when voice-app received it |
| `text` | text | canonical transcript |
| `metadata` | jsonb | source-specific fields |

Unique constraint: `(source, external_id)`. RLS policies per 008 (`tenant_id = (auth.jwt() ->> 'tenantId')::uuid OR isInternalStaff = true`).

### Adding new sources

Adding a source = one new Inngest function that:
1. Listens to its source-specific event (e.g., `plaud.transcript-ready`)
2. Parses the source-specific payload
3. Determines the tenant (via routing rules per source — Plaud might use API-key-to-tenant mapping; 4tradesCRM voice-capture would inherit tenant from the JWT)
4. Emits `transcript.normalized`

Everything downstream is inherited.

### Audio: explicitly out of scope, door left open

V1 does **not** ingest audio. Plaud transcribes on-device; emails forward text only. If a future source produces audio (a customer uploads voice memos directly, a CRM hands off audio files, etc.), the architecture inserts cleanly:

- Audio-producing source emits `audio.received` instead of `transcript.normalized`
- A new `transcribe-audio` Inngest function listens to `audio.received`, calls an ASR provider (per Q15), and emits `transcript.normalized`
- Everything downstream stays unchanged

This is documented as a *future-extension pattern*, not v1 scope. We do not build the `transcribe-audio` function, an audio storage bucket, or an ASR provider integration in v1. We do not optimize the v1 schema for audio (no `audio_url` column on `transcripts` until needed). When the first audio source materializes, we add the bucket, the ASR step, and the column at that point — bounded incremental work.

## Consequences

**Locks in:**
- Single shared `dedupe-and-persist-transcript` Inngest function. No per-source persistence logic.
- `(source, external_id)` as the dedup key on the `transcripts` table.
- Tenant determination happens *inside* each source-specific handler, not in shared downstream code. Each handler must explicitly resolve the tenant from its source-specific input (e.g., email-to-tenant mapping via the inbound address per [012](012-email-vendor.md); Plaud API key-to-tenant mapping; CRM JWT for handoffs).
- Adding a new source is a focused change: one new Inngest function plus its event-type registration.

**Creates / constrains follow-up decisions:**
- **Q15 (LLM provider strategy)** — does NOT need to include ASR provider in v1. Pure text-handling LLM choice.
- **Q17 (keyword routing)** — consumes `transcript.ingested` events.
- **Q24 (compliance posture)** — text-only retention is a simpler compliance story than audio. Audio retention policy is deferred until audio ingestion lands.

**Future-extension pattern (not v1 scope, documented for clarity):**
- Audio ingestion: source adapter emits `audio.received` → new `transcribe-audio` step → emits `transcript.normalized` → existing pipeline. Add storage bucket and `audio_url` column at that point.

**Risks accepted:**
- We're committing to a slightly opinionated event-flow shape before any source other than email is implemented. Mitigation: the shape is small (one normalized event, one shared persistence step) and well-precedented in event-driven architectures. If a source has fundamentally incompatible needs, we revisit.
- Tenant resolution happens per-source handler rather than in shared code. This is the right design — different sources have different tenant signals — but it's a place where new-source bugs could land. Mitigation: code-review checklist for new source handlers explicitly verifies tenant resolution is correct; integration test for cross-tenant safety.
