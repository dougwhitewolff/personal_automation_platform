import { afterEach, describe, expect, it, vi } from "vitest";
import { TenantRouteKind } from "@prisma/client";
import { OutboxRelayService } from "../src/outbox/outbox-relay.service";

const PLAUD_FROM = "Plaud <no-reply@plaud.ai>";

describe("OutboxRelayService", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("publishes pending rows and marks SENT", async () => {
    vi.stubEnv("PLAUD_SENDER_EMAIL", "no-reply@plaud.ai");

    const row = {
      id: "o1",
      tenantId: "t1",
      crmTenantId: "00000000-0000-0000-0000-000000000001",
      appId: "a1",
      mailboxWatchId: "watch-1",
      providerEmailId: "graph-msg",
      messageId: "<mid@example.com>",
      emailPayload: { from: PLAUD_FROM, hello: "world" },
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
      tenantRouter: { findUnique: vi.fn().mockResolvedValue(null) }
    };

    const kafka = {
      enabled: true,
      sendJsonRecord: vi.fn().mockResolvedValue(undefined)
    };

    const relay = new OutboxRelayService(prisma as never, kafka as never);
    await relay.relayPendingToKafka();

    expect(kafka.sendJsonRecord).toHaveBeenCalledTimes(1);
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

  it("resolves CRM tenant from tenant_routers when outbox row has no crmTenantId", async () => {
    vi.stubEnv("PLAUD_SENDER_EMAIL", "noreply@plaud.ai");

    const row = {
      id: "o2",
      tenantId: "t1",
      crmTenantId: null,
      appId: "a1",
      mailboxWatchId: null,
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
    const findUniqueRouter = vi.fn().mockResolvedValue({
      id: "r1",
      routeKind: TenantRouteKind.email,
      routeKey: "noreply@plaud.ai",
      crmTenantId: "00000000-0000-0000-0000-000000000099"
    });

    const prisma = {
      outboxEmail: { findMany, update },
      tenantRouter: { findUnique: findUniqueRouter }
    };

    const kafka = {
      enabled: true,
      sendJsonRecord: vi.fn().mockResolvedValue(undefined)
    };

    const relay = new OutboxRelayService(prisma as never, kafka as never);
    await relay.relayPendingToKafka();

    expect(findUniqueRouter).toHaveBeenCalledWith({
      where: {
        routeKind_routeKey: {
          routeKind: TenantRouteKind.email,
          routeKey: "noreply@plaud.ai"
        }
      }
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

  it("includes payload.transcript on platform events when email_payload has transcript", async () => {
    vi.stubEnv("PLAUD_SENDER_EMAIL", "noreply@plaud.ai");

    const demoTranscript = "Create a lead for Jane Doe at Example Corp.";
    const row = {
      id: "o3",
      tenantId: "t1",
      crmTenantId: "00000000-0000-0000-0000-000000000001",
      appId: "a1",
      mailboxWatchId: null,
      providerEmailId: "graph-msg-3",
      messageId: "<mid3@example.com>",
      emailPayload: {
        from: "Plaud <noreply@plaud.ai>",
        subject: "Demo",
        bodyText: `Marker\nThe original audio transcription is as follows:\n${demoTranscript}`,
        transcript: demoTranscript
      },
      status: "PENDING" as const,
      attempts: 0,
      lastError: null,
      createdAt: new Date(),
      updatedAt: new Date(),
      publishedAt: null
    };

    const prisma = {
      outboxEmail: {
        findMany: vi.fn().mockResolvedValue([row]),
        update: vi.fn().mockResolvedValue(row)
      },
      tenantRouter: { findUnique: vi.fn().mockResolvedValue(null) }
    };

    const kafka = {
      enabled: true,
      sendJsonRecord: vi.fn().mockResolvedValue(undefined)
    };

    const relay = new OutboxRelayService(prisma as never, kafka as never);
    await relay.relayPendingToKafka();

    expect(kafka.sendJsonRecord).toHaveBeenCalledWith(
      expect.objectContaining({
        key: "o3",
        value: expect.objectContaining({
          payload: expect.objectContaining({
            transcript: demoTranscript
          })
        })
      })
    );
  });

  it("skips Kafka for non-Plaud senders but marks outbox row SENT", async () => {
    vi.stubEnv("PLAUD_SENDER_EMAIL", "no-reply@plaud.ai");

    const row = {
      id: "o-ms",
      tenantId: "t1",
      crmTenantId: "00000000-0000-0000-0000-000000000001",
      appId: "a1",
      mailboxWatchId: "watch-1",
      providerEmailId: "graph-ms",
      messageId: "<ms@example.com>",
      emailPayload: {
        from: "Microsoft365@communication.microsoft.com",
        subject: "Get work done on the go"
      },
      status: "PENDING" as const,
      attempts: 0,
      lastError: null,
      createdAt: new Date(),
      updatedAt: new Date(),
      publishedAt: null
    };

    const update = vi.fn().mockResolvedValue(row);
    const prisma = {
      outboxEmail: { findMany: vi.fn().mockResolvedValue([row]), update },
      tenantRouter: { findUnique: vi.fn() }
    };
    const kafka = {
      enabled: true,
      sendJsonRecord: vi.fn().mockResolvedValue(undefined)
    };

    const relay = new OutboxRelayService(prisma as never, kafka as never);
    await relay.relayPendingToKafka();

    expect(kafka.sendJsonRecord).not.toHaveBeenCalled();
    expect(update).toHaveBeenCalledWith({
      where: { id: "o-ms" },
      data: { status: "SENT", lastError: null }
    });
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
