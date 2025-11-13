**Limitless Pendant Automations -- Product Definition v1.0 *()***

# 0. Overview

## 0.1 Problem Statement

Users wearing the Limitless Pendant generate continuous voice data, but
there is no unified, reliable mechanism to transform those recordings
into structured, actionable automations.\
The current Limitless API provides transcripts, yet downstream workflows
must manually interpret and act on them.\
This subsystem solves that gap by providing a single, canonical trigger
phrase ("Log that") and a reliable automation pipeline that converts
tagged speech into verified actions and logs.

## 0.2 Primary Users and Use Cases

**Users:**

- Individuals using the Limitless Pendant to capture personal context.

- Developers extending the Personal Automation Platform with new
  modules.

**Core Use Cases:**

1.  User says "Log that" after describing a meal or workout →
    corresponding module logs structured data.

2.  User uploads an image (e.g., Peloton screen, meal) → correct module
    extracts metrics and confirms in Discord.

3.  User asks natural questions ("How much protein today?") → system
    retrieves and summarizes from stored data.

4.  System posts automatic daily summaries and reminders.

------------------------------------------------------------------------

# 1. Goals and Non-Goals

## 1.1 Goals

- Provide a **single verbal entry point** ("Log that") for all
  automations.

- Enable **semantic routing** that classifies user intent and dispatches
  to the correct module.

- Guarantee **auditable reliability** with dual evidence (system + human
  visible).

- Maintain **consistent data schema** across modules for analytics and
  future scaling.

- Achieve **real-time behavior** within one polling interval after a
  lifelog appears.

- Deliver confirmations and summaries through Discord as the unified
  user interface.

## 1.2 Non-Goals

- Passive background inference or unsolicited actions.

- Integration with third-party CRMs or external data warehouses in v1.0.

- Long-term analytics dashboards beyond daily summaries.

- Voice feedback playback through the pendant (future consideration).

------------------------------------------------------------------------

# 2. Key User Stories and Acceptance Criteria

  ------------------------------------------------------------------------------
  **\#**   **User Story**              **Acceptance Criteria**
  -------- --------------------------- -----------------------------------------
  1        As a user, when I say "Log  Routing accuracy ≥ 95 %. Logs include
           that," the system detects   lifelog_id and module name.
           the tag and routes to the   
           correct module.             

  2        As a user, I want every     Confirmation posted ≤ 15 s P95 after
           successful automation to    speech end; message links to evidence
           appear as a confirmation in record.
           Discord.                    

  3        As a developer, I need      Documents contain lifelog_id, timestamp,
           every module write to       module, processed_by, source,
           follow a common Mongo       metadata.schema_version and
           schema.                     metadata.hash.

  4        As a user, I want the       Polling resumes and catches up ≤ one
           system to recover           interval (2 s).
           automatically if polling is 
           interrupted.                

  5        As an admin, I want         100 % of records link to a lifelog_id and
           traceable evidence for each Discord message id.
           automation.                 

  6        As a developer, I need      Poll start, detection, routing, write,
           reliable timing metrics for and Discord post times logged for every
           optimization.               entry.
  ------------------------------------------------------------------------------

------------------------------------------------------------------------

# 3. High-Level Requirements

## 3.1 Functional Requirements

1.  Poll Limitless API every 2 seconds (configurable).

2.  Detect canonical phrase "Log that."

3.  Perform semantic routing via Automation Orchestrator and
    ModuleRegistry.

4.  Execute selected Module's handle_log or handle_image methods.

5.  Persist results in MongoDB following shared schema.

6.  Post confirmation to Discord and store evidence document.

7.  Run scheduled tasks and summaries via Scheduler.

## 3.2 Non-Functional Requirements

- **Uptime:** ≥ 99.9 %.

- **Processing Latency:** ≤ 2 s from lifelog detection to DB write.

- **End-to-End Latency:** ≤ 15 s P95 (speech → Discord).

- **Data Integrity:** 100 % atomic and idempotent writes.

- **Routing Accuracy:** ≥ 95 %.

- **Audit Completeness:** 100 % traceable records.

------------------------------------------------------------------------

# 4. Release Criteria and Milestones

  ------------------------------------------------------------------------
  **Phase**         **Objective**            **Milestone Definition**
  ----------------- ------------------------ -----------------------------
  M0 --             Limitless polling, Mongo All core services
  Infrastructure    schema, Discord bot      operational; test lifelog
                    running.                 processed end-to-end.

  M1 -- Core        Nutrition and Workout    Both modules respond to "Log
  Modules           automations active.      that" and log structured
                                             records.

  M2 -- Reliability Instrumentation and      Telemetry captures timing
  Metrics           error recovery           metrics; system recovers from
                    validated.               restart without loss.

  M3 -- Audit and   Evidence logging and     Evidence records link to
  Summary           daily summaries          Discord messages; scheduler
                    complete.                delivers summary.

  M4 -- Empirical   Measure actual Limitless Publish observed P95
  Latency Benchmark update cadence.          speech-to-confirmation
                                             latency and revise targets.
  ------------------------------------------------------------------------

