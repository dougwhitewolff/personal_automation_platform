---
number: 011
title: Hosting and deployment
status: accepted
date: 2026-04-28
---

# 011 — Hosting and deployment

**Status:** accepted
**Date:** 2026-04-28

## Question

Where does the voice-app run in production? The candidates are Next.js-friendly hosts: Vercel (Next.js's home), Fly.io (containers, persistent processes), Railway (managed platform), and self-hosted (AWS/GCP/Render). Constraints: must serve the Next.js app at the chosen subdomain (e.g., `voice.4trades.io` per [009](009-crm-integration-shape.md)), must be reachable from Inngest's hosted service for webhook callbacks, and should be in (or near) the Supabase project's region for low DB latency.

## Why this matters now

Hosting choice influences daily operations more than most decisions in this queue. Locks in:

- Deploy ergonomics (one-click vs. Dockerfile vs. CI pipeline)
- Cold-start latency model (serverless vs. persistent process)
- Pricing curve as we scale from 1 user → 100 → 1,000
- Preview-branch / staging-environment story
- Vendor relationship for the layer that owns runtime
- Domain / DNS topology (subdomain on a shared root with 4tradesCRM)

Switching hosts later is rarely catastrophic for a Next.js app, but it's a multi-day distraction at a bad moment. Better to pick correctly now.

## Options

### Option A — Vercel

Next.js's home. First-party support: zero-config deploys, automatic preview branches per pull request, integrated edge runtime, built-in analytics, Image/Font optimization, ISR / Server Components / Server Actions all work without setup. Connects to GitHub, deploys on push.

**Steel-manned reasoning:** This is the path of least resistance for a Next.js application in 2026, full stop. Every Next.js feature (App Router, Server Components, Server Actions, edge functions, ISR, Image, Middleware) works exactly as documented because Vercel and Next.js are built by the same team. Preview deploys per PR are free and automatic — solo dev gets a real staging environment without setup. Inngest's webhook integration is documented for Vercel specifically; cold starts on the Inngest route handler are bounded (~150–300ms) and don't matter for async event ingestion. The integrated dashboard surfaces logs, traces, and errors in one place. For a solo dev whose hours are the most expensive resource in the project, every saved minute of deploy plumbing is a minute spent on the actual product. Pricing is honest: Hobby tier is free for non-commercial use; Pro tier is $20/seat/mo + bandwidth-and-compute usage — predictable, reasonable for v1+v2 scale, and meaningfully cheaper than the equivalent ops time on Fly or AWS.

**Priors / assumptions this rests on:**
- Vercel's first-party Next.js support is materially better than competitors — confidence: **high** (every Next.js feature ships on Vercel first; some features are Vercel-exclusive at launch)
- Cold starts on serverless functions (~150–300ms) don't matter for our workload — confidence: **high** (dashboard requests are user-initiated and tolerate this; Inngest webhooks are async; pipelines run inside Inngest's runtime, not Vercel's)
- Vercel pricing is acceptable at v1 + v2 scale — confidence: **medium-high** (Pro tier is fine; bandwidth costs are a v3-scale concern)
- Preview deploys per PR are a meaningful productivity gain — confidence: **medium-high** (real value for testing pipeline changes against real Inngest events without affecting production)
- Vendor lock-in is bounded — confidence: **medium-high** (Next.js itself is portable; some Vercel-specific features can be replaced if needed)

### Option B — Fly.io

Container-based hosting. Deploy via `fly.toml` + Dockerfile (or auto-detected for Next.js). Multi-region built-in; persistent processes (no cold starts); low-cost VM-backed compute. Good for apps that need always-warm processes or non-standard runtimes.

**Steel-manned reasoning:** Fly gives us persistent Node processes with no cold-start variance. Multi-region deployment is straightforward — if voice-app needs to be co-located with 4tradesCRM (wherever the CRM is hosted) for inter-product API call latency, Fly handles that natively. Cheaper at scale than Vercel for compute-heavy workloads. The containerized model means we own the runtime exactly — no surprise platform changes, no runtime ABI shifts. For a long-lived hosted service, owning the box has real value.

**Priors / assumptions this rests on:**
- Persistent processes meaningfully outperform Vercel serverless for our workload — confidence: **low** (cold starts don't bite us; serverless scales to zero, which is cheaper at v1)
- Multi-region deployment is a v1 concern — confidence: **low** (single region next to Supabase is sufficient)
- Solo dev wants to manage `fly.toml` and Dockerfile — confidence: **low** (real ops cost; Vercel's zero-config is genuinely faster)
- Fly's preview-branch story is comparable to Vercel's — confidence: **low** (Vercel's per-PR previews are best-in-class; Fly requires more setup)
- Cost savings vs. Vercel materialize in v1/v2 — confidence: **low-medium** (true at scale; not at our scale yet)

### Option C — Railway

Managed platform with simple deploys. Connect a GitHub repo; Railway auto-detects Next.js. Persistent processes. Same dashboard for app + Postgres if you want them co-located. Less feature-rich than Vercel; less ops than Fly.

**Steel-manned reasoning:** Railway hits the sweet spot between Vercel's polish and Fly's flexibility. Auto-detect for Next.js means minimal config; persistent processes mean no cold-start surprises; the same dashboard hosts the app, the database (if we wanted to host Postgres there instead of Supabase), and any side services like Redis. For a solo dev who values simplicity and predictability over ecosystem depth, Railway is a clean choice. Pricing is usage-based and reasonable.

**Priors / assumptions this rests on:**
- Railway's Next.js support matches Vercel for our use case — confidence: **medium-low** (close but Vercel is unambiguously tighter)
- Persistent processes vs. serverless makes a v1 difference — confidence: **low** (same as Fly's prior)
- Railway's longevity and product direction are stable — confidence: **medium** (smaller vendor; some platform risk)
- Railway pricing is competitive — confidence: **medium-high** (reasonable for v1)
- Solo dev productivity matches Vercel — confidence: **medium-low** (slightly more setup; no first-party Next.js features; preview-branch story is OK but not as polished)

### Option D — Self-hosted (AWS ECS/Fargate, GCP Cloud Run, or VM)

Run Next.js on our own cloud infrastructure. Maximum control. Deploy via custom CI/CD, container registry, orchestration platform.

**Steel-manned reasoning:** Maximum control and minimum vendor relationship. Enterprise-grade scaling, custom networking, IAM-level access control. For a system intended to grow into an enterprise product with serious compliance requirements, owning the cloud account is foundational. AWS is the safe long-term bet; GCP Cloud Run is the simplest "managed serverless" alternative.

**Priors / assumptions this rests on:**
- Solo dev productivity on AWS/GCP matches managed Next.js platforms — confidence: **very low** (ops surface is dramatically larger; CloudFormation / Terraform / IAM are full skills)
- Enterprise compliance requirements are a v1 concern — confidence: **low** (premature; v1 has no enterprise customers asking for VPC isolation)
- Cost savings materialize at v1 scale — confidence: **very low** (managed platforms are dramatically cheaper for small workloads when you account for ops time)
- The control benefit is worth the ops cost in v1 — confidence: **very low**

## Recommendation

**Option A — Vercel.**

For a Next.js application built by a solo dev, hosted on Vercel is the correct default. Every Next.js feature works as documented because Vercel and Next.js are built by the same team. Preview deploys per pull request are zero-config and free — invaluable for testing pipeline changes against real Inngest events without touching production. Cold starts (~150–300ms) are imperceptible for our workload (dashboard requests tolerate it; pipeline execution lives in Inngest's runtime, not Vercel's). Pricing is honest at $20/seat/mo + usage — meaningfully cheaper than the equivalent ops time on Fly or AWS, and fine through v2 scale.

Fly (B) and Railway (C) are defensible alternatives if there's a specific reason to prefer persistent processes or co-location with 4tradesCRM hosting (depends on where the CRM runs in production). Self-hosted (D) is over-investment in v1 with no offsetting benefit.

**Concrete v1 deliverables:**
1. Vercel project connected to the voice-app GitHub repo (this repo). Branch `main` → production; pull-request branches → preview deploys.
2. Custom domain `voice.4trades.io` configured in Vercel; DNS CNAME record pointing to Vercel.
3. Environment variables in Vercel: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `INNGEST_EVENT_KEY`, `INNGEST_SIGNING_KEY`, `TRUSTED_ISSUERS_4TRADES_JWKS_URL`. Secrets segmented by environment (preview vs. production).
4. Vercel region matches the Supabase project's region (e.g., `iad1` for `us-east`). Confirms low DB latency.
5. Vercel Analytics enabled (built-in; free at low scale) for basic request metrics. Real observability stack is a separate decision (Q19).

**Open question that may shift the call:** where does 4tradesCRM run in production today? If it's already on Fly or Railway, hosting voice-app on the same platform may be worth the small productivity hit on Next.js polish — co-location reduces inter-product API latency and consolidates billing. Worth confirming before committing.

**Key reason it wins:** zero-config Next.js deploys + preview branches + first-party feature support, all at a price that's cheaper than the equivalent ops time on alternatives.

**Main risk we're accepting:** vendor lock-in to Vercel for the runtime layer. Mitigation: Next.js itself is portable; the few Vercel-specific features we use (preview deploys, image optimization, ISR if any) can be replaced when needed. Migration to Fly or self-hosted later is bounded engineering work, not a rewrite.

## Decision

**Option A — Vercel.** Decided 2026-04-28.

Confirmed that 4tradesCRM is already on Vercel, so this also consolidates hosting infrastructure across both products — single vendor for the runtime layer, one billing surface, and inter-product API calls stay within Vercel's network.

## Consequences

**Locks in:**
- Vercel as the runtime host. Production deploy from `main`; preview deploys per pull request.
- Custom domain `voice.4trades.io` (or Doug's preferred subdomain) configured in Vercel; CNAME points to Vercel.
- Vercel region matches the Supabase project's region (e.g., `iad1` for `us-east`) for low DB latency.
- Environment variables managed in Vercel UI, segmented by environment (preview vs. production). Required: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `INNGEST_EVENT_KEY`, `INNGEST_SIGNING_KEY`, `TRUSTED_ISSUERS_4TRADES_JWKS_URL`.
- Single-vendor consolidation with 4tradesCRM (both on Vercel). Inter-product API calls stay within Vercel's network — minor latency benefit, single billing surface.

**Creates / constrains follow-up decisions:**
- **Q19 (observability stack)** — Vercel Analytics covers basic request metrics natively; pipeline observability comes from Inngest's run inspector; full observability stack still needs deciding (Sentry, Axiom, OTEL, etc.).
- **Q21 (CI/CD)** — Vercel handles deploy on push automatically; CI for tests / type-checks / RLS suite still needs deciding (GitHub Actions is the obvious default).

**Risks accepted:**
- Vendor lock-in on Vercel for the runtime layer. Mitigation: Next.js itself is portable; few Vercel-specific features in active use; migration to Fly/Railway/AWS later is bounded engineering work.
- Vercel pricing scales with usage. At v3 scale (~1,000 users), Vercel costs may exceed the equivalent on Fly. Mitigation: revisit if/when bandwidth/compute costs cross a threshold (a few hundred dollars per month).

**Migration trigger (added 2026-04-28 after backend-shape pressure-test):**

The backend-shape reframe (voice-app is a pure backend service per [003](003-primary-user-surface.md) rewrite; durability lives in Inngest per [006](006-workflow-engine.md), not in Vercel compute) made Vercel still the right call for v1. Document explicit migration signals so we revisit deliberately rather than reactively:

- Vercel function + bandwidth bill exceeds ~$200/mo (signals scale where Fly's flat pricing wins)
- Cold-start variance shows up as user-facing latency in observability
- An agent class that genuinely needs >15 minutes per run materializes (exceeds Vercel Pro Fluid Compute limit)
- Multi-region deployment becomes a real customer requirement

If any trigger fires, evaluate Fly.io (persistent containers, no cold starts, multi-region native) as the most likely replacement. Migration cost is bounded — Next.js standalone output runs on Fly via Dockerfile.

**Implementation refinement: Edge Runtime for hot webhook endpoints.**

Inbound webhook routes (`/api/email/inbound`, `/api/verdict/captured`, future `/api/plaud/transcript-ready`) use Vercel Edge Runtime by default. Near-zero cold starts; thin handlers that validate signatures and emit Inngest events fit Edge's constraints (no Node-only APIs needed for this work). All other routes use the standard Node runtime.
