# Decision Index

Running list of architecture and product decisions. Each entry is a self-contained doc capturing the question, options, reasoning, priors, recommendation, and final choice.

## Format

See [000-template.md](000-template.md).

## Decisions

| #   | Title | Status | Date |
|-----|-------|--------|------|
| 000 | Template | template | 2026-04-28 |

## Planning queue

Questions to work through, in roughly the order they should be resolved (later questions often depend on earlier ones):

1. **Target user & v1 scope** — who is v1 for, what does "done" mean for v1?
2. **Primary user surface** — how does the user interact with the assistant (web, Discord, mobile, voice, multi)?
3. **Language / runtime** — TypeScript on Node, TypeScript on Bun, Go, something else?
4. **Backend framework** — Hono, Fastify, NestJS, Next.js API routes, etc.
5. **Workflow / job engine** — Inngest, Temporal, Trigger.dev, Hatchet, BullMQ, roll-our-own?
6. **Primary database** — Supabase, Neon, Railway PG, self-hosted, etc.
7. **Vector store** — pgvector, Turbopuffer, Pinecone, etc.
8. **Multi-tenancy model** — RLS in Postgres, app-layer enforcement, schema-per-tenant?
9. **Auth provider** — Clerk, WorkOS, Supabase Auth, custom?
10. **Hosting / deployment** — Fly.io, Railway, Vercel, AWS, etc.
11. **Email ingestion vendor** — Postmark, AWS SES, SendGrid, Mailgun?
12. **Transcript source adapter interface** — shape of the abstraction so Plaud API drops in cleanly.
13. **LLM provider strategy** — Anthropic only, multi-provider abstraction, when to introduce one?
14. **Pipeline definition format** — code, declarative config, hybrid?
15. **Keyword routing strategy** — exact match, embedding similarity, LLM classifier, hybrid?
16. **Memory / retrieval strategy** — what does the assistant remember across transcripts?
17. **Repo structure** — monorepo (pnpm + turbo) vs. single package?
18. **Observability stack** — Sentry, Axiom, OTEL, Datadog, etc.
19. **Secrets management** — Doppler, 1Password, env files, cloud-native?
20. **CI/CD** — GitHub Actions baseline, anything else?
21. **When to wire in billing** — never (personal), v1, post-validation?
22. **Compliance posture** — audio is PII; what's the retention/storage policy?

This list will be refined as decisions are made — some questions will spawn sub-questions, others may be merged or deferred.
