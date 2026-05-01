---
number: 014
title: LLM provider strategy
status: accepted
date: 2026-04-28
---

# 014 — LLM provider strategy

**Status:** accepted
**Date:** 2026-04-28

## Question

How does voice-app call LLMs? Two interrelated sub-questions:

1. **Abstraction layer.** Use the Vercel AI SDK (provider-neutral, deep Next.js integration), call provider SDKs directly behind a thin `LLMService`, or route through a gateway like OpenRouter?
2. **Provider strategy.** Doug's stated prior: OpenAI (ChatGPT family) primary, Anthropic (Claude family) fallback, motivated by cost. What triggers fallback — errors only, cost thresholds, latency?

V1 ingests text only per [013](013-transcript-source-adapter.md), so no ASR provider is in scope. Fine-tuning is deferred to v2 per [002](002-learning-model-and-feedback-architecture.md). The question is purely about how the runtime LLM calls are wired.

## Why this matters now

Pipelines call LLMs for routing, drafting, retrieval-augmented generation, and structured output extraction. If every pipeline step calls `openai.chat.completions.create()` directly, then the eventual fallback wiring, cost monitoring, and provider migration become a refactor of every step. If we wire abstraction correctly from day one, swapping provider or adding fallback is a config change.

The choice also affects:
- **Q16 (pipeline definition format)** — pipeline steps that need LLM calls go through whatever abstraction we pick.
- **Q19 (observability)** — token usage, latency, and cost per provider need to be measurable.
- **Q24 (compliance)** — provider data-handling policies differ; multi-provider design forces a "which provider sees what data" question.

## Options

### Option A — Vercel AI SDK with OpenAI primary + Anthropic fallback

Use the Vercel AI SDK (`ai` package) as the abstraction layer. It's provider-neutral with first-class support for OpenAI, Anthropic, Google, Groq, and others. Deep Next.js integration: streaming, structured output, tool use, React Server Components support. Built by the same team as Vercel and Next.js. v1 wires OpenAI as primary with an Anthropic fallback path.

**Steel-manned reasoning:** The Vercel AI SDK is the canonical LLM abstraction for Next.js + Vercel stacks in 2026. Provider-neutral by design — `generateText({ model: openai('gpt-4.1') })` becomes `generateText({ model: anthropic('claude-sonnet-4-6') })` with a one-line change. Built-in support for streaming responses (relevant if dashboard ever needs streaming UX), structured output via Zod schemas (heavily used by pipeline steps that extract typed data), tool use, and prompt caching where supported. Fallback patterns are well-documented: try the primary provider; on rate-limit or 5xx, fall back to secondary. The integration with Next.js Server Actions and Server Components is tighter than any direct-SDK approach. For solo dev productivity, the SDK eliminates significant boilerplate per pipeline step.

**Priors / assumptions this rests on:**
- Vercel AI SDK is the canonical LLM abstraction in the Vercel/Next.js ecosystem in 2026 — confidence: **high**
- Streaming + structured output + tool use are needs that will materialize in v1 pipelines — confidence: **high** (structured output for sure; streaming for any dashboard live-updates)
- Provider-neutral abstraction allows clean fallback wiring — confidence: **high**
- Cost overhead of the abstraction layer (vs. direct SDK calls) is negligible — confidence: **high**
- Vercel AI SDK keeps pace with new provider features (caching, MCP, etc.) — confidence: **medium-high** (so far excellent track record)

### Option B — Direct provider SDKs with custom `LLMService` wrapper

Write our own `LLMService` abstraction that wraps OpenAI's SDK and Anthropic's SDK directly. Custom interface tailored to our needs — no "second hand" through Vercel's library.

**Steel-manned reasoning:** Maximum control. We know exactly what every call does because every line of integration is ours. No risk of the abstraction layer making opinionated choices we disagree with. Direct SDKs have the deepest provider-specific feature support. For cost-sensitive workloads, owning the integration means we can tune token usage, caching, and retry semantics exactly.

