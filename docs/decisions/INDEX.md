# Decision Index

Running list of architecture and product decisions. Each entry is a self-contained doc capturing the question, options, reasoning, priors, recommendation, and final choice.

## Format

See [000-template.md](000-template.md).

## Decisions

| #   | Title | Status | Date |
|-----|-------|--------|------|
| 000 | Template | template | 2026-04-28 |
| 001 | _(unused - number reserved or skipped)_ | - | - |
| 002 | Service stack | accepted | 2026-05-01 |
| 003 | Repo structure | accepted | 2026-05-01 |
| 004 | Multi-tenancy model | accepted | 2026-05-01 |
| 005 | Auth and service access | accepted | 2026-05-01 |
| 006 | Mailbox ingestion implementation | deferred | - |

## Open Decisions

Questions to resolve as implementation gets closer. Later questions may depend on earlier ones. Categorized by handoff impact; see `DEV_HANDOFF_PRD.md` section 15 for the same split with full rationale.

### Needed before final parser behavior

1. **Plaud email format spec + sample fixtures** - real example Plaud emails (PII scrubbed) under `docs/fixtures/plaud/` plus section 7.3 in the PRD describing the format. Product owner will provide an email to Faiyaz when needed.
2. **Mailbox ingestion implementation** - default dev mailbox is `doug@4trades.ai`; final access mechanism can be chosen during implementation and isolated behind the ingestion adapter.

### Resolvable during scaffold (defaults set in PRD section 15.2)

3. **Validation library** - default: Zod.
4. **Testing library** - default: Vitest.
5. **Review surface for Slice 1** - default: REST endpoints on the service.
6. **API key issuance flow for Slice 1** - default: `prisma db seed` + `pnpm key:create` CLI script.

### Genuinely deferable

7. **CRM adapter contract** - exact API endpoints/events the CRM exposes for confirmed actions.
8. **Deployment target** - Fly.io, Railway, Render, AWS, Azure, or another target.
9. **Retention policy** - how long raw emails/transcripts, summaries, review items, and audit records are retained.
10. **LLM provider strategy** - OpenAI only, Anthropic only, or multi-provider abstraction for Slice 2.
11. **Observability, secrets, and CI/CD** - baseline operational tooling for the first deployable service.

This list will be refined as decisions are made. Some questions will spawn sub-questions; others may be merged or deferred.
