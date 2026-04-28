# Product Requirements Document

**Status:** In planning. This document is filled in incrementally as decisions are resolved in [decisions/](decisions/).

## How to read this doc

Each section below corresponds to a decision area. When a decision is made, this PRD records the *outcome* (what we're building), and the corresponding `decisions/NNN-*.md` file records the *reasoning* (why we chose it, what we considered, what assumptions we're making).

Sections marked **[PENDING]** have not been resolved yet.

---

## 1. Product framing
- [PENDING] Target user & v1 scope
- [PENDING] Primary user surface(s)

## 2. Architecture foundations
- [PENDING] Language / runtime
- [PENDING] Backend framework
- [PENDING] Repo structure (monorepo vs. single package)
- [PENDING] Hosting / deployment target

## 3. Data layer
- [PENDING] Primary database
- [PENDING] Vector store
- [PENDING] Multi-tenancy model

## 4. Workflow & pipelines
- [PENDING] Workflow / job engine
- [PENDING] Pipeline definition format (code, config, both)
- [PENDING] Keyword routing strategy

## 5. Ingestion
- [PENDING] Email ingestion vendor (workaround layer)
- [PENDING] Transcript source adapter interface (Plaud-ready)

## 6. Intelligence
- [PENDING] LLM provider strategy (Anthropic primary, multi-provider abstraction?)
- [PENDING] Prompt / context management approach
- [PENDING] Memory / retrieval strategy

## 7. Auth & identity
- [PENDING] Auth provider
- [PENDING] When to wire in auth (v1 vs. later)

## 8. Operations
- [PENDING] Observability stack
- [PENDING] Secrets management
- [PENDING] CI/CD

## 9. Productization
- [PENDING] Billing — when and how
- [PENDING] Admin / support tooling
- [PENDING] Compliance posture (PII, audio data, retention)

---

## Out-of-scope for v1

(Recorded as decisions are made — this section captures things we explicitly chose NOT to build now.)
