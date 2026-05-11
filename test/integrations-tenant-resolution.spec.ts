import { describe, expect, it, vi } from "vitest";
import { IntegrationsService } from "../src/integrations/integrations.service";

describe("integrations tenant resolution", () => {
  it("uses client recipient to resolve tenant for polled messages", async () => {
    const prisma = {
      integration: {
        findFirst: vi.fn().mockResolvedValue({
          id: "integration-1",
          tenantId: "seed-tenant",
          appId: "seed-app",
          mailboxAddress: "our-inbox@example.com"
        })
      },
      clientApp: {
        findFirst: vi.fn().mockResolvedValue({ id: "client-app-1", tenantId: "tenant-client" })
      }
    };
    const outboxService = { upsertIncomingEmail: vi.fn().mockResolvedValue({ id: "ob1" }) };
    const graphClient = {
      fetchRecentMessages: vi.fn().mockResolvedValue([
        {
          id: "msg-1",
          internetMessageId: "<id-1>",
          from: { emailAddress: { address: "plaud@example.com" } },
          toRecipients: [
            { emailAddress: { address: "our-inbox@example.com" } },
            { emailAddress: { address: "client@example.com" } }
          ],
          subject: "Plaud summary",
          bodyPreview: "body"
        }
      ]),
      fetchAttachments: vi.fn().mockResolvedValue([])
    };
    const tenantsService = {
      findByClientEmail: vi.fn().mockResolvedValue({ id: "tenant-client" })
    };

    const service = new IntegrationsService(prisma as never, outboxService as never, graphClient as never, tenantsService as never);

    vi.stubEnv("M365_USER_EMAIL", "our-inbox@example.com");
    await service.pollM365Mailbox();
    vi.unstubAllEnvs();

    expect(tenantsService.findByClientEmail).toHaveBeenCalledWith("client@example.com");
    expect(outboxService.upsertIncomingEmail).toHaveBeenCalledWith(
      expect.objectContaining({
        tenantId: "tenant-client",
        appId: "client-app-1",
        providerEmailId: "msg-1",
        messageId: "<id-1>",
        emailPayload: expect.objectContaining({
          to: "client@example.com"
        })
      })
    );
  });
});
