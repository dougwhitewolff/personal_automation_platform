import { Injectable } from "@nestjs/common";
import { OutboxPrismaService } from "./outbox-prisma.service";
import type { OutboxEmailPayload } from "./outbox-email-payload.type";

export type UpsertIncomingEmailInput = {
  tenantId: string;
  appId: string;
  integrationId?: string;
  /** Graph message id or dev synthetic — dedupe key with tenantId. */
  providerEmailId: string;
  /** RFC Message-ID / internetMessageId — downstream dedupe. */
  messageId: string;
  emailPayload: OutboxEmailPayload;
};

@Injectable()
export class OutboxService {
  constructor(private readonly outboxPrisma: OutboxPrismaService) {}

  /**
   * Idempotent inbox write: same tenant + providerEmailId never creates a second row.
   */
  upsertIncomingEmail(input: UpsertIncomingEmailInput) {
    return this.outboxPrisma.outboxEmail.upsert({
      where: {
        tenantId_providerEmailId: {
          tenantId: input.tenantId,
          providerEmailId: input.providerEmailId
        }
      },
      create: {
        tenantId: input.tenantId,
        appId: input.appId,
        integrationId: input.integrationId,
        providerEmailId: input.providerEmailId,
        messageId: input.messageId,
        emailPayload: input.emailPayload as object
      },
      update: {}
    });
  }
}
