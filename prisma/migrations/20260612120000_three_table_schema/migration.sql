-- Simplify to outbox + tenant router + mailbox watch

DROP TABLE IF EXISTS "audit_events" CASCADE;
DROP TABLE IF EXISTS "review_items" CASCADE;
DROP TABLE IF EXISTS "workflow_runs" CASCADE;
DROP TABLE IF EXISTS "capture_events" CASCADE;
DROP TABLE IF EXISTS "service_api_keys" CASCADE;
DROP TABLE IF EXISTS "integrations" CASCADE;
DROP TABLE IF EXISTS "client_apps" CASCADE;
DROP TABLE IF EXISTS "crm_tenant_email_mappings" CASCADE;
DROP TABLE IF EXISTS "automation_tenants" CASCADE;

DROP TYPE IF EXISTS "CaptureStatus";
DROP TYPE IF EXISTS "ReviewStatus";

CREATE TYPE "TenantRouteKind" AS ENUM ('email', 'device_id');

CREATE TABLE "tenant_routers" (
    "id" TEXT NOT NULL,
    "route_kind" "TenantRouteKind" NOT NULL,
    "route_key" VARCHAR(320) NOT NULL,
    "crm_tenant_id" UUID,
    "label" VARCHAR(255),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "tenant_routers_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "tenant_routers_route_kind_route_key_key" ON "tenant_routers"("route_kind", "route_key");

CREATE TABLE "mailbox_watches" (
    "id" TEXT NOT NULL,
    "mailbox_address" VARCHAR(254) NOT NULL,
    "m365_tenant_id" VARCHAR(64) NOT NULL,
    "m365_client_id" VARCHAR(64) NOT NULL,
    "m365_client_secret" TEXT NOT NULL,
    "enabled" BOOLEAN NOT NULL DEFAULT true,
    "label" VARCHAR(255),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "mailbox_watches_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "mailbox_watches_mailbox_address_key" ON "mailbox_watches"("mailbox_address");

ALTER TABLE "outbox_emails" RENAME COLUMN "integration_id" TO "mailbox_watch_id";
UPDATE "outbox_emails" SET "mailbox_watch_id" = NULL;

ALTER TABLE "outbox_emails"
ADD CONSTRAINT "outbox_emails_mailbox_watch_id_fkey"
FOREIGN KEY ("mailbox_watch_id") REFERENCES "mailbox_watches"("id") ON DELETE SET NULL ON UPDATE CASCADE;
