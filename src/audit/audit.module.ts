import { Module } from "@nestjs/common";
import { AuditService } from "./audit.service";
import { PrismaService } from "../infrastructure/prisma.service";

@Module({
  providers: [AuditService, PrismaService],
  exports: [AuditService]
})
export class AuditModule {}
