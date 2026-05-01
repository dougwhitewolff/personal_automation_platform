---
number: 003
title: Primary user surface
status: accepted
date: 2026-04-28
---

# 003 — Primary user surface

**Status:** accepted
**Date:** 2026-04-28

## Question

Given the learning-model commitment in [002](002-learning-model-and-feedback-architecture.md) — verdicts as first-class data, dashboard as canonical edit/review surface — the v1 surface question is no longer "what UI does the user have." The dashboard is mandatory. The remaining question is: **what is the delivery flow?** Specifically:

1. Do pipeline outputs land in native targets (Google Calendar, Google Docs, etc.) **before** user review (deliver-then-review), or **after** user review (review-then-deliver)?
2. How is the user notified that a run has completed and feedback is needed?
3. Is the policy uniform across all pipeline outputs, or does it vary by output type?

## Why this matters now

The delivery flow shapes how trust is earned and how feedback is captured. Review-then-deliver is the safest model — the system never takes irreversible action without explicit approval — but adds friction the author has to absorb on every output. Deliver-then-review is lower friction but means some outputs (sent emails, scheduled meetings) can have real-world consequences before the author has reviewed them. Per-output-type routing acknowledges that not every output has the same stakes, but adds a config dimension to every pipeline.

The notification mechanism is a smaller question but affects whether the author actually sees pending reviews promptly. Email is universal and already in scope; push is more immediate but requires more infrastructure; chat is conversational but adds a platform dependency.

This decision also nails down the relationship between the dashboard and native targets. If the dashboard is canonical, native targets are downstream delivery — they receive *what was accepted*. If native targets are canonical, the dashboard is observability + feedback only, and edits sync bidirectionally. The first is simpler; the second is more flexible but adds engineering complexity.

## Options

### Option A — Review-then-deliver (uniform, dashboard-canonical)

Pipeline runs → output drafted → lands in dashboard pending review → user reviews/edits → on accept, system delivers to the relevant native target. Email notifies user that a review is pending. Native targets are read-only delivery destinations; they receive the *accepted* artifact, never the unreviewed draft. Edits, if any, happen in the dashboard before delivery.

**Steel-manned reasoning:** This is the safest possible trust-building model and the cleanest from a feedback-capture standpoint. The system never takes irreversible action without explicit user approval — no accidentally-scheduled meetings, no accidentally-shared drafts, no calendar pollution. The diff between draft and accepted is the explicit, structured feedback signal — exactly what 002 needs as data. Dashboard-as-canonical means there is no bidirectional-sync engineering, which is a meaningful complexity reduction. And the friction of reviewing every output is exactly the discipline the author needs in v1 to actually look at what the system is doing — which is the dogfooding loop that drives quality up.

**Priors / assumptions this rests on:**
- Author tolerates opening the dashboard for every output in v1 — confidence: **medium-high** (early on, yes; long-term, may chafe)
- Email notification is reliable enough for time-sensitive pending reviews — confidence: **medium-high**
- Single-direction delivery (dashboard → native target) is meaningfully simpler than bidirectional sync — confidence: **high**
- The friction of universal review surfaces useful feedback the author wouldn't otherwise volunteer — confidence: **medium-high**

### Option B — Deliver-then-review (uniform, native-target-canonical)

Pipeline runs → output delivered immediately to native target (Calendar event created, doc drafted). Dashboard shows the run as "delivered, awaiting verdict." User can edit either in the native target or in the dashboard; edits sync bidirectionally. Verdict is captured either explicitly (user clicks accept/reject) or implicitly (no edits in N days = accepted, edits = delta to learn from).

**Steel-manned reasoning:** Lowest friction for the author — outputs are immediately useful, no gating. Native targets are best-in-class UIs for their data type; editing happens where it's most natural rather than in our custom dashboard. The "asynchronous personal assistant" framing in VISION.md works best when outputs *just appear* without requiring user action to take effect. And implicit-verdict capture (silence = approval) sidesteps the problem of users forgetting to explicitly approve outputs they're fine with.

**Priors / assumptions this rests on:**
- System rarely produces outputs harmful enough that auto-deliver is unsafe — confidence: **low-medium** (early system, more harm risk; one accidentally-sent email can break trust)
- Bidirectional sync between dashboard and native targets is reliable enough to ship in v1 — confidence: **medium-low** (real engineering complexity; webhook coverage varies by provider)
- Implicit verdict from "no action in N days" is good signal — confidence: **low** (silence is genuinely ambiguous — user may have ignored, missed, or been busy)
- Native-target editing produces feedback signal the system can capture and learn from — confidence: **low-medium** (diffing post-edit is fragile; structured edit deltas are much cleaner)

