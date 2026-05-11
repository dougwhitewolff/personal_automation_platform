import { describe, expect, it, vi } from "vitest";
import { OutboxRelayService } from "../src/outbox/outbox-relay.service";

describe("OutboxRelayService", () => {
  it("publishes pending rows and marks SENT", async () => {
    const row = {
      id: "o1",
      tenantId: "t1",
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

    const outboxPrisma = {
      outboxEmail: { findMany, update }
    };

    const kafka = {
      enabled: true,
      sendJsonRecord: vi.fn().mockResolvedValue(undefined)
    };

    const relay = new OutboxRelayService(outboxPrisma as never, kafka as never);
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

    expect(update).toHaveBeenCalledWith({
      where: { id: "o1" },
      data: expect.objectContaining({ status: "SENT", publishedAt: expect.any(Date) })
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
