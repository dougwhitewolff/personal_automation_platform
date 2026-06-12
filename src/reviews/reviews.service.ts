import { Injectable, NotFoundException } from "@nestjs/common";
import { PrismaService } from "../infrastructure/prisma.service";
import { AuditService } from "../audit/audit.service";
import { MockCrmAdapter } from "../adapters/crm/mock-crm.adapter";

@Injectable()
export class ReviewsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly auditService: AuditService,
    private readonly crmAdapter: MockCrmAdapter
  ) {}

  ensureReviewForCapture(params: { tenantId: string; appId: string; captureEventId: string }) {
    return this.prisma.reviewItem.upsert({
      where: { captureEventId: params.captureEventId },
      create: {
        tenantId: params.tenantId,
        appId: params.appId,
        captureEventId: params.captureEventId,
        proposedAction: "LOG_INTERACTION",
        proposedPayload: { captureEventId: params.captureEventId }
      },
      update: {}
    });
  }

  list(tenantId: string, appId: string) {
    return this.prisma.reviewItem.findMany({ where: { tenantId, appId }, orderBy: { createdAt: "desc" } });
  }

  getOne(tenantId: string, appId: string, id: string) {
    return this.prisma.reviewItem.findFirst({ where: { id, tenantId, appId } });
  }

  async confirm(params: {
    tenantId: string;
    appId: string;
    reviewId: string;
    actorUserId?: string;
    actorEmail?: string;
    payloadOverride?: unknown;
  }) {
    const review = await this.prisma.reviewItem.findFirst({ where: { id: params.reviewId, tenantId: params.tenantId, appId: params.appId } });
    if (!review) throw new NotFoundException("Review not found");

    const payload = params.payloadOverride ?? review.proposedPayload;
    const updated = await this.prisma.reviewItem.update({
      where: { id: review.id },
      data: {
        status: "CONFIRMED",
        actorUserId: params.actorUserId,
        actorEmail: params.actorEmail,
        decidedAt: new Date(),
        proposedPayload: payload as never
      }
    });

    await this.crmAdapter.deliver({
      tenantId: params.tenantId,
      appId: params.appId,
      reviewItemId: updated.id,
      payload
    });

    await this.auditService.log({
      tenantId: params.tenantId,
      appId: params.appId,
      reviewItemId: updated.id,
      captureEventId: updated.captureEventId,
      eventType: "review_confirmed"
    });

    return updated;
  }

  async reject(params: {
    tenantId: string;
    appId: string;
    reviewId: string;
    actorUserId?: string;
    actorEmail?: string;
  }) {
    const review = await this.prisma.reviewItem.findFirst({ where: { id: params.reviewId, tenantId: params.tenantId, appId: params.appId } });
    if (!review) throw new NotFoundException("Review not found");

    const updated = await this.prisma.reviewItem.update({
      where: { id: review.id },
      data: {
        status: "REJECTED",
        actorUserId: params.actorUserId,
        actorEmail: params.actorEmail,
        decidedAt: new Date()
      }
    });

    await this.auditService.log({
      tenantId: params.tenantId,
      appId: params.appId,
      reviewItemId: updated.id,
      captureEventId: updated.captureEventId,
      eventType: "review_rejected"
    });

    return updated;
  }
}
