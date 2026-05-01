---
number: 012
title: Email vendor (inbound + outbound)
status: accepted
date: 2026-04-28
---

# 012 — Email vendor (inbound + outbound)

**Status:** accepted
**Date:** 2026-04-28

## Question

What email vendor handles voice-app's two email needs?

1. **Inbound parsing** — Plaud devices forward voice transcripts (or audio attachments) to a dedicated email address. Voice-app needs to receive that email as a webhook (HTTP POST with parsed body, attachments, headers) so the ingestion pipeline can fire.
2. **Outbound transactional** — voice-app sends "review pending" notifications when a pipeline finishes and needs author review (per [003](003-primary-user-surface.md)).

The vendor must support both. Inbound parsing rules out generic SMTP (which is what 4tradesCRM uses via nodemailer — outbound-only).

## Why this matters now

Email ingestion is the v1 transcript source per VISION.md (Plaud API will replace it later as an adapter swap). The vendor controls reliability of the most important plumbing in the system — if inbound parsing fails or has high latency, transcripts don't arrive and pipelines don't fire. Outbound deliverability also matters: review-pending emails are time-sensitive, and if they land in spam, the trust-building dogfooding loop breaks.

Switching vendors later isn't catastrophic but is real work — DNS records (DKIM, SPF, DMARC) must be re-verified, inbound webhook URLs migrated, sender reputation re-built (warm-up periods on new providers).

## Options

### Option A — Resend

Modern email API built by ex-Vercel folks (2022+). React Email integration for templates. Inbound parse webhook (added 2024). Generous free tier (3,000 emails/month, 100/day). Pricing scales reasonably.

**Steel-manned reasoning:** Resend is the canonical modern email vendor for the Next.js + Vercel ecosystem in 2026. The DX is genuinely best-in-class — React Email lets us write notification templates as React components with shared design tokens, type-checked at build time. The inbound parse webhook is a standard HTTP POST to a route handler we already own; no S3 buckets, no Lambda functions, no warm-up period. Vercel and Resend are explicit ecosystem partners; the integration is documented and battle-tested. Free tier covers v1 (author + 2 customer companies generates well under 3,000 emails/month). Pricing past free tier ($20/mo for 50K emails) is honest. Deliverability has matured significantly since launch — competitive with Postmark for transactional emails in 2026.

