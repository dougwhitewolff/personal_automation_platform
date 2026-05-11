import { Injectable, Logger } from "@nestjs/common";
import { Cron, CronExpression } from "@nestjs/schedule";
import { PrismaService } from "../infrastructure/prisma.service";
import { AuthContext } from "../common/auth-context.type";
import { M365GraphClient } from "./m365/m365-graph.client";
import { TenantsService } from "../tenants/tenants.service";
import { OutboxService } from "../outbox/outbox.service";
import { normalizedEmailToOutboxPayload } from "../outbox/to-outbox-payload";
import { stableDevProviderEmailId } from "../outbox/stable-dev-id";
import type { NormalizedEmail } from "./normalized-email.type";

@Injectable()
export class IntegrationsService {
  private readonly logger = new Logger(IntegrationsService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly outboxService: OutboxService,
    private readonly graphClient: M365GraphClient,
    private readonly tenantsService: TenantsService
  ) {}

  async ingestDevPayload(
    ctx: AuthContext,
    payload: {
      messageId?: string;
      /** Simulate Microsoft Graph message id for dedupe (optional). */
      providerEmailId?: string;
      from: string;
      to: string;
      subject: string;
      bodyText?: string;
      bodyHtml?: string;
      attachments?: Array<{ filename: string; contentType?: string; textContent?: string; size?: number }>;
    }
  ) {
    const integration = await this.prisma.integration.findFirst({
      where: {
        tenantId: ctx.tenantId,
        appId: ctx.appId,
        provider: "m365-graph",
        mailboxAddress: payload.to
      }
    });

    if (!integration) {
      throw new Error(`No integration for mailbox ${payload.to}`);
    }

    const providerEmailId =
      payload.providerEmailId?.trim() ||
      stableDevProviderEmailId([
        ctx.tenantId,
        payload.messageId ?? "",
        payload.from,
        payload.to,
        payload.subject,
        payload.bodyText ?? "",
        payload.bodyHtml ?? ""
      ]);

    const messageId =
      payload.messageId?.trim() ||
      `<dev-${providerEmailId.replace(/[^a-zA-Z0-9.@_-]+/g, "_")}@localhost>`;

    const email = this.buildNormalizedEmail({
      messageId,
      from: payload.from,
      to: payload.to,
      subject: payload.subject,
      bodyText: payload.bodyText,
      bodyHtml: payload.bodyHtml,
      attachments: payload.attachments,
      rawSourceRef: "dev-post"
    });

    return this.outboxService.upsertIncomingEmail({
      tenantId: ctx.tenantId,
      appId: ctx.appId,
      integrationId: integration.id,
      providerEmailId,
      messageId,
      emailPayload: normalizedEmailToOutboxPayload(email)
    });
  }

  @Cron(CronExpression.EVERY_5_MINUTES)
  async pollM365Mailbox(): Promise<void> {
    const mailboxAddress = process.env.M365_USER_EMAIL;
    if (!mailboxAddress) return;

    const integration = await this.prisma.integration.findFirst({
      where: {
        provider: "m365-graph",
        mailboxAddress
      }
    });
    if (!integration) return;

    const messages = await this.graphClient.fetchRecentMessages(mailboxAddress);
    for (const message of messages) {
      const graphMessageId = message.id;
      if (!graphMessageId) {
        this.logger.warn("Skipping message with no Graph id");
        continue;
      }

      const recipients = (message.toRecipients ?? [])
        .map((recipient) => this.normalizeEmail(recipient.emailAddress?.address))
        .filter((recipient): recipient is string => Boolean(recipient));
      const clientRecipient = recipients.find((recipient) => recipient !== this.normalizeEmail(mailboxAddress));
      if (!clientRecipient) {
        this.logger.warn(`Message ${graphMessageId} skipped: no client recipient in toRecipients`);
        continue;
      }

      const tenant = await this.tenantsService.findByClientEmail(clientRecipient);
      if (!tenant) {
        this.logger.warn(`Message ${graphMessageId} skipped: no tenant for client email ${clientRecipient}`);
        continue;
      }

      const app = await this.prisma.clientApp.findFirst({
        where: { tenantId: tenant.id },
        orderBy: { createdAt: "asc" }
      });
      if (!app) {
        this.logger.warn(`Message ${graphMessageId} skipped: tenant ${tenant.id} has no app`);
        continue;
      }

      const attachments = await this.graphClient.fetchAttachments(mailboxAddress, graphMessageId);
      const decodedAttachments = attachments.map((attachment) => ({
        filename: attachment.name ?? "unknown.txt",
        contentType: attachment.contentType ?? "application/octet-stream",
        size: attachment.size ?? 0,
        textContent: attachment.contentBytes
          ? Buffer.from(attachment.contentBytes, "base64").toString("utf8")
          : undefined
      }));

      const messageId =
        message.internetMessageId?.trim() ||
        `<graph-${graphMessageId.replace(/[^a-zA-Z0-9.@_-]+/g, "_")}@local.invalid>`;

      const email: NormalizedEmail = {
        messageId,
        from: message.from?.emailAddress?.address ?? "",
        to: clientRecipient,
        subject: message.subject ?? "",
        headers: {},
        bodyText: message.bodyPreview ?? undefined,
        bodyHtml: message.body?.contentType === "html" ? message.body.content : undefined,
        receivedAt: message.receivedDateTime ? new Date(message.receivedDateTime) : new Date(),
        rawSourceRef: `graph:${graphMessageId}`,
        attachments: decodedAttachments
      };

      await this.outboxService.upsertIncomingEmail({
        tenantId: tenant.id,
        appId: app.id,
        integrationId: integration.id,
        providerEmailId: graphMessageId,
        messageId,
        emailPayload: normalizedEmailToOutboxPayload(email)
      });
    }

    this.logger.log(`Polled ${messages.length} messages from M365`);
  }

  private buildNormalizedEmail(input: {
    messageId: string;
    from: string;
    to: string;
    subject: string;
    bodyText?: string;
    bodyHtml?: string;
    rawSourceRef: string;
    attachments?: Array<{ filename: string; contentType?: string; textContent?: string; size?: number }>;
  }): NormalizedEmail {
    return {
      messageId: input.messageId,
      from: input.from,
      to: input.to,
      subject: input.subject,
      headers: {},
      bodyText: input.bodyText,
      bodyHtml: input.bodyHtml,
      receivedAt: new Date(),
      rawSourceRef: input.rawSourceRef,
      attachments: (input.attachments ?? []).map((a) => ({
        filename: a.filename,
        contentType: a.contentType ?? "text/plain",
        textContent: a.textContent,
        size: a.size ?? a.textContent?.length ?? 0
      }))
    };
  }

  private normalizeEmail(email?: string | null): string | undefined {
    return email?.trim().toLowerCase() || undefined;
  }
}
