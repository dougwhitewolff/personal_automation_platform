import { Module } from "@nestjs/common";
import { MockCrmAdapter } from "./crm/mock-crm.adapter";
import { AuditService } from "../audit/audit.service";
import { PrismaService } from "../infrastructure/prisma.service";

@Module({
  providers: [MockCrmAdapter, AuditService, PrismaService],
  exports: [MockCrmAdapter]
})
export class AdaptersModule {}
