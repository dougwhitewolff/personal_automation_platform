# Vision

## What we're building

A personal AI assistant — initially for the author, ultimately a product — that turns voice transcripts into executed work. You record a thought on a Plaud device, it shows up as a transcript, the system identifies what kind of task it is, and routes it through the appropriate pipeline (which may itself fan out into many sub-tasks).

The phrase that captures it: *"a personal assistant in your pocket."*

## Core mental model

```
voice recording
    ↓ (Plaud device)
transcript
    ↓ (Plaud API → eventually; email attachment → for now)
ingestion layer
    ↓ (keyword routing)
task pipeline (single-use per transcript, for now)
    ↓ (durable workflow execution)
outcomes (calls made, docs drafted, calendar events created, messages sent, etc.)
```

## Non-negotiables

1. **Plaud API ready.** Email ingestion is a workaround. The system must be designed so that swapping email-attachment ingestion for the Plaud API is an adapter swap, not a refactor. The ingestion layer is an interface; email and Plaud are implementations.

2. **Productizable from day one.** Even though v1 will likely have one user (the author), the data model, auth boundaries, and workflow engine choice should not require a rewrite to support a second user. Multi-tenancy is foundational; billing and onboarding polish are deferred.

3. **Durable, not best-effort.** Pipelines may take minutes or hours, may call external APIs that fail, may need retries. An in-process scheduler (the old system's approach) is not acceptable. A real workflow engine is required.

4. **Single-use transcripts (for now).** Each transcript maps to exactly one task pipeline. Multi-pipeline routing per transcript is a future concern and should not complicate v1.

## What we explicitly are NOT building (yet)

- Multi-pipeline routing per transcript
- Real-time conversational interface (the assistant runs asynchronously on transcripts)
- Mobile app (until we know the right surface)
- A polished SaaS onboarding flow
- Custom ML models — all intelligence is via API calls to frontier LLMs

## Why we wiped the previous code

The legacy Python prototype was built around assumptions that no longer hold:

- **Limitless-first.** We're switching to Plaud.
- **Single-user, single-process.** Won't scale or productize.
- **Modules (sleep/nutrition/workout/health) were the product.** They're not — those were experiments. The *platform* is the product, and pipelines are user-defined or app-defined, not hardcoded.
- **Python.** Acceptable for a prototype, suboptimal for a product that needs durable workflows, strong typing across many integrations, and a long-lived hosted service.

The legacy code is preserved on the `legacy-python-v1` tag and branch. We do not expect to port any of it directly, but a few prompts or schemas may be useful reference.

## North-star use case (for design pressure)

The author records: *"Remind me to follow up with Sarah about the Q3 planning doc next Tuesday, and pull together the latest revenue numbers so I can compare them to what she said in our last call."*

The system should:
1. Receive the transcript.
2. Identify this as a "follow-up with prep" pipeline.
3. Create a calendar reminder for Tuesday.
4. Search prior transcripts/notes for "Sarah" + "Q3 planning" context.
5. Pull revenue numbers from a connected data source.
6. Draft a comparison doc.
7. Surface the result before Tuesday's reminder fires.

If the architecture can't gracefully express that flow, it's the wrong architecture.
