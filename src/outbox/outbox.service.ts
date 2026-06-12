import { Injectable } from "@nestjs/common";
import { sanitizePostgresText } from "../common/sanitize-postgres-text";
import { PrismaService } from "../infrastructure/prisma.service";
import type { OutboxEmailPayload } from "./outbox-email-payload.type";

export type UpsertIncomingEmailInput = {
  tenantId: string;
  appId: string;
  mailboxWatchId?: string;
  /** CRM tenants.id UUID — set from the linked tenant router during mailbox poll. */
  crmTenantId?: string;
  /** Graph message id or dev synthetic — dedupe key with tenantId. */
  providerEmailId: string;
  /** RFC Message-ID / internetMessageId — downstream dedupe. */
  messageId: string;
  emailPayload: OutboxEmailPayload;
};

@Injectable()
export class OutboxService {
  constructor(private readonly prisma: PrismaService) {}

  /**
   * Idempotent inbox write: same tenant + providerEmailId never creates a second row.
   */
  upsertIncomingEmail(input: UpsertIncomingEmailInput) {
    const providerEmailId = sanitizePostgresText(input.providerEmailId);
    const messageId = sanitizePostgresText(input.messageId);

    return this.prisma.outboxEmail.upsert({
      where: {
        tenantId_providerEmailId: {
          tenantId: input.tenantId,
          providerEmailId
        }
      },
      create: {
        tenantId: input.tenantId,
        appId: input.appId,
        mailboxWatchId: input.mailboxWatchId,
        crmTenantId: input.crmTenantId,
        providerEmailId,
        messageId,
        emailPayload: input.emailPayload as object
      },
      update: {}
    });
  }
}
