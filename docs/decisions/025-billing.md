---
number: 025
title: Billing — when and how
status: accepted
date: 2026-04-28
---

# 025 — Billing — when and how

**Status:** accepted
**Date:** 2026-04-28

## Question

When does voice-app start charging customers, and how is billing structured?

## Why this matters now

Building billing infrastructure (Stripe integration, plans, invoicing, dunning, etc.) is meaningful scope. Picking the right *time* to add it matters more than picking the *vendor* — premature billing slows down v1; late billing leaves revenue on the table.

The decided constraints make the answer clear: per [001](001-target-user-and-v1-scope.md), v1 is author-only and onboarding/billing/self-serve are explicitly out of scope. Per Doug's clarifications, v1's external customers all come through consuming apps (4tradesCRM + marketing app, both Doug's products) which already have their own customer relationships and subscription models.

## Decision

**No voice-app-level billing in v1. Bill through consuming apps' existing subscription models when external customers arrive (likely v2).** Decided 2026-04-28.

### v1 (author-only)

No billing. Voice-app is internal-only; Doug isn't billing himself.

### v2 (when 4tradesCRM and marketing-app customers start using voice-app)

Voice-app is consumed as a feature of those products. Customers pay 4tradesCRM (or marketing app) on their existing subscription terms; voice-app's costs (LLM calls, Vercel compute, Supabase, Resend, Inngest) are part of the consuming product's COGS. The consuming app may add a Plaud-automation tier to its plans or bundle it; that's a 4tradesCRM-side product decision, not a voice-app-side decision.

Voice-app exposes **per-tenant usage metrics** (LLM tokens consumed, agent runs, transcripts processed, webhook deliveries) via admin APIs so the consuming apps can:
- Surface usage to their customers
- Apply usage-based pricing if they want to
- Internally track which customers are driving voice-app's COGS

These usage metrics are already being captured for observability per [022](022-observability-stack.md) — exposing them to consuming apps is a small additional API surface, not new infrastructure.

### v3+ (if/when voice-app is sold standalone)

If voice-app is ever sold directly to customers without going through a consuming app (not the current plan, but worth considering), revisit billing then with real evidence about pricing and packaging. Stripe is the obvious vendor; subscription model TBD.

## Consequences

**Locks in:**
- Zero billing infrastructure in v1.
- Voice-app exposes per-tenant usage metrics via admin APIs in v2 (for consuming apps to consume); already captured for observability.
- Consuming apps own pricing and customer billing relationships in v2.
- Voice-app does not have a "subscription" entity, "plan" entity, or any payment-related state in its data model.

**Creates / constrains follow-up decisions:**
- **Q27 (compliance)** — payment data is not in voice-app's scope, simplifying compliance (no PCI considerations).
- **v3+ standalone billing** — deferred decision, gated on a real standalone customer materializing. Revisit Stripe vs. alternatives at that point.

**Risks accepted:**
- Voice-app's COGS at v2 falls on consuming apps' margins. Mitigation: per-tenant usage metrics let consuming apps set pricing that accounts for it.
- If voice-app is sold standalone unexpectedly early (a customer wants it without the CRM), we have no billing infrastructure to use. Mitigation: v1.x-add Stripe integration is bounded engineering (~1 week); not blocking architecture.

## Decision

_Awaiting decision._

## Consequences

_To be filled in after decision._
