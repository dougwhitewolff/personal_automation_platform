import { describe, expect, it, vi } from "vitest";
import { IntegrationsService } from "../src/integrations/integrations.service";

describe("integrations mailbox poll", () => {
  it("ingests Plaud messages for each enabled mailbox watch", async () => {
    const watch = {
      id: "watch-1",
      mailboxAddress: "faiyaz@4trades.ai",
      m365TenantId: "azure-tenant",
      m365ClientId: "client-id",
      m365ClientSecret: "client-secret",
      enabled: true
    };

    const prisma = {
      mailboxWatch: {
        findMany: vi.fn().mockResolvedValue([watch])
      },
      tenantRouter: {
        findUnique: vi.fn().mockResolvedValue({
          crmTenantId: "00000000-0000-0000-0000-000000000001"
        })
      }
    };
    const outboxService = { upsertIncomingEmail: vi.fn().mockResolvedValue({ id: "ob1" }) };
    const graphClient = {
      fetchRecentMessages: vi.fn().mockResolvedValue([
        {
          id: "msg-1",
          internetMessageId: "<id-1>",
          from: { emailAddress: { address: "no-reply@plaud.ai" } },
          subject: "Plaud summary",
          bodyPreview:
            "The transcript is brief, no summary is needed. The original audio transcription is as follows:\nSpeaker 1 00:00:01\nWell, that worked great."
        },
        {
          id: "msg-ms",
          from: { emailAddress: { address: "Microsoft365@communication.microsoft.com" } },
          subject: "Get work done on the go"
        }
      ]),
      fetchAttachments: vi.fn().mockResolvedValue([
        {
          name: "transcript.txt",
          contentType: "text/plain",
          size: 448,
          contentBytes: Buffer.from("Well, that worked great.", "utf8").toString("base64")
        }
      ])
    };

    const service = new IntegrationsService(prisma as never, outboxService as never, graphClient as never);

    vi.stubEnv("PLAUD_SENDER_EMAIL", "no-reply@plaud.ai");
    await service.pollM365Mailbox();
    vi.unstubAllEnvs();

    expect(graphClient.fetchRecentMessages).toHaveBeenCalledWith(
      {
        m365TenantId: watch.m365TenantId,
        m365ClientId: watch.m365ClientId,
        m365ClientSecret: watch.m365ClientSecret
      },
      watch.mailboxAddress
    );
    expect(outboxService.upsertIncomingEmail).toHaveBeenCalledTimes(1);
    expect(outboxService.upsertIncomingEmail).toHaveBeenCalledWith(
      expect.objectContaining({
        tenantId: "watch-1",
        appId: "platform",
        mailboxWatchId: "watch-1",
        crmTenantId: "00000000-0000-0000-0000-000000000001",
        providerEmailId: "msg-1",
        messageId: "<id-1>"
      })
    );
  });
});