**Priors / assumptions this rests on:**
- Resend's DX is meaningfully better than competitors for solo dev on Next.js — confidence: **high** (React Email + Vercel partnership is genuinely tighter integration)
- Inbound parse webhook is reliable for v1 traffic — confidence: **medium-high** (newer feature than Postmark's; less battle-tested but mature by 2026)
- Free tier covers v1 + early v2 — confidence: **high** (generous; voice-app email volume is bounded)
- Deliverability is competitive with Postmark in 2026 — confidence: **medium** (gap has closed; Postmark still slightly ahead for highest-stakes mail)
- Resend's longevity is stable — confidence: **medium-high** (well-funded, growing, ecosystem-aligned)

### Option B — Postmark

Founder-led, product-focused vendor with the strongest deliverability reputation in transactional email. Inbound parse via "InboundHook." Mature, stable, slightly more expensive than competitors.

**Steel-manned reasoning:** Postmark is the deliverability champion. For a system where review-pending emails are time-sensitive, "lands in inbox not spam" is the actual product, and Postmark has the best track record for that. Inbound parsing is mature (~10 years in production), with rich webhook payloads. The product is opinionated — Postmark explicitly only does transactional email (no marketing), which means their sender reputation isn't tainted by mass-marketing baggage like SendGrid's. For a long-lived hosted service where deliverability is a real moat, Postmark is the safe long-term call.

**Priors / assumptions this rests on:**
- Deliverability advantage over Resend is meaningful in practice — confidence: **medium** (real but the gap has closed; matters more at scale)
- Postmark's InboundHook is the gold standard for parsing reliability — confidence: **medium-high**
- Pricing premium ($15/mo starter, $1.25 per 1K vs. Resend's $20/mo for 50K) is worth it — confidence: **medium-low** (real cost; Resend's lower per-email cost compounds at scale)
- Postmark's product longevity is stable — confidence: **high** (mature, profitable, founder-led)

### Option C — AWS SES + S3/Lambda for inbound

The cheapest sending option per email at scale. Inbound requires SES → S3 (received emails stored as files) → Lambda (parses and POSTs webhook). More moving parts.

**Steel-manned reasoning:** At significant scale, SES is dramatically cheaper than the alternatives — fractions of a cent per email vs. Resend/Postmark's per-thousand pricing. AWS-native means tight integration if we ever go all-in on AWS. The inbound architecture (SES + S3 + Lambda) is decoupled and scales horizontally. For a hosted service that may eventually send millions of emails per month, betting on SES from the start avoids a future migration.

**Priors / assumptions this rests on:**
- Cost savings materialize at v1 scale — confidence: **very low** (free tier on Resend covers v1 entirely; SES setup time exceeds the savings by orders of magnitude)
- Solo dev can maintain SES + S3 + Lambda for inbound — confidence: **low** (real ops; warm-up periods, reputation management, IAM, CloudWatch)
- Deliverability on a fresh SES account is acceptable for v1 — confidence: **low** (warm-up periods; new SES accounts start in sandbox; reputation building takes weeks)
- The control benefit is worth the ops cost in v1 — confidence: **very low**

### Option D — SendGrid

Twilio-owned. Mature. Has both inbound parse and outbound. Lots of features. More complex pricing. Reputation issues at scale due to marketing-email baggage.

**Steel-manned reasoning:** Long-established vendor with both inbound and outbound covered. Twilio backing means it's not going anywhere. Free tier exists. API is mature.

**Priors / assumptions this rests on:**
- SendGrid's marketing-email reputation doesn't bleed into our transactional sender — confidence: **medium-low** (it's improved; still a real concern for shared-IP plans)
- Pricing is competitive with Resend — confidence: **medium-low** (SendGrid pricing is Byzantine; Resend is cleaner)
- DX matches modern alternatives — confidence: **low** (feels legacy in 2026; React Email integration absent)
- Long-term direction under Twilio is stable — confidence: **medium**

## Recommendation

**Option A — Resend.**

For a solo dev on Vercel + Next.js, Resend is the canonical modern choice. React Email lets us write notification templates as type-checked React components with shared design tokens. Inbound parse webhook is a standard route handler — no S3, no Lambda, no warm-up. Free tier covers v1 + early v2 entirely; paid pricing is honest. Vercel and Resend are explicit ecosystem partners with documented integration patterns.

Postmark (B) is the safer call for absolute-best deliverability, and we should revisit if we ever ship a system where "must land in inbox" is the dominant concern. SES (C) is over-investment for v1. SendGrid (D) feels legacy and the marketing-email baggage is a real concern for transactional deliverability.

**Concrete v1 deliverables:**
1. Resend account + API key. Stored in Vercel env (`RESEND_API_KEY`).
2. Verified sending domain (e.g., `voice.4trades.io`) with DKIM/SPF/DMARC records configured. From-address: `notifications@voice.4trades.io` (or similar).
3. Inbound domain configured (e.g., `inbound.voice.4trades.io`). Plaud devices forward voice memos to a dedicated address (e.g., `<tenant-id>@inbound.voice.4trades.io`).
4. Inbound webhook route handler at `/api/email/inbound` that Resend POSTs received emails to. Handler validates signature, extracts attachments, normalizes the payload, and emits an Inngest event (`transcript.received`) per [006](006-workflow-engine.md). The Inngest function then drives the pipeline.
5. Outbound notification templates in `emails/` directory using React Email components: `ReviewPending`, `RunCompleted`, `RunFailed`, etc. Each template is a React component returning JSX rendered to HTML by Resend.
6. Bounce / complaint webhook handler that updates user records when emails fail to deliver, so the dashboard can surface delivery problems.

**Multi-tenancy in inbound addressing:** dedicated inbound address per tenant (e.g., `<tenant-id>@inbound.voice.4trades.io` or a friendlier slug). When an email arrives, the webhook handler reads the recipient address, looks up the tenant, and emits the Inngest event scoped to that tenant. This means Plaud users don't share a single inbound address — each company's recordings are isolated by the address they forward to. Required for the multi-tenant architecture.

**Migration trigger documented:** if deliverability becomes a measurable problem (>2% of review-pending emails landing in spam at 30-day rolling rate), evaluate switching to Postmark. The vendor swap is bounded — Resend → Postmark is roughly an evening of work given the abstraction we'll have around `EmailService`.

**Key reason it wins:** best DX for our stack (React Email + Vercel ecosystem partnership), free tier covers v1+, inbound parse is straightforward webhook, deliverability is competitive in 2026.

**Main risk we're accepting:** Resend's deliverability is competitive but not best-in-class — Postmark still has a slight edge. Mitigation: monitor delivery metrics from day one (Resend exposes them); migration trigger above documents when to revisit. We also maintain DKIM/SPF/DMARC properly so we're not bottlenecked by sender authentication.

## Decision

**Option A — Resend.** Decided 2026-04-28.

Resend handles both inbound parsing (Plaud → email → webhook) and outbound transactional. React Email for templates. `EmailService` abstraction wraps Resend so vendor swap is bounded if migration becomes necessary.

> **Outbound scope amended 2026-04-28** after the headless-backend reframe. Originally, outbound was the v1 review-pending notification channel for users. After [003](003-primary-user-surface.md) was rewritten (consuming-app-canonical review), user-facing notifications are no longer voice-app's responsibility — consuming apps notify their own users. Outbound email's v1 scope reduces to **system-to-system alerts only** (super-admin notifications about anomalies, delivery-failure escalations, audit-log digests, etc.). Inbound parsing (Plaud forwards) is unaffected and remains the v1 transcript ingestion channel.

## Consequences

**Locks in:**
- Resend as the vendor for both inbound and outbound v1 email.
- Verified sending domain `voice.4trades.io` with DKIM/SPF/DMARC records.
- Inbound domain `inbound.voice.4trades.io` with per-tenant addresses (`<tenant-id>@inbound.voice.4trades.io` or friendlier slug).
- Webhook route at `/api/email/inbound` validates Resend signature, extracts attachments, emits Inngest `transcript.received` event scoped to tenant.
- React Email templates in `emails/` directory; type-checked at build time, shared design tokens.
- `EmailService` abstraction (in `lib/email/`) wraps Resend; no direct Resend SDK calls in business code.

**Creates / constrains follow-up decisions:**
- **Q14 (transcript source adapter)** — email is the v1 transcript source; adapter shape must accommodate Resend's webhook payload format.
- **Q19 (observability stack)** — must surface delivery metrics (bounce rate, spam-folder rate) so the migration trigger can fire if needed.

**Risks accepted:**
- Resend's deliverability is competitive but slightly behind Postmark. Mitigation: monitor delivery from day one; migration trigger documented (>2% spam-folder rate at 30-day rolling); `EmailService` abstraction makes the swap bounded.
- Resend is younger than Postmark/SendGrid. Mitigation: well-funded, growing, ecosystem-aligned with Vercel; revisit if vendor stability degrades.
