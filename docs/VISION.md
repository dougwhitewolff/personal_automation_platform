# Vision

Build a shared automation service that gives our apps a common AI/workflow layer instead of making every product reinvent ingestion, prompting, review, execution, and audit.

The service should feel boring in the right places: tenant-aware, durable, observable, idempotent, and explicit about what it is allowed to do. The intelligence can evolve, but the service contract should stay stable enough that the CRM, Mason, and future tools can depend on it.

## Mental Model

```
external signal or app request
    -> ingestion adapter
    -> normalized capture/event
    -> parser/classifier/workflow
    -> review or auto-approved action
    -> app adapter
    -> client app outcome
```

## First Consumers

CRM:

- Plaud voice captures become reviewed CRM actions.
- Later workflows may support email/calendar context, follow-ups, task creation, customer updates, and lead enrichment.

Mason trades marketing generator:

- Business, trade, project, and customer context becomes marketing drafts.
- Drafts can be reviewed, revised, approved, and reused across channels.

Future apps and tools:

- Any app can submit a structured automation request and receive status, results, and audit history.

## Principles

1. **Service first, app aware.** The core service owns reusable automation primitives. App-specific behavior lives in adapters.
2. **Tenant boundaries from day one.** Every event, workflow, review item, setting, and action is tenant-scoped.
3. **Human review where trust is not earned.** Low-confidence or high-impact actions go to review before commit.
4. **Durable, not best-effort.** Workflows need retries, idempotency, and audit trails.
5. **No raw content dumping.** Captured content is parsed, summarized, and transformed before it becomes an app record.
6. **Integrations are replaceable.** Plaud email ingestion is one adapter; future Plaud API support should not require a rewrite.

## First North-Star Workflow

A field user records a site visit on Plaud. Plaud emails the transcript to a dedicated email account. The service detects the email, parses the useful content, creates a capture event, routes it to review, and sends the confirmed action to the CRM as a lead note, task, new lead, or lead update.

That workflow is intentionally narrow. It proves the service primitives we will need everywhere else: ingestion, parsing, review, tenant config, workflow state, audit, and app action execution.
