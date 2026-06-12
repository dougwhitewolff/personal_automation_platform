import { Injectable } from "@nestjs/common";
import { PrismaService } from "../infrastructure/prisma.service";
import { AuditService } from "../audit/audit.service";
import { ReviewsService } from "../reviews/reviews.service";
import { NormalizedEmail } from "../integrations/normalized-email.type";
import { fallbackSourceMessageId, parsePlaudEmail } from "./plaud-parser";

@Injectable()
export class CapturesService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly auditService: AuditService,
    private readonly reviewsService: ReviewsService
  ) {}

  async processEmail(input: { tenantId: string; appId: string; integrationId?: string; email: NormalizedEmail }) {
    const parseResult = parsePlaudEmail({
      from: input.email.from,
      subject: input.email.subject,
      bodyText: input.email.bodyText,
      attachments: input.email.attachments.map((a) => ({ filename: a.filename, textContent: a.textContent }))
    });

    if (!parseResult.isPlaud) {
      await this.auditService.log({
        tenantId: input.tenantId,
        appId: input.appId,
        eventType: "plaud_rejected",
        payload: { reason: parseResult.reason, messageId: input.email.messageId }
      });
      return null;
    }

    const sourceMessageId = input.email.messageId || fallbackSourceMessageId({
      from: input.email.from,
      to: input.email.to,
      subject: input.email.subject,
      bodyText: input.email.bodyText
    });

    const capture = await this.prisma.captureEvent.upsert({
      where: {
        tenantId_sourceMessageId: {
          tenantId: input.tenantId,
          sourceMessageId
        }
      },
      create: {
        tenantId: input.tenantId,
        appId: input.appId,
        integrationId: input.integrationId,
        sourceMessageId,
        sourceFrom: input.email.from,
        sourceTo: input.email.to,
        subject: input.email.subject,
        bodyText: input.email.bodyText,
        bodyHtml: input.email.bodyHtml,
        summaryText: parseResult.summaryText,
        transcriptText: parseResult.transcriptText,
        attachmentMeta: input.email.attachments,
        status: "PARSED",
        receivedAt: input.email.receivedAt
      },
      update: {}
    });

    await this.auditService.log({
      tenantId: input.tenantId,
      appId: input.appId,
      captureEventId: capture.id,
      eventType: "capture_created"
    });

    await this.reviewsService.ensureReviewForCapture({
      tenantId: input.tenantId,
      appId: input.appId,
      captureEventId: capture.id
    });

    return capture;
  }
}
