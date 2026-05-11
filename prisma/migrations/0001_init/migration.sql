-- Initial tenant-aware schema
-- Generated manually for bootstrap

CREATE TYPE "CaptureStatus" AS ENUM ('RECEIVED', 'PARSED', 'NEEDS_ATTENTION');
CREATE TYPE "ReviewStatus" AS ENUM ('PENDING', 'CONFIRMED', 'REJECTED');

CREATE TABLE "Tenant" (
  "id" TEXT PRIMARY KEY,
  "name" TEXT NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL
);

CREATE TABLE "ClientApp" (
  "id" TEXT PRIMARY KEY,
  "tenantId" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "slug" TEXT NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL
);

CREATE TABLE "ServiceApiKey" (
  "id" TEXT PRIMARY KEY,
  "tenantId" TEXT NOT NULL,
  "appId" TEXT NOT NULL,
  "keyHash" TEXT NOT NULL,
  "keyPrefix" TEXT NOT NULL,
  "label" TEXT NOT NULL,
  "scopes" TEXT[] NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "rotatedAt" TIMESTAMP(3)
);

CREATE TABLE "Integration" (
  "id" TEXT PRIMARY KEY,
  "tenantId" TEXT NOT NULL,
  "appId" TEXT NOT NULL,
  "provider" TEXT NOT NULL,
  "mailboxAddress" TEXT NOT NULL,
  "configJson" JSONB,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL
);

CREATE TABLE "CaptureEvent" (
  "id" TEXT PRIMARY KEY,
  "tenantId" TEXT NOT NULL,
  "appId" TEXT NOT NULL,
  "integrationId" TEXT,
  "sourceMessageId" TEXT NOT NULL,
  "sourceFrom" TEXT NOT NULL,
  "sourceTo" TEXT NOT NULL,
  "subject" TEXT NOT NULL,
  "bodyText" TEXT,
  "bodyHtml" TEXT,
  "summaryText" TEXT,
  "transcriptText" TEXT,
  "attachmentMeta" JSONB,
  "status" "CaptureStatus" NOT NULL DEFAULT 'RECEIVED',
  "parserError" TEXT,
  "receivedAt" TIMESTAMP(3) NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL
);

CREATE TABLE "ReviewItem" (
  "id" TEXT PRIMARY KEY,
  "tenantId" TEXT NOT NULL,
  "appId" TEXT NOT NULL,
  "captureEventId" TEXT NOT NULL,
  "status" "ReviewStatus" NOT NULL DEFAULT 'PENDING',
  "proposedAction" TEXT NOT NULL,
  "proposedPayload" JSONB NOT NULL,
  "actorUserId" TEXT,
  "actorEmail" TEXT,
  "decidedAt" TIMESTAMP(3),
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL
);

CREATE TABLE "AuditEvent" (
  "id" TEXT PRIMARY KEY,
  "tenantId" TEXT NOT NULL,
  "appId" TEXT NOT NULL,
  "captureEventId" TEXT,
  "reviewItemId" TEXT,
  "eventType" TEXT NOT NULL,
  "payload" JSONB,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE "WorkflowRun" (
  "id" TEXT PRIMARY KEY,
  "tenantId" TEXT NOT NULL,
  "appId" TEXT NOT NULL,
  "captureEventId" TEXT,
  "reviewItemId" TEXT,
  "provider" TEXT NOT NULL,
  "providerRunId" TEXT NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX "ClientApp_tenantId_slug_key" ON "ClientApp"("tenantId", "slug");
CREATE UNIQUE INDEX "Integration_provider_mailboxAddress_key" ON "Integration"("provider", "mailboxAddress");
CREATE UNIQUE INDEX "CaptureEvent_tenantId_sourceMessageId_key" ON "CaptureEvent"("tenantId", "sourceMessageId");
CREATE UNIQUE INDEX "ReviewItem_captureEventId_key" ON "ReviewItem"("captureEventId");
CREATE UNIQUE INDEX "WorkflowRun_provider_providerRunId_key" ON "WorkflowRun"("provider", "providerRunId");

ALTER TABLE "ClientApp" ADD CONSTRAINT "ClientApp_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES "Tenant"("id");
ALTER TABLE "ServiceApiKey" ADD CONSTRAINT "ServiceApiKey_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES "Tenant"("id");
ALTER TABLE "Integration" ADD CONSTRAINT "Integration_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES "Tenant"("id");
ALTER TABLE "CaptureEvent" ADD CONSTRAINT "CaptureEvent_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES "Tenant"("id");
ALTER TABLE "ReviewItem" ADD CONSTRAINT "ReviewItem_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES "Tenant"("id");
ALTER TABLE "ReviewItem" ADD CONSTRAINT "ReviewItem_captureEventId_fkey" FOREIGN KEY ("captureEventId") REFERENCES "CaptureEvent"("id");
ALTER TABLE "AuditEvent" ADD CONSTRAINT "AuditEvent_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES "Tenant"("id");
ALTER TABLE "AuditEvent" ADD CONSTRAINT "AuditEvent_captureEventId_fkey" FOREIGN KEY ("captureEventId") REFERENCES "CaptureEvent"("id");
