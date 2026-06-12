-- Unified PostgreSQL schema (automation platform — replaces MongoDB + separate outbox DB)

CREATE TYPE "CaptureStatus" AS ENUM ('RECEIVED', 'PARSED', 'NEEDS_ATTENTION');
CREATE TYPE "ReviewStatus" AS ENUM ('PENDING', 'CONFIRMED', 'REJECTED');
CREATE TYPE "OutboxStatus" AS ENUM ('PENDING', 'SENT', 'FAILED');

CREATE TABLE "automation_tenants" (
    "id" TEXT NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "client_email" VARCHAR(254),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "automation_tenants_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "automation_tenants_client_email_key" ON "automation_tenants"("client_email");

CREATE TABLE "client_apps" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "slug" VARCHAR(100) NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "client_apps_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "client_apps_tenant_id_slug_key" ON "client_apps"("tenant_id", "slug");
CREATE INDEX "client_apps_tenant_id_idx" ON "client_apps"("tenant_id");

CREATE TABLE "service_api_keys" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "app_id" TEXT NOT NULL,
    "key_hash" VARCHAR(255) NOT NULL,
    "key_prefix" VARCHAR(32) NOT NULL,
    "label" VARCHAR(255) NOT NULL,
    "scopes" TEXT[] NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "rotated_at" TIMESTAMP(3),

    CONSTRAINT "service_api_keys_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "service_api_keys_tenant_id_app_id_idx" ON "service_api_keys"("tenant_id", "app_id");

CREATE TABLE "integrations" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "app_id" TEXT NOT NULL,
    "provider" VARCHAR(100) NOT NULL,
    "mailbox_address" VARCHAR(254) NOT NULL,
    "config_json" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "integrations_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "integrations_provider_mailbox_address_key" ON "integrations"("provider", "mailbox_address");
CREATE INDEX "integrations_tenant_id_app_id_idx" ON "integrations"("tenant_id", "app_id");

CREATE TABLE "capture_events" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "app_id" TEXT NOT NULL,
    "integration_id" TEXT,
    "source_message_id" VARCHAR(500) NOT NULL,
    "source_from" VARCHAR(500) NOT NULL,
    "source_to" VARCHAR(500) NOT NULL,
    "subject" VARCHAR(1000) NOT NULL,
    "body_text" TEXT,
    "body_html" TEXT,
    "summary_text" TEXT,
    "transcript_text" TEXT,
    "attachment_meta" JSONB,
    "status" "CaptureStatus" NOT NULL DEFAULT 'RECEIVED',
    "parser_error" TEXT,
    "received_at" TIMESTAMP(3) NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "capture_events_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "capture_events_tenant_id_source_message_id_key" ON "capture_events"("tenant_id", "source_message_id");
CREATE INDEX "capture_events_tenant_id_app_id_status_idx" ON "capture_events"("tenant_id", "app_id", "status");

CREATE TABLE "review_items" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "app_id" TEXT NOT NULL,
    "capture_event_id" TEXT NOT NULL,
    "status" "ReviewStatus" NOT NULL DEFAULT 'PENDING',
    "proposed_action" VARCHAR(255) NOT NULL,
    "proposed_payload" JSONB NOT NULL,
    "actor_user_id" VARCHAR(255),
    "actor_email" VARCHAR(254),
    "decided_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "review_items_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "review_items_capture_event_id_key" ON "review_items"("capture_event_id");
CREATE INDEX "review_items_tenant_id_app_id_status_idx" ON "review_items"("tenant_id", "app_id", "status");

CREATE TABLE "audit_events" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "app_id" TEXT NOT NULL,
    "capture_event_id" TEXT,
    "review_item_id" TEXT,
    "event_type" VARCHAR(100) NOT NULL,
    "payload" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "audit_events_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "audit_events_tenant_id_app_id_event_type_idx" ON "audit_events"("tenant_id", "app_id", "event_type");

CREATE TABLE "workflow_runs" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "app_id" TEXT NOT NULL,
    "capture_event_id" TEXT,
    "review_item_id" TEXT,
    "provider" VARCHAR(100) NOT NULL,
    "provider_run_id" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "workflow_runs_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "workflow_runs_provider_provider_run_id_key" ON "workflow_runs"("provider", "provider_run_id");
CREATE INDEX "workflow_runs_tenant_id_app_id_idx" ON "workflow_runs"("tenant_id", "app_id");

CREATE TABLE "outbox_emails" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "app_id" TEXT NOT NULL,
    "integration_id" TEXT,
    "provider_email_id" VARCHAR(500) NOT NULL,
    "crm_tenant_id" UUID,
    "message_id" VARCHAR(500) NOT NULL,
    "email_payload" JSONB NOT NULL,
    "status" "OutboxStatus" NOT NULL DEFAULT 'PENDING',
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "last_error" VARCHAR(2000),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "published_at" TIMESTAMP(3),

    CONSTRAINT "outbox_emails_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "outbox_emails_tenant_id_provider_email_id_key" ON "outbox_emails"("tenant_id", "provider_email_id");
CREATE INDEX "outbox_emails_status_created_at_idx" ON "outbox_emails"("status", "created_at");

CREATE TABLE "crm_tenant_email_mappings" (
    "id" TEXT NOT NULL,
    "source_email" VARCHAR(254) NOT NULL,
    "crm_tenant_id" UUID NOT NULL,
    "label" VARCHAR(255),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "crm_tenant_email_mappings_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "crm_tenant_email_mappings_source_email_key" ON "crm_tenant_email_mappings"("source_email");

ALTER TABLE "client_apps" ADD CONSTRAINT "client_apps_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "automation_tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "service_api_keys" ADD CONSTRAINT "service_api_keys_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "automation_tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "integrations" ADD CONSTRAINT "integrations_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "automation_tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "capture_events" ADD CONSTRAINT "capture_events_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "automation_tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "review_items" ADD CONSTRAINT "review_items_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "automation_tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "review_items" ADD CONSTRAINT "review_items_capture_event_id_fkey" FOREIGN KEY ("capture_event_id") REFERENCES "capture_events"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "audit_events" ADD CONSTRAINT "audit_events_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "automation_tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "audit_events" ADD CONSTRAINT "audit_events_capture_event_id_fkey" FOREIGN KEY ("capture_event_id") REFERENCES "capture_events"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "workflow_runs" ADD CONSTRAINT "workflow_runs_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "automation_tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;
