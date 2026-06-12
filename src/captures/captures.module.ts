import { Module } from "@nestjs/common";
import { CapturesService } from "./captures.service";
import { AuditService } from "../audit/audit.service";
import { ReviewsService } from "../reviews/reviews.service";
import { MockCrmAdapter } from "../adapters/crm/mock-crm.adapter";

@Module({
  providers: [CapturesService, AuditService, ReviewsService, MockCrmAdapter],
  exports: [CapturesService]
})
export class CapturesModule {}