### Option C — Per-output-type routing (hybrid)

Pipelines declare per-output stakes. High-stakes outputs (drafts to send, communications, contractually significant docs, scheduled meetings with others) route through dashboard for review-then-deliver. Low-stakes outputs (calendar reminders for self, internal notes, draft revisions of one's own docs) deliver directly to native target with feedback collected in dashboard. The pipeline definition format includes a `review_required: bool` flag (or equivalent) per output.

**Steel-manned reasoning:** Honest acknowledgement that not all outputs have the same stakes. A drafted email to a client absolutely needs review; a 10am Tuesday reminder for the author themselves does not. Matches how human assistants actually work — "send this email" requires approval, "schedule this reminder for me" doesn't. Reduces friction where appropriate, adds gates where needed. The implementation cost is small: a per-output flag in the pipeline definition. And it preserves a useful knob: start strict (review-required everywhere) and downgrade specific output types as trust grows. That's a per-pipeline tunable, not a one-time architectural choice.

**Priors / assumptions this rests on:**
- Pipeline outputs cleanly classify into stakes tiers — confidence: **medium** (clean cases exist; gray zones do too)
- Per-pipeline `review_required` config is a reasonable v1 burden — confidence: **medium-high** (small flag in pipeline definition)
- The author can articulate stakes tiers per output — confidence: **high** (Doug clearly thinks this way)
- Mixed-mode outputs (some delivered, some pending) are not confusing in the dashboard — confidence: **medium** (UI can express it cleanly with status badges)

### Option D — Review-then-deliver with "auto-approve on N successes"

Same as Option A in v1, but with a forward-looking trust-graduation mechanism: once a particular pipeline-output type has been accepted N consecutive times without edits, the system auto-graduates it to deliver-then-review. The author can override per-output or per-pipeline.

**Steel-manned reasoning:** Combines Option A's safety with Option B's eventual low-friction. The trust-building period is rigorous (everything is reviewed); once the system has earned trust on a specific output type, friction drops. The graduation is automatic (no decision the author has to make) but reversible (override available). It also produces a useful signal — the auto-graduation event itself tells you which pipelines are ready for less oversight.

**Priors / assumptions this rests on:**
- Trust accrues per output type, not per pipeline-run-instance — confidence: **medium** (probably true, but graduation criteria are non-trivial to design)
- An automatic threshold mechanism is genuinely better than a manual flag the author sets — confidence: **medium-low** (manual flags are simpler and equally effective; automation here adds machinery)
- The graduation logic can be specified in v1 without becoming complex — confidence: **medium-low** (these mechanisms tend to grow complex once edge cases hit)

## Recommendation

**Option C — per-output-type routing.**

The trust-building benefits of review-then-deliver where it matters, the friction-reduction of deliver-then-review where it doesn't. A drafted email needs review; a calendar reminder for the author themselves does not. The implementation cost is one flag per pipeline output type. Most importantly, this preserves a knob the author controls — the policy is per-output-type, so it can be tuned per pipeline as evidence accrues without re-architecting.

Default policy: `review_required: true` for all outputs in v1, downgraded explicitly per output type as the author chooses. This means v1 effectively starts as Option A (review-then-deliver everywhere), but the architecture supports loosening over time without a rebuild.

Notification mechanism: **email** in v1 — already in scope as ingestion plumbing, universal across devices, reliable. Push and chat can be added later if email proves too slow for time-sensitive reviews.

Native target relationship: **dashboard-canonical, native targets as downstream delivery.** Native targets receive accepted artifacts; they are not edited bidirectionally. This avoids the sync engineering of Option B without losing the ability to add it later if needed.

**Key reason it wins:** acknowledges reality (different outputs have different stakes) without over-engineering. Single per-output-type flag, defaults to safe, tunable as trust grows. Option A is too friction-heavy long-term; Option B is too risky in v1; Option D's auto-graduation is machinery the author doesn't need.

**Main risk we're accepting:** judgment calls on which outputs are "high stakes" can be wrong, and the wrong call lands a real-world consequence the author didn't approve. Mitigation: default to `review_required: true` for every new output type and downgrade only after demonstrated reliability. Errors are biased toward friction, not toward unreviewed action.

## Decision

> **Substantively amended 2026-04-28** after the headless-backend reframe. The original decision (per-output-type routing with voice-app as the canonical review surface) is preserved below for context. The actual v1 shape is **consuming-app-canonical review** — voice-app is a backend service with no user-facing UI; consuming apps (4tradesCRM, marketing app, future third-party CRMs) own the review surface entirely. Verdicts flow back to voice-app via inbound webhooks.

### Original Option C decision (superseded by amendment)

~~Per-output-type routing with default `review_required: true`. Dashboard-canonical for review; native targets as downstream delivery; email notifications for review pending.~~

### Amended decision: consuming-app-canonical review

**Voice-app has zero user-facing UI in v1.** It is a backend service. Per-output-type routing (`review_required: true` default) is preserved as a *concept on outputs* — but the review happens in the consuming app, not in voice-app. Specifically:

- **Voice-app produces outputs** (drafts, calendar events, leads, project-tagged transcripts, etc.) and ships them to consuming apps via outbound webhooks (per [020](020-integration-contracts.md)).
- **Consuming apps render outputs** in their own UI. 4tradesCRM gets a "voice-app drafts" inbox; marketing app gets a project-tagged-interaction view. Each consuming app uses its own UX patterns and design system.
- **Users review/edit/accept/reject in the consuming app.** No voice-app UI involved.
- **Verdicts return via inbound webhooks** (per [020](020-integration-contracts.md)). Consuming apps POST `verdict.captured` events with the user's decision + edited artifact (if any) + reason. Voice-app processes these into the audit log and the learning corpus per [002](002-learning-model-and-feedback-architecture.md).
- **Super-admin UI is a separate Next.js app**, not part of voice-app, per [019](019-repo-structure.md). Voice-app exposes admin APIs; super-admin renders them.
- **Email outbound** scope-reduces — no longer the user-facing review channel (consuming apps notify their own users). Outbound email retained only for system-to-system alerts (super-admin notifications, etc.) per [012](012-email-vendor.md).

The `review_required` concept on `outputs[].kind` (per [015](015-pipeline-definition-format.md)) still applies — it tells voice-app whether to deliver immediately or hold pending verdict. But the actual review happens in the consuming app's UI, not voice-app's.

## Consequences

**Locks in (amended):**
- Voice-app is a backend service with no user-facing UI in v1. The original "web dashboard is required" requirement is removed.
- Outputs flow to consuming apps via outbound webhooks (per [020](020-integration-contracts.md)). Each tenant configures destinations per output kind.
- Verdicts flow back via inbound webhooks from consuming apps. Webhook contract is HMAC-signed per tenant.
- The `review_required` flag on `outputs[].kind` (per [015](015-pipeline-definition-format.md)) is preserved — it tells voice-app whether to hold an output until verdict arrives or deliver immediately. The *location* of review is in the consuming app.
- Super-admin UI lives in a separate Next.js app per [019](019-repo-structure.md). It reads voice-app's admin APIs.
- The original dashboard-related work in 015 (auto-discovered pipeline registry, "Unavailable in standalone mode" rendering, citation-anchored output) is preserved — but rendered by the consuming app, not voice-app.

**4tradesCRM-side work added (tracked separately, not in this repo):**
- "Voice-app drafts" review inbox in CRM UI for users to accept/edit/reject proposed task completions.
- Webhook receiver in CRM that consumes voice-app's `pipeline.output.proposed` events.
- Webhook sender in CRM that emits `verdict.captured` events back to voice-app on user action.
- Same-shape work needed for the marketing app on Doug's marketing-app side.

**Creates / constrains follow-up decisions:**
- **[020] (integration contracts)** is the new decision that captures the webhook shapes, tenant→destination mapping, HMAC signing, retry/replay semantics. This is the integration boundary docs consuming apps will read.
- **[012] (email vendor)** scope-reduces — outbound transactional email is no longer the user-facing review channel. Inbound (Plaud parsing) is unaffected.
- **[009] (CRM integration shape)** generalizes — 4tradesCRM is the v1 CRM consumer; marketing app is the v1 marketing consumer; pattern extends to future third-party CRM consumers.
- **[015] (pipeline definition)** gains a per-output `webhookContract` reference — outputs declare their wire shape so consuming apps can subscribe with confidence.
- **Q21 (observability)** must include outbound webhook delivery + inbound verdict receipt as first-class observability surfaces.

**Risks accepted (amended):**
- Voice-app is dependent on consuming apps to ship the user-facing review UX. v1 won't be usable until 4tradesCRM has the "voice-app drafts" inbox and the marketing app has its project-attached-transcript view. Mitigation: those consuming-app changes are bounded; both products are owned by Doug; coordination is internal.
- A single tenant in both CRM and marketing app means the same transcript may produce outputs to both. Mitigation: per-output-kind destination config (per [020](020-integration-contracts.md)); cross-app overlap becomes config, not architecture.
- "Time-sensitive review" cases may still arise (meeting in 30 minutes needs immediate review). Mitigation: consuming apps own the notification UX (CRM may push to mobile, marketing app may surface differently); voice-app no longer has to solve this.
