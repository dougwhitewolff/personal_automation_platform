import { Injectable, Logger } from "@nestjs/common";
import { Cron, CronExpression } from "@nestjs/schedule";
import { PrismaService } from "../infrastructure/prisma.service";
import { M365GraphClient } from "./m365/m365-graph.client";
import { OutboxService } from "../outbox/outbox.service";
import { normalizedEmailToOutboxPayload } from "../outbox/to-outbox-payload";
import { stableDevProviderEmailId } from "../outbox/stable-dev-id";
import { decodeAttachmentTextContent } from "./decode-attachment-text";
import { getPlaudSenderEmailFromEnv, matchesPlaudSender } from "./plaud-sender";
import { PLATFORM_APP_ID } from "../common/platform-constants";
import { resolveCrmTenantIdFromMailboxWatchId } from "../tenant-router/resolve-crm-tenant";
import type { NormalizedEmail } from "./normalized-email.type";

@Injectable()
export class IntegrationsService {
  private readonly logger = new Logger(IntegrationsService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly outboxService: OutboxService,
    private readonly graphClient: M365GraphClient
  ) {}

  async ingestDevPayload(payload: {
    messageId?: string;
    providerEmailId?: string;
    from: string;
    to: string;
    subject: string;
    bodyText?: string;
    bodyHtml?: string;
    attachments?: Array<{ filename: string; contentType?: string; textContent?: string; size?: number }>;
  }) {
    const mailboxAddress = payload.to.trim().toLowerCase();
    const mailbox = await this.prisma.mailboxWatch.findUnique({
      where: { mailboxAddress },
      include: { tenantRouter: true }
    });

    if (!mailbox) {
      throw new Error(`No mailbox watch configured for ${payload.to}`);
    }

    const providerEmailId =
      payload.providerEmailId?.trim() ||
      stableDevProviderEmailId([
        mailbox.id,
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

    const crmTenantId =
      mailbox.tenantRouter?.crmTenantId ??
      process.env.CRM_DEMO_TENANT_ID?.trim() ??
      undefined;

    return this.outboxService.upsertIncomingEmail({
      tenantId: mailbox.id,
      appId: PLATFORM_APP_ID,
      mailboxWatchId: mailbox.id,
      crmTenantId,
      providerEmailId,
      messageId,
      emailPayload: normalizedEmailToOutboxPayload(email)
    });
  }

  @Cron(CronExpression.EVERY_5_MINUTES)
  async pollM365Mailbox(): Promise<void> {
    const watches = await this.prisma.mailboxWatch.findMany({
      where: { enabled: true },
      include: { tenantRouter: true },
      orderBy: { mailboxAddress: "asc" }
    });

    if (watches.length === 0) {
      return;
    }

    const plaudSenderEmail = getPlaudSenderEmailFromEnv();
    let totalIngested = 0;

    for (const watch of watches) {
      const credentials = {
        m365TenantId: watch.m365TenantId,
        m365ClientId: watch.m365ClientId,
        m365ClientSecret: watch.m365ClientSecret
      };

      const messages = await this.graphClient.fetchRecentMessages(credentials, watch.mailboxAddress);
      let ingestedForWatch = 0;

      for (const message of messages) {
        const graphMessageId = message.id;
        if (!graphMessageId) {
          this.logger.warn(`Skipping message with no Graph id (${watch.mailboxAddress})`);
          continue;
        }

        const fromAddress = message.from?.emailAddress?.address ?? "";
        if (plaudSenderEmail && !matchesPlaudSender(fromAddress, plaudSenderEmail)) {
          continue;
        }

        try {
          const attachments = await this.graphClient.fetchAttachments(
            credentials,
            watch.mailboxAddress,
            graphMessageId
          );
          const decodedAttachments = attachments.map((attachment) => {
            const contentType = attachment.contentType ?? "application/octet-stream";
            return {
              filename: attachment.name ?? "unknown.txt",
              contentType,
              size: attachment.size ?? 0,
              textContent: attachment.contentBytes
                ? decodeAttachmentTextContent(attachment.contentBytes, contentType)
                : undefined
            };
          });

          const messageId =
            message.internetMessageId?.trim() ||
            `<graph-${graphMessageId.replace(/[^a-zA-Z0-9.@_-]+/g, "_")}@local.invalid>`;

          const email: NormalizedEmail = {
            messageId,
            from: fromAddress,
            to: watch.mailboxAddress,
            subject: message.subject ?? "",
            headers: {},
            bodyText: message.bodyPreview ?? undefined,
            bodyHtml: message.body?.contentType === "html" ? message.body.content : undefined,
            receivedAt: message.receivedDateTime ? new Date(message.receivedDateTime) : new Date(),
            rawSourceRef: `graph:${graphMessageId}`,
            attachments: decodedAttachments
          };

          const crmTenantId =
            watch.tenantRouter?.crmTenantId ??
            process.env.CRM_DEMO_TENANT_ID?.trim() ??
            undefined;

          await this.outboxService.upsertIncomingEmail({
            tenantId: watch.id,
            appId: PLATFORM_APP_ID,
            mailboxWatchId: watch.id,
            crmTenantId,
            providerEmailId: graphMessageId,
            messageId,
            emailPayload: normalizedEmailToOutboxPayload(email)
          });
          ingestedForWatch += 1;
        } catch (error) {
          const subject = message.subject ?? "(no subject)";
          this.logger.error(
            `Failed to ingest Graph message ${graphMessageId} (${subject}) for ${watch.mailboxAddress}: ${
              error instanceof Error ? error.message : String(error)
            }`
          );
        }
      }

      totalIngested += ingestedForWatch;
      this.logger.log(
        `Polled ${messages.length} messages from ${watch.mailboxAddress}; ingested ${ingestedForWatch} Plaud message(s)`
      );
    }

    if (totalIngested > 0) {
      this.logger.log(`Mailbox poll complete; ingested ${totalIngested} message(s) across ${watches.length} watch(es)`);
    }
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
}