------------------------------------------------------------------------

# 5. Risks and Open Questions

  -----------------------------------------------------------------------
  **Risk / Question**      **Mitigation / Owner**
  ------------------------ ----------------------------------------------
  Unverified Limitless API Collect production telemetry; refine latency
  posting delay            targets after benchmark. -- Engineering Lead

  AI routing               Expand training samples and prompt tests per
  misclassification \< 95  module. -- AI Engineer
  %                        

  Mongo schema drift       Centralize schema contract in shared library.
  between modules          -- Backend Lead

  Discord API rate limits  Batch messages or apply back-off retry. -- Bot
                           Maintainer

  Service restart during   Persist last_processed timestamp and replay
  polling                  gap. -- Infrastructure Engineer
  -----------------------------------------------------------------------

# 6. Dependencies and Timeline

**Dependencies:**

- Limitless API access and stable poll endpoints.

- OpenAI API for semantic routing and extraction.

- Discord bot permissions and webhook URLs.

- MongoDB instance with reliable persistence layer.

**Indicative Timeline:**

  ----------------------------------------------------
  **Month**   **Deliverable**
  ----------- ----------------------------------------
  Month 1     M0--M1 core pipeline and two modules
              operational.

  Month 2     Instrumentation and evidence logging
              (M2).

  Month 3     Full reliability benchmarks and report
              (M3--M4).
  ----------------------------------------------------

------------------------------------------------------------------------

# 7. Decision Log

  -----------------------------------------------------------------------
  **Decision**                  **Rationale**
  ----------------------------- -----------------------------------------
  Canonical voice tag = "Log    Ensures user consistency and predictable
  that."                        routing.

  Semantic Routing Model via    Supports modular extensibility and
  Automation Orchestrator.      context-aware intent classification.

  MongoDB as primary DB.        Document model fits variable module
                                schemas and scales for future analytics.

  Discord as user interface.    Single confirmation and summary surface
                                for all automations.

  Reliability First metrics and Measurable accountability for both humans
  dual evidence framework.      and systems.
  -----------------------------------------------------------------------

**How to Use This PRD Section**

- Product lead uses Goals, Non-Goals, and Milestones for planning.

- Developers derive tickets directly from User Stories and Acceptance
  Criteria.

- QA creates tests and release checklist from High-Level Requirements
  and Release Criteria.

- This section precedes the Reliability-First Product Definition to give
  a complete handoff document for engineering execution.

------------------------------------------------------------------------

# 7. Purpose and Strategic Alignment

## 1.1 Core Purpose

Provide a personal assistant layer that executes user-initiated
automations when the user speaks the single canonical tag "Log that."
The subsystem semantically routes each tagged utterance to the correct
module, processes it with AI where needed, persists a verifiable record,
and posts confirmations and summaries to the Discord channel.

## 1.2 Strategic Context

This subsystem is a core part of the Personal Automation Platform. It
exists to standardize how voice inputs from the Limitless Pendant become
reliable, auditable actions and logs across all current and future
modules.

## 1.3 Alignment and Principles

- Triggered, not passive. All module actions require the explicit "Log
  that" tag.

- Modular and extensible. Each automation is a Module with a stable
  interface managed by the ModuleRegistry.

- Reliability first. Every record is traceable to a source lifelog and
  confirmed to the user in Discord.

# 8. System Overview

## 2.1 What This Subsystem Is

An end-to-end orchestration layer that: polls the Limitless API, detects
the "Log that" tag, uses an Automation Orchestrator for semantic
routing, invokes the appropriate Module, uses the OpenAI client for text
or vision analysis when required, persists results to MongoDB, and posts
confirmations and summaries to Discord. Core entrypoint and
orchestration are demonstrated in the platform's main process and shared
services.

## 2.2 End-to-End Workflow

1.  User speaks "Log that" into the Limitless Pendant.

2.  Poller retrieves new lifelogs from the Limitless API.

3.  Automation Orchestrator performs semantic routing to the correct
    Module(s) via ModuleRegistry.

4.  Module uses OpenAI Client for text or image extraction as needed.

5.  Result is persisted to MongoDB following the common schema contract.

6.  Discord interface posts a human-readable confirmation or summary and
    handles Q and A.

7.  Scheduler triggers recurring tasks and daily summaries.

