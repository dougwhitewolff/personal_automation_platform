import { Module } from "@nestjs/common";
import { ReviewsService } from "./reviews.service";
import { ReviewsController } from "./reviews.controller";
import { PrismaService } from "../infrastructure/prisma.service";
import { AuditService } from "../audit/audit.service";
import { MockCrmAdapter } from "../adapters/crm/mock-crm.adapter";
import { ApiKeyGuard } from "../common/api-key.guard";

@Module({
  controllers: [ReviewsController],
  providers: [ReviewsService, PrismaService, AuditService, MockCrmAdapter, ApiKeyGuard],
  exports: [ReviewsService]
})
export class ReviewsModule {}
