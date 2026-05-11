import { Injectable } from "@nestjs/common";
import { PrismaService } from "../infrastructure/prisma.service";

@Injectable()
export class AuditService {
  constructor(private readonly prisma: PrismaService) {}

  async log(params: {
    tenantId: string;
    appId: string;
    eventType: string;
    captureEventId?: string;
    reviewItemId?: string;
    payload?: unknown;
  }) {
    return this.prisma.auditEvent.create({ data: params });
  }
}
