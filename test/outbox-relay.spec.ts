import { describe, expect, it, vi } from "vitest";
import { OutboxRelayService } from "../src/outbox/outbox-relay.service";

describe("OutboxRelayService", () => {
  it("publishes pending rows and marks SENT", async () => {
    const row = {
      id: "o1",
      tenantId: "t1",
      crmTenantId: "00000000-0000-0000-0000-000000000001",
      appId: "a1",
      integrationId: "int1",
      providerEmailId: "graph-msg",
      messageId: "<mid@example.com>",
      emailPayload: { hello: "world" },
      status: "PENDING" as const,
      attempts: 0,
      lastError: null,
      createdAt: new Date(),
      updatedAt: new Date(),
      publishedAt: null
    };

    const findMany = vi.fn().mockResolvedValue([row]);
    const update = vi.fn().mockResolvedValue(row);

    const prisma = {
      outboxEmail: { findMany, update },
      crmTenantEmailMapping: { findUnique: vi.fn().mockResolvedValue(null) }
    };

    const kafka = {
      enabled: true,
      sendJsonRecord: vi.fn().mockResolvedValue(undefined)
    };

    const relay = new OutboxRelayService(prisma as never, kafka as never);
    await relay.relayPendingToKafka();

    expect(kafka.sendJsonRecord).toHaveBeenCalledWith(
      expect.objectContaining({
        topic: expect.any(String),
        key: "t1:<mid@example.com>",
        value: expect.objectContaining({
          messageId: "<mid@example.com>",
          tenantId: "t1",
          outboxEmailId: "o1"
        })
      })
    );

    expect(kafka.sendJsonRecord).toHaveBeenCalledWith(
      expect.objectContaining({
        topic: expect.any(String),
        key: "o1",
        value: expect.objectContaining({
          schemaVersion: 1,
          eventType: "plaud.email.inbound",
          source: "personal_automation_platform",
          correlationId: "o1",
          tenantId: "00000000-0000-0000-0000-000000000001"
        })
      })
    );

    expect(update).toHaveBeenCalledWith({
      where: { id: "o1" },
      data: expect.objectContaining({ status: "SENT", publishedAt: expect.any(Date) })
    });
  });

  it("resolves CRM tenant from crm_tenant_email_mappings when outbox row has no crmTenantId", async () => {
    const row = {
      id: "o2",
      tenantId: "t1",
      crmTenantId: null,
      appId: "a1",
      integrationId: null,
      providerEmailId: "graph-msg-2",
      messageId: "<mid2@example.com>",
      emailPayload: { from: "Plaud <noreply@plaud.ai>", subject: "x" },
      status: "PENDING" as const,
      attempts: 0,
      lastError: null,
      createdAt: new Date(),
      updatedAt: new Date(),
      publishedAt: null
    };

    const findMany = vi.fn().mockResolvedValue([row]);
    const update = vi.fn().mockResolvedValue(row);
    const findUniqueMapping = vi.fn().mockResolvedValue({
      id: "m1",
      sourceEmail: "noreply@plaud.ai",
      crmTenantId: "00000000-0000-0000-0000-000000000099"
    });

    const prisma = {
      outboxEmail: { findMany, update },
      crmTenantEmailMapping: { findUnique: findUniqueMapping }
    };

    const kafka = {
      enabled: true,
      sendJsonRecord: vi.fn().mockResolvedValue(undefined)
    };

    const relay = new OutboxRelayService(prisma as never, kafka as never);
    await relay.relayPendingToKafka();

    expect(findUniqueMapping).toHaveBeenCalledWith({
      where: { sourceEmail: "noreply@plaud.ai" }
    });

    expect(kafka.sendJsonRecord).toHaveBeenCalledWith(
      expect.objectContaining({
        key: "o2",
        value: expect.objectContaining({
          tenantId: "00000000-0000-0000-0000-000000000099"
        })
      })
    );
  });

  it("skips when Kafka is disabled", async () => {
    const sendJsonRecord = vi.fn();
    const relay = new OutboxRelayService({ outboxEmail: { findMany: vi.fn() } } as never, {
      enabled: false,
      sendJsonRecord
    } as never);

    await relay.relayPendingToKafka();

    expect(sendJsonRecord).not.toHaveBeenCalled();
  });
});
