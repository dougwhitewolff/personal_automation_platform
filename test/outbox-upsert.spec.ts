import { describe, expect, it, vi } from "vitest";
import { OutboxService } from "../src/outbox/outbox.service";

describe("OutboxService upsert", () => {
  it("delegates to prisma upsert with tenant plus provider id compound key", async () => {
    const upsert = vi.fn().mockResolvedValue({ id: "x" });
    const outboxPrisma = { outboxEmail: { upsert } };

    const svc = new OutboxService(outboxPrisma as never);
    await svc.upsertIncomingEmail({
      tenantId: "t1",
      appId: "a1",
      mailboxWatchId: "watch-1",
      providerEmailId: "graph-123",
      messageId: "<mid@example.com>",
      emailPayload: {
        from: "a@b.com",
        to: "c@d.com",
        subject: "s",
        headers: {},
        receivedAt: new Date().toISOString(),
        attachments: []
      }
    });

    expect(upsert).toHaveBeenCalledWith({
      where: {
        tenantId_providerEmailId: { tenantId: "t1", providerEmailId: "graph-123" }
      },
      create: expect.objectContaining({
        tenantId: "t1",
        appId: "a1",
        providerEmailId: "graph-123",
        messageId: "<mid@example.com>"
      }),
      update: {}
    });
  });
});
