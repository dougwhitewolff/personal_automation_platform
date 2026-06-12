import { Module } from "@nestjs/common";
import { MockCrmAdapter } from "./crm/mock-crm.adapter";
import { AuditService } from "../audit/audit.service";
@Module({
  providers: [MockCrmAdapter, AuditService],
  exports: [MockCrmAdapter]
})
export class AdaptersModule {}