## 2.3 Primary Components and Roles

- Polling Service. Retrieves lifelogs on a fixed interval and hands
  entries to the orchestrator.

- Automation Orchestrator. Semantic router that chooses which Module to
  invoke.

- ModuleRegistry. Loads modules, matches messages, and dispatches to the
  selected Module.

- Modules. Self-contained automation units that implement a standard
  interface for logging, queries, image handling, schedules, and
  summaries.

- OpenAI Client. Text and vision analysis used by modules.

- Discord Interface. Two-way channel for confirmations, reactions,
  commands, and Q and A.

- Scheduler. Runs recurring module tasks and summary jobs.

# 9. Core Architecture

## 3.1 Limitless API Integration

The poller requests lifelogs and handles parameters such as date, start,
end, markdown inclusion, and direction. It logs and gracefully backs off
on errors and rate limits.

## 3.2 Automation Orchestrator and Routing

The Automation Orchestrator is invoked when the single canonical tag
"Log that" is detected. The orchestrator uses semantic analysis of the
surrounding transcript to classify intent and then selects one or more
Modules via the ModuleRegistry. The ModuleRegistry supports keyword and
pattern matching and exposes a catalog of loaded modules.

## 3.3 Module Interface and Responsibilities

All Modules must implement the standard interface defined by BaseModule,
including setup, logging, queries, image handling, schedules, and daily
summaries. This ensures consistent behavior across Nutrition, Workout,
and future modules.

## 3.4 AI Analysis Layer

Text extraction and image analysis are performed by the OpenAI Client.
Calls enforce JSON-only outputs for structured ingestion and defensive
error handling when JSON parsing fails.

## 3.5 Discord Interface

Discord bot handles message routing, image attachments, Q and A,
reaction-based confirmations, and summary commands. It posts module
results using rich embeds and supports a daily summary command.

## 3.6 Scheduler

A daily scheduler registers tasks provided by Modules and executes them
at specified times with async support and run logging.

# 10. Automation Lifecycle

## 4.1 Trigger and Detection

- Canonical verbal tag: "Log that."

- Poller detects new lifelogs and submits candidate entries to the
  orchestrator within one polling interval.

## 4.2 Semantic Routing

- The orchestrator uses OpenAI to infer the correct Module(s) from the
  transcript context and ModuleRegistry patterns.

## 4.3 Module Execution

- The Module performs extraction, validation, and record creation.
  Nutrition and Workout demonstrate text and vision flows with
  confirmation logic and post-processing such as intensity
  classification and dynamic targets.

## 4.4 Persistence

- Records are saved to MongoDB following the shared schema contract in
  Section 6. Writes are atomic and idempotent with unique lifelog
  linkage.

## 4.5 Feedback and Summaries

- Discord confirmation posts on success. Scheduled daily summaries
  aggregate across modules for the current day.

# 11. Timing and "Real Time" Definition

## 5.1 Polling and Processing Guarantees

- The platform processes new Limitless lifelogs within one polling
  interval once they appear in the API. Default interval is 2 seconds
  and is configurable.

## 5.2 End-to-End Responsiveness

- End-to-end real-time responsiveness from voice input to Discord
  confirmation will be measured and benchmarked after verifying the
  Limitless update frequency.

- Provisional user-visible confirmation target is listed in Section 9.

# 12. Data Model and MongoDB Schema Contract

## 6.1 Collection Strategy

- One collection per module. Examples: nutrition_logs, workout_logs.

- Shared collection for evidence and telemetry: automation_evidence.

## 6.2 Required Common Fields

Each record written by any Module must include:

- lifelog_id. Unique identifier from Limitless lifelog.

- timestamp. ISO 8601 time the record was created.

- module. Module name such as nutrition or workout.

- processed_by. Orchestrator and module versions or component
  identifiers.

- source. Structured details about origin such as limitless_api,
  discord_image, transcript.

- metadata. Nested document with version, schema_version, hash, and
  audit annotations.

## 6.3 Module Payload Conventions

- Nutrition records. Itemized fields such as item, calories, protein_g,
  carbs_g, fat_g, fiber_g.

- Workout records. Fields such as exercise_type, duration_minutes,
  calories_burned, peloton_output, avg_hr, training_zone_summary.

- All writes must be atomic, idempotent, and traceable to the lifelog_id
  that initiated them.

## 6.4 Evidence Records

- Evidence documents contain the source excerpt, parsed JSON, record
  pointer, confirmation message id, and integrity hash to support audits
  and replays.

# 13. Error Handling and Recovery

## 7.1 Detection and Isolation

- OpenAI parsing errors. Validate JSON; on failure, retry with
  constrained prompt and log raw content.

