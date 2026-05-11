-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateEnum
CREATE TYPE "OutboxStatus" AS ENUM ('PENDING', 'SENT', 'FAILED');

-- CreateTable
CREATE TABLE "outbox_emails" (
    "id" TEXT NOT NULL,
    "tenant_id" TEXT NOT NULL,
    "app_id" TEXT NOT NULL,
    "integration_id" TEXT,
    "provider_email_id" TEXT NOT NULL,
    "message_id" TEXT NOT NULL,
    "email_payload" JSONB NOT NULL,
    "status" "OutboxStatus" NOT NULL DEFAULT 'PENDING',
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "last_error" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "published_at" TIMESTAMP(3),

    CONSTRAINT "outbox_emails_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "outbox_emails_status_created_at_idx" ON "outbox_emails"("status", "created_at");

-- CreateIndex
CREATE UNIQUE INDEX "outbox_emails_tenant_id_provider_email_id_key" ON "outbox_emails"("tenant_id", "provider_email_id");
