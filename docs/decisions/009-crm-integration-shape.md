---
number: 009
title: CRM integration shape and federation model
status: accepted
date: 2026-04-28
---

# 009 — CRM integration shape and federation model

**Status:** accepted
**Date:** 2026-04-28

> **Numbering note:** This decision was inserted ahead of the original 009 (auth provider, now [010](010-auth-provider.md)) after exploration of `C:\Development\4tradesCRM` revealed an existing custom-JWT auth model the voice-app must federate with. The CRM-integration question shapes Q10 (auth) and several other downstream decisions, so it belongs first.

## Question

The voice-app has two confirmed deployment shapes for v1: **standalone** (customers sign up directly at voice-app's domain), and **CRM-integrated** (4tradesCRM customers access voice-app from inside their CRM workflow). What is the integration topology for CRM-integrated deployments? Specifically:

1. Where does the voice-app UI render — own domain, iframe inside CRM, embedded React components, or no voice-app UI (CRM renders everything)?
2. How does identity flow from CRM to voice-app — JWT pass-through, OAuth/OIDC, postMessage, shared cookie?
3. How do voice-app pipelines write CRM artifacts (Leads, Contacts, follow-up tasks) — direct DB writes, REST API calls, or something else?
4. Does this same architecture extend to future third-party CRM integrations (the "Mass provider" Doug mentioned), or do we need separate patterns?

## Why this matters now

This decision constrains several downstream choices:

- **Q10 (auth provider)** — the auth choice is downstream of integration shape. Tight embedding may need a different auth provider than loose federation.
- **Q11 (hosting)** — domain topology, CORS, deployment count all depend on integration shape.
- **Q15 (pipeline definition format)** — pipelines that produce CRM artifacts (Leads, Contacts) need a way to write them. The integration shape defines the API contract.
- **Q12 (transcript source adapter)** — existing CRM voice feature already does file-upload transcription. Voice-app may want to consume from the CRM's voice ingestion path; the integration shape determines whether that's a shared backend or an adapter.
- **Future multi-CRM federation** — if/when third-party CRM integrations come, the v1 pattern either generalizes (good) or doesn't (rebuild).

Picking the wrong shape locks in topology decisions that are painful to reverse: domain ownership, iframe vs. native, deployment unit count, JWT-vs-OAuth federation.

## Options

### Option A — Loose federation (own domain, JWT pass-through, REST integration)

Voice-app is a standalone Next.js application deployed at its own domain (e.g., `voice.4trades.io`). 4tradesCRM has a "Voice Assistant" link that opens voice-app, passing the user's JWT via deep-link parameter or fragment (or doing a quick SSO handshake). Voice-app verifies the JWT using a JWKS endpoint exposed by the CRM (RS256 signing), establishes the user's session, and renders its own UI with the CRM's tenant context. Standalone customers sign up directly at voice-app's domain; voice-app mints its own JWTs in the same shape (`sub`, `tenantId`, `role`, `isInternalStaff`). When pipelines need to write CRM artifacts, they call 4tradesCRM's REST API.

**Steel-manned reasoning:** This is the architecturally cleanest option and the one that scales gracefully to standalone + multi-CRM. The voice-app is its own real product — independently deployable, independently brandable, independently versionable. The CRM never has to redeploy when voice-app's UI changes. The federation pattern (JWKS-verified JWT or OAuth/OIDC) generalizes directly to third-party CRMs in v2 — Salesforce, HubSpot, the "Mass provider" all become "another trusted issuer in our JWKS list" rather than "another iframe to embed." Backend integration via REST means voice-app's pipelines treat the CRM as an external system, which is exactly what it is from voice-app's standpoint. The user experience can still feel cohesive: same subdomain (`voice.4trades.io`), shared brand, persistent session, smooth back-link to the CRM. Users notice they navigated to a different page, but they don't notice they're in a different app — the same way clicking from `mail.google.com` to `drive.google.com` doesn't feel like leaving Google.

**Priors / assumptions this rests on:**
- Subdomain + JWT pass-through delivers a "feels like one product" UX without iframe gymnastics — confidence: **medium-high** (proven pattern; Linear+Slack, Vercel+v0, Notion+Notion AI all use it)
- JWKS-based JWT verification scales to multiple CRM issuers in v2 — confidence: **high**
- 4tradesCRM is willing to expose a JWKS endpoint and migrate from HS256 to RS256 — confidence: **high** (Doug owns the CRM; small one-time cost, big multi-product win)
- REST-based CRM artifact writes are sufficient — confidence: **medium-high** (CRM's API surface needs a small audit; some Lead-write endpoints may need to exist or be exposed)
- The user-friction cost of "leaving the CRM page" is bounded with good UX (back-link, same subdomain, consistent branding) — confidence: **medium-high**

### Option B — Embedded iframe inside CRM

Voice-app rendered as an iframe inside CRM pages. CRM passes the JWT via `postMessage` after the iframe loads. Voice-app feels like a feature of the CRM rather than a separate product. CSP, third-party cookies, iframe-resize, and same-origin issues are all part of the deal.

**Steel-manned reasoning:** Maximum UX coherence — users genuinely can't tell they're using two different apps. For users who live inside the CRM and only occasionally use voice features, this minimizes context-switching. The integration looks "native." For Doug's two confirmed customers who specifically asked for CRM integration, "in the CRM" probably means "inside the CRM UI," not "next to the CRM in a different tab" — and Option B delivers literally that.

**Priors / assumptions this rests on:**
- "Inside the CRM" expectation means inside the UI, not just shared identity — confidence: **medium** (could be either; worth clarifying with Doug's customers but probably acceptable as a pure-SSO link in their minds)
- Iframe issues (CSP headers, third-party cookies in 2026 browsers, height management, modal positioning, drag-and-drop file uploads inside iframe) are bounded — confidence: **low-medium** (these are real chronic problems; modern browsers actively work against third-party iframes)
- Standalone deployment of voice-app still works as a non-iframe app at its own domain — confidence: **medium** (means maintaining two rendering modes; doable but adds complexity)
- iframe pattern generalizes to third-party CRMs — confidence: **low** (every CRM has its own embedding rules; maintaining iframe compatibility across multiple CRMs is a quarterly tax)

### Option C — White-label module (React components imported into CRM frontend)

Voice-app's frontend ships as an npm package (`@voice-app/react`) that the CRM frontend imports. The CRM renders voice-app's components inline as part of its own pages. Voice-app's backend is still separate; the CRM frontend talks to voice-app's backend via the user's JWT. Maximum native feel; tightest coupling.

**Steel-manned reasoning:** From the user's perspective, voice-app is part of the CRM — same React app, same routing, same global state, same design system. No iframe issues, no domain-switching. From a developer perspective, the voice-app team owns the components but the CRM team controls when to release them. For solo dev (single owner of both products), the coupling cost is low because there's no team-coordination overhead.

**Priors / assumptions this rests on:**
- Doug owns both codebases, so the "CRM redeploys when voice UI changes" coupling is low-friction — confidence: **medium-high** (true for now; not true for third-party CRM customers in the future)
- Standalone deployment of voice-app uses the same components but in its own Next.js app — confidence: **medium** (workable but means the package serves two consumers with different styling/auth contexts)
- This pattern generalizes to third-party CRMs — confidence: **very low** (Salesforce/HubSpot/etc. don't accept React component packages from us; the pattern is literally non-portable)
- Solo dev productivity benefit is real — confidence: **low-medium** (same person maintaining both = same release cadence; benefits are aesthetic, not pragmatic)

### Option D — API-only (no voice-app UI; CRM renders everything)

Voice-app exposes a REST/RPC API. CRM's frontend builds the entire voice-app UI, calling voice-app's API directly using the user's JWT. Standalone deployment of voice-app requires a *separate* frontend project, since CRM owns the UI in this option.

**Steel-manned reasoning:** Cleanest possible separation: voice-app is a service, CRM is a UI. This is how most enterprise platform integrations work — Stripe is a service, your checkout page is your UI. From a long-term-flexibility standpoint, decoupling UI from backend means each CRM customer can build their own UI experience over the same API. Third-party CRM integrations become trivial — they just call the API.

**Priors / assumptions this rests on:**
- Doug is willing to build voice-app UI twice (once in CRM, once standalone) — confidence: **low** (real cost; effectively doubles frontend work for a solo dev)
- 003's "dashboard is canonical edit/review surface" can be satisfied by a CRM-rendered UI — confidence: **medium** (works, but means the dashboard's design is partly owned by CRM, partly by voice-app)
- Future third-party CRM customers will build their own UIs — confidence: **low** (most won't; they'll want a turn-key embed, which D doesn't provide)
- Standalone product viability without a voice-app-owned UI — confidence: **low** (standalone customers don't get to use the CRM-rendered UI; voice-app needs its own anyway)

## Recommendation

**Option A — Loose federation (own domain, JWT pass-through, REST integration).**

This is the only option that scales gracefully across all three deployment scenarios (standalone, 4tradesCRM-integrated, future third-party CRM-integrated) using the same underlying architecture. The voice-app is a real product with its own UI, its own deploy, its own brand, its own evolution cadence. CRM users access it via a "Voice Assistant" link that does a JWT pass-through (deep-link or quick SSO handshake), and the user experience feels coherent because the subdomain pattern, shared branding, and persistent session make the navigation feel like moving between rooms in the same house — exactly the pattern Linear-and-Slack, Notion-and-Notion-AI, and most modern multi-product companies use.

The federation mechanism — JWKS-verified RS256 JWTs — generalizes directly to third-party CRMs in v2: each becomes a trusted issuer added to the JWKS list. Backend integration via 4tradesCRM's REST API treats the CRM as an external system (which it is) and keeps voice-app's pipelines portable across CRMs. None of the other options have a clean third-party-CRM story.

Option B (iframe) trades a marginal UX win for a chronic technical-debt tax — third-party cookies, CSP, height management, browser sandbox tightening — that compounds across multiple CRM integrations. Option C (white-label module) is fundamentally non-portable to third-party CRMs and creates a release-coupling between two products that should evolve independently. Option D (API-only) doubles frontend work for the standalone product and offloads UX to CRM teams that will not all build a good one.

**Concrete v1 mechanics under Option A:**

1. **Voice-app deployed at `voice.4trades.io`** (or similar subdomain — Doug's call on exact domain).
2. **4tradesCRM upgrades JWT signing from HS256 (shared secret) to RS256 (asymmetric)** as a one-time change. Exposes a JWKS endpoint (`/.well-known/jwks.json`).
3. **Voice-app verifies CRM-issued JWTs** by fetching JWKS, checking signature, validating standard claims (`iss`, `aud`, `exp`), and reading domain claims (`tenantId`, `role`, `isInternalStaff`).
4. **CRM exposes a "Voice Assistant" entry point** that links to `voice.4trades.io/?token=<jwt>` (or a more sophisticated SSO flow if we want to avoid token-in-URL). Voice-app reads the token, establishes a session, and redirects to a clean URL.
5. **Standalone customers** sign up at `voice.4trades.io` directly. Voice-app mints its own JWTs in the same shape (different `iss` claim).
6. **Voice-app pipelines that need to write CRM artifacts** call 4tradesCRM's REST API using the user's JWT for authorization (or a service account token for system-level writes).
7. **Pipeline definitions declare CRM-integration requirements** so a pipeline can be marked "requires CRM Lead-write API" and standalone customers without a CRM connection get a clear "this pipeline is unavailable in standalone mode" message rather than a runtime failure.

**Key reason it wins:** scales gracefully across all three deployment scenarios with the same architecture, generalizes to future third-party CRMs, treats voice-app as a real product with independent evolution.

**Main risk we're accepting:** Users clicking from CRM into voice-app navigate to a different subdomain. Mitigation: subdomain on shared root domain (looks like one company's product), shared visual branding, persistent session, prominent "back to CRM" affordance. We accept that this UX is slightly less seamless than B's iframe — and we get back the iframe complexity tax we'd otherwise pay for the rest of the product's life.

**Secondary risk:** Token-in-URL pattern for the initial SSO handshake has security implications (URLs get logged, copied, leaked). Mitigation: use a short-lived (≤30s) one-time code rather than a full JWT in the URL; voice-app exchanges the code for the JWT via a server-to-server call. This is a small implementation detail to nail but well-precedented (OAuth Authorization Code flow does this).

## Decision

> **Generalized 2026-04-28** after the headless-backend reframe surfaced multiple v1 consumers (4tradesCRM + marketing app) and additional future consumers (third-party CRMs, e.g., the "Mass provider" Doug mentioned). Original framing was "CRM-integrated voice-app." Generalized framing is **consuming-app pattern** — voice-app is a headless backend service; multiple consuming apps subscribe via integration contracts (per [020](020-integration-contracts.md)). 4tradesCRM is the v1 CRM consumer; marketing app is the v1 marketing consumer; pattern extends generically.

**Option A — Loose federation (own domain, JWT pass-through, REST integration).** Decided 2026-04-28.

- Voice-app deployed at its own subdomain on the shared root (e.g., `voice.4trades.io` — exact subdomain TBD).
- 4tradesCRM upgrades JWT signing from HS256 (shared secret) to RS256 (asymmetric) and exposes a JWKS endpoint at `/.well-known/jwks.json`. This is a one-time CRM-side change.
- Voice-app verifies CRM-issued JWTs via JWKS (signature + standard claims `iss`/`aud`/`exp` + domain claims `tenantId`/`role`/`isInternalStaff`).
- CRM exposes a "Voice Assistant" entry point that does a short-lived (≤30s) one-time-code SSO handshake — no raw token-in-URL. Voice-app exchanges the code for a JWT via server-to-server call. Standard OAuth Authorization Code pattern.
- Standalone customers sign up directly at voice-app's domain. Voice-app mints its own JWTs in the same shape (different `iss` claim).
- Voice-app pipelines emit outputs to consuming apps via outbound webhooks per [020](020-integration-contracts.md). 4tradesCRM is the v1 CRM consumer; marketing app is the v1 marketing consumer. Each output kind maps to a destination configured per tenant.
- Pipeline definitions (per [015](015-pipeline-definition-format.md)) declare per-output `kind` and stakes. An output kind without a configured destination produces a clear "destination not configured" error rather than failing at runtime.

> **Amended 2026-04-28**: original line said "voice-app calls 4tradesCRM's REST API for Lead/Contact writes." That was a 4tradesCRM-specific shortcut. After the multi-consumer reframe, the general pattern is **outbound webhooks** to consuming apps (per 020). 4tradesCRM may still expose REST endpoints for some specific operations (e.g., looking up a project list), but the canonical *output delivery* pattern is webhooks.

## Consequences

**Locks in:**
- Voice-app is its own product with its own domain, deploy, and brand. Independent evolution from 4tradesCRM.
- Federation protocol is RS256/JWKS-verified JWTs. Generalizes to multiple trusted issuers (4tradesCRM in v1; future third-party CRMs added by registering their JWKS endpoint).
- Voice-app's auth layer must support two issuance paths: (a) verify externally-issued JWTs from trusted issuers, (b) mint its own JWTs for standalone customers. Both paths produce JWTs in the same shape.
- 4tradesCRM-side work is required: HS256 → RS256 migration, JWKS endpoint exposure, "Voice Assistant" entry point with one-time-code flow, REST API surface audit for Lead/Contact/follow-up-task writes (some endpoints may need to exist or be expanded).
- Pipeline definition format must declare CRM-integration requirements as a first-class field.
- Voice-app maintains a `crm_artifacts` (or similar) table that records "we created CRM Lead X for transcript Y" for traceability across the integration boundary. This is voice-app's source of truth for "what did I do in the CRM"; the CRM's DB is the source of truth for the artifacts themselves.

**Creates / constrains follow-up decisions:**
- **Q11 (auth provider)** — answer is now scoped: a custom JWT verifier (RS256/JWKS) for federated CRM tokens, plus a standalone sign-up layer (Supabase Auth, Lucia, Auth.js, or Clerk for the standalone customers). Both paths must produce same-shape JWTs.
- **Q12 (hosting / deployment)** — voice-app deploys to its own subdomain on the shared `4trades.io` root. CORS/CSRF policies must permit cross-subdomain JWT exchange and the one-time-code handshake.
- **Q13 (email ingestion vendor)** — independent of integration shape; voice-app handles its own ingestion regardless of whether the user is CRM-integrated or standalone.
- **Q14 (transcript source adapter)** — voice-app may consume from 4tradesCRM's existing voice-capture path as one source adapter (CRM already has Whisper-based file upload). Transcript-source adapter interface must support both "Plaud email ingestion" and "CRM voice-capture handoff" cleanly.
- **Q16 (pipeline definition format)** — must include `requires_crm_integration: bool` (or richer declaration of which CRM APIs the pipeline depends on) so pipelines fail fast in standalone mode rather than at runtime.

**4tradesCRM-side work added (not part of this repo, tracked separately):**
- Migrate JWT signing from HS256 to RS256, generate keypair, secure private key.
- Expose JWKS endpoint at `/.well-known/jwks.json`.
- Add "Voice Assistant" entry point in CRM UI (link/button) that does one-time-code SSO handshake to voice-app.
- Audit/expand REST API surface for the Lead/Contact/follow-up-task writes voice-app's pipelines will perform.
- Optionally: shared design tokens / brand assets package consumed by both products for visual consistency.

**Risks accepted:**
- Subdomain navigation feels less seamless than iframe embedding. Mitigation: shared brand, persistent session, prominent "back to CRM" link on voice-app pages, smooth one-time-code SSO handshake. We accept this small UX cost in exchange for not paying iframe complexity tax for the rest of the product's life.
- One-time-code SSO handshake adds a small implementation detail (server-to-server code exchange endpoint). Mitigation: well-precedented OAuth pattern; libraries available; bounded one-time engineering cost.
- HS256 → RS256 migration on the CRM side is real work and a security-sensitive change. Mitigation: standard pattern; can be done with a short transition window where both signing methods are accepted; all existing CRM clients re-authenticate.
- 4tradesCRM REST API may not currently expose all the write endpoints voice-app pipelines need. Mitigation: Q14 (and some pipeline-design work) will surface specific gaps; CRM API additions are bounded incremental work, not architectural.