- API failures and rate limits. Back off, retry, and continue polling
  without blocking other modules.

## 7.2 Idempotency and Deduplication

- Duplicate lifelog processing prevented via lifelog_id checks.

- Writes use upserts with unique keys where appropriate.

## 7.3 Catch-up After Downtime

- After restart, the system catches up on missed entries within one
  polling interval, then resumes steady state.

# 14. Security and Access

## 8.1 Secrets Management

- OpenAI and Limitless credentials are required and loaded via
  environment configuration.

## 8.2 Least Privilege and Logging

- External API tokens are scoped to required endpoints.

- Evidence and telemetry avoid sensitive content beyond what is
  essential for traceability.

# 15. Reliability and Performance Targets

## 9.1 Core System Targets under Platform Control

- System uptime. Greater than or equal to 99.9 percent.

- Polling interval. 2 seconds configurable.

- Processing latency. Less than or equal to 2 seconds from lifelog
  detection to database write.

- Data integrity. 100 percent atomic idempotent writes.

- Routing accuracy. Greater than or equal to 95 percent correct module
  classification.

- Audit completeness. 100 percent of records link to a verifiable
  lifelog_id.

## 9.2 Provisional End-to-End Targets dependent on Limitless timing

- Speech to Discord confirmation P95. Less than or equal to 15 seconds.

- Mean latency. 8 to 10 seconds typical.

- Recovery target. Catch up within one polling cycle after downtime.

## 9.3 Measurement Plan

- Instrument poll cycle start, lifelog detection time, orchestrator
  routing time, module write time, and Discord post time.

- Establish final SLIs after observing Limitless lifelog posting
  behavior in production logs.

# 16. Operational Acceptance Criteria

## 10.1 Trigger and Routing

- The system detects "Log that," performs semantic routing, and invokes
  the correct Module with a routing accuracy greater than or equal to 95
  percent.

## 10.2 Processing and Persistence

- For any lifelog containing "Log that," the subsystem writes a
  validated record to MongoDB in less than or equal to 2 seconds after
  detection with the required common fields present.

## 10.3 Feedback and Evidence

- The system posts a human-readable confirmation to Discord for every
  successful write and stores an evidence document linking the
  lifelog_id, parsed JSON, and posted message reference.

## 10.4 Scheduler and Summaries

- Scheduler runs each configured task at its time and logs success or
  failure with module attribution.

# 17. Scope Clarification

## 11.1 In Scope

- Limitless polling, orchestration, semantic routing, module execution,
  AI analysis, MongoDB persistence, Discord feedback, and scheduling.

## 11.2 Out of Scope for v1.0

- Wearable integrations, long-horizon trend analytics, and external data
  warehouse integrations. These may be added by later roadmap.

# 18. Module Integration Model

## 12.1 Module Interface Contract

- Modules must implement the BaseModule interface for setup, log
  handling, question handling, image handling, scheduled tasks, and
  daily summaries.

## 12.2 ModuleRegistry Responsibilities

- Load enabled modules, provide keyword and question matching helpers,
  and expose enumeration of scheduled tasks and daily summaries across
  modules.

## 12.3 Examples

- Nutrition module. Food and health logging, image analysis for meals,
  summaries and targets.

- Workout module. Exercise logging, Peloton image extraction, intensity
  and electrolytes logic.

# 19. User Interface Contract

## 13.1 Discord as the Official Interface

- All confirmations, Q and A answers, and daily summaries are posted to
  Discord. The bot implements commands for help and summary and manages
  reaction-based confirmations for image flows.

## 13.2 Commands and Interactions

- Summary and help commands are available to provide daily overviews and
  usage guidance.

# 20. Success Metrics

## 14.1 Technical Reliability

- Uptime, processing latency, data integrity, and catch-up after
  downtime.

## 14.2 Behavioral Reliability

- Correct semantic routing when "Log that" is used and correct
  enforcement of the schema contract.

## 14.3 Cognitive Reliability

- User-perceived accuracy and trust in confirmations and summaries as
  gathered through periodic feedback.

# 21. Document Control and Version History

- Version 1.0. Initial product definition for Limitless Pendant
  Automations as a core subsystem.

- This document governs the module-level product definitions and will be
  reviewed after empirical latency measurements of Limitless lifelog
  posting behavior.

------------------------------------------------------------------------

## Notes on Code Alignment

- Polling, dispatch, and scheduler patterns are implemented in the main
  process and supporting services.

- Module lifecycle, routing, and standard interfaces are defined by
  ModuleRegistry and BaseModule.

- The Discord, OpenAI, and Limitless integrations referenced in this
  definition are operational in the current codebase.