**Priors / assumptions this rests on:**
- Vercel AI SDK introduces meaningful overhead or constraint — confidence: **low** (it's mostly thin; the few opinionated bits are easily overridden)
- Custom wrapper is bounded engineering effort vs. Vercel AI SDK adoption — confidence: **low** (real ongoing maintenance: track API changes across two providers, add features as they ship)
- Provider-specific features we need aren't covered by Vercel AI SDK — confidence: **low** (the SDK exposes provider-specific options as escape hatches)
- Solo dev productivity is comparable — confidence: **low** (Vercel AI SDK saves meaningful boilerplate)

### Option C — OpenAI only in v1; add Anthropic when actually needed

Skip the abstraction layer entirely in v1. Call OpenAI's SDK directly. Add Anthropic and a thin abstraction when a real cost-driven need surfaces (e.g., "GPT-4 cost is hurting us; let's route some calls to Claude Haiku").

**Steel-manned reasoning:** YAGNI. Doug's stated prior is "OpenAI primary, Anthropic fallback" but the fallback isn't actually wired up at v1 — it's a hedge for a future cost concern. Building abstraction infrastructure for a fallback that may or may not fire is the textbook YAGNI mistake. v1 with OpenAI direct is simpler, has fewer dependencies, fewer abstraction layers, and ships faster. When the cost concern materializes (real bill data), we add the abstraction with evidence.

**Priors / assumptions this rests on:**
- The fallback to Anthropic is unlikely to be needed in v1 — confidence: **medium** (cost concerns scale with traffic; v1 has minimal traffic)
- Refactoring direct SDK calls into an abstraction later is bounded — confidence: **medium** (true if the LLM call sites are few; gets harder with more pipelines)
- Solo dev productivity is higher without an abstraction — confidence: **low-medium** (true initially; pays back the moment fallback or provider swap is needed)
- Vercel AI SDK has meaningful overhead vs. raw OpenAI SDK — confidence: **very low** (it doesn't)

### Option D — OpenRouter (or similar gateway)

Route all LLM calls through OpenRouter, a unified API that fronts dozens of providers. Single API key, single billing surface, single integration.

**Steel-manned reasoning:** Simplest possible multi-provider story. OpenRouter handles the provider abstraction at the network layer. One API to integrate, one set of credentials, one billing dashboard. Adding a new provider is a model-name change. Provides usage analytics, fallback policies, and cost optimization out of the box.

**Priors / assumptions this rests on:**
- OpenRouter's reliability + latency is acceptable for production — confidence: **medium-low** (extra hop adds latency; dependence on a smaller vendor)
- The single-API simplification is worth giving up direct provider relationships — confidence: **low-medium** (loses access to provider-specific features that ship before OpenRouter exposes them; loses provider-specific cost optimizations)
- OpenRouter pricing is competitive with direct provider rates — confidence: **medium-low** (small markup is normal for gateways)
- Vendor risk is acceptable — confidence: **low** (smaller vendor than the providers themselves; outage risk concentrated)

## Recommendation

**Option A — Vercel AI SDK with OpenAI primary + Anthropic fallback.**

The SDK is the canonical LLM abstraction for our stack. Built by the same team as Vercel and Next.js, deeply integrated, provider-neutral, with first-class support for the patterns we'll actually use (streaming for any future dashboard live-update views, structured output via Zod for pipeline steps that extract typed data, tool use for pipelines that call external APIs, prompt caching where supported). Provider switching is a one-line change. Fallback wiring is documented and bounded.

Option B (direct SDKs + custom wrapper) commits us to ongoing maintenance of an abstraction we'd rebuild anyway with significantly less leverage than the SDK. Option C (OpenAI only, no abstraction) is YAGNI taken too far given that we already know we want fallback wired in — Doug's stated prior. Option D (OpenRouter) trades direct provider relationships for a gateway whose reliability and latency are extra dependencies we don't need.

**Concrete v1 mechanics:**

1. **Vercel AI SDK installed.** `ai` package + `@ai-sdk/openai` + `@ai-sdk/anthropic`.
2. **`lib/llm/client.ts`** — thin wrapper that selects model and provider via config. Default: OpenAI's GPT-4.1 (or current best mid-tier model in 2026); fallback: Anthropic's Claude Sonnet-4 (matching tier).
3. **Fallback semantics for v1: error-based.** If primary returns 429 (rate limit), 503 (service unavailable), or transient 5xx, retry on the fallback provider. Permanent errors (400, 401) propagate. Token-usage limits and cost-based fallback are deferred until real bill data exists.
4. **All LLM calls go through `lib/llm/client.ts`.** Pipelines do not import provider SDKs directly. This makes provider migration, model swaps, and observability instrumentation single-edit changes.
5. **Token usage tracked per call.** Logged with `tenantId`, `pipeline`, `step`, `model`, `inputTokens`, `outputTokens`. Pairs with Q19 observability.
6. **Per-pipeline-step model selection.** Each pipeline step declares which model tier it needs (cheap-and-fast for routing/classification; high-quality for drafting). The client respects that.
7. **Cost-based fallback deferred.** When real cost data shows it's worth it (likely v1.x or v2 once we have ~30 days of bill data), add a token-budget tracker that routes to the cheaper provider when the daily budget is exceeded. Don't build it speculatively.

**Key reason it wins:** zero-cost provider abstraction, deep Next.js integration, single edit to swap providers or add fallback policies, mature ecosystem, no maintenance overhead beyond the dependency itself.

**Main risks accepted:**
- Lock-in to Vercel's SDK as the abstraction layer. Mitigation: it's open source, provider-neutral, and pipeline code can move to a different abstraction with bounded effort if Vercel's SDK ever stagnates.
- Anthropic fallback is wired but rarely exercised in v1 (low traffic = rare rate limits). Mitigation: ship with it anyway; small ongoing cost; high marginal value when cost-based fallback gets added later.

## Decision

**Option A — Vercel AI SDK with OpenAI primary + Anthropic fallback.** Decided 2026-04-28.

`ai` + `@ai-sdk/openai` + `@ai-sdk/anthropic` packages. All LLM calls flow through `lib/llm/client.ts`. Error-based fallback in v1 (rate-limit / 5xx triggers retry on Anthropic). Cost-based fallback deferred until real bill data exists.

## Consequences

**Locks in:**
- Vercel AI SDK as the LLM abstraction layer. No direct provider SDK imports in pipeline code.
- OpenAI is the default v1 provider; Anthropic is the fallback.
- Per-pipeline-step model tier selection (cheap-and-fast for routing/classification; high-quality for drafting). Each step explicitly declares which tier it needs.
- Token usage logged per call (`tenantId`, `pipeline`, `step`, `model`, `inputTokens`, `outputTokens`). Pairs with Q19 observability.
- Structured output via Zod schemas is the canonical pattern for typed pipeline-step outputs.

**Creates / constrains follow-up decisions:**
- **Q16 (pipeline definition format)** — pipeline steps that need LLM calls go through `lib/llm/client.ts`.
- **Q19 (observability)** — must surface token-usage and per-provider cost metrics.

**Risks accepted:**
- Vercel AI SDK lock-in. Mitigation: open source, provider-neutral, bounded migration if SDK stagnates.
- Anthropic fallback rarely exercised in v1 (low traffic = rare rate limits). Mitigation: ship with it anyway; small ongoing maintenance cost; high marginal value when cost-based fallback is added later.

**Deferred:**
- Cost-based fallback policy (token-budget tracker that routes to cheaper provider when daily budget exceeded). Add when real bill data exists, likely v1.x or v2.
