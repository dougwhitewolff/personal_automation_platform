# Personal Automation Platform

A personal AI assistant designed to ingest voice transcripts, route them through task pipelines via keyword matching, and act as a productized "assistant in your pocket."

## Status: Greenfield rewrite (started 2026-04-28)

The previous Python implementation has been wiped from `main`. It is preserved at:
- Git tag: `legacy-python-v1`
- Git branch: `legacy-python-v1`

To inspect the legacy code: `git checkout legacy-python-v1`

## Why the rewrite

The old system was a single-user Python prototype built around the Limitless API, an in-process scheduler, a Discord bot, and a handful of health/nutrition/sleep modules. None of that is central to the new direction:

1. **Switching transcript source from Limitless to Plaud.** Plaud has not yet released their API, so email-with-attachment ingestion is a temporary workaround that will be swapped for the Plaud API when available.
2. **Designed to productize and scale**, not a personal toy. Multi-tenancy, durable workflows, auth, and billing are first-class concerns from the start (though some are deferred until v1 of the assistant works for one real user — likely the author).
3. **Stack change** away from Python toward something better suited to a long-running, IO-heavy AI orchestration product with a strong SDK ecosystem.

## What this repo will become

- A multi-tenant backend that ingests voice transcripts (email attachment now, Plaud API later)
- A keyword-routed pipeline engine that treats each transcript as single-use input to one task pipeline
- A durable job/workflow layer that can fan out to many tasks per transcript
- An LLM orchestration layer (Anthropic primary) for understanding transcripts and driving pipelines
- User-facing surfaces (TBD during planning — web, mobile, Discord, voice are all candidates)

The full product specification will be developed in [docs/PRD.md](docs/PRD.md) through a structured planning session captured in [docs/decisions/](docs/decisions/).

## Documentation

- [docs/VISION.md](docs/VISION.md) — north star, product framing, what we're building and why
- [docs/PRD.md](docs/PRD.md) — the consolidated product requirements document (filled in during planning)
- [docs/decisions/INDEX.md](docs/decisions/INDEX.md) — running list of architecture/product decisions
- [docs/decisions/000-template.md](docs/decisions/000-template.md) — format used for each decision

## How to resume planning in a new chat

Open a new Claude Code session in this repo and say: *"Resume the PRD planning session. Read docs/VISION.md, docs/PRD.md, and docs/decisions/INDEX.md for context, then continue from the next unanswered question."*

The decision docs are designed to be self-contained: each one captures the question, options considered, steel-manned reasoning, priors on assumptions, recommendation, and final choice — so a fresh session can pick up exactly where the previous one left off.
