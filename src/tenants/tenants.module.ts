import { Module } from "@nestjs/common";
import { TenantsService } from "./tenants.service";
import { PrismaService } from "../infrastructure/prisma.service";

@Module({
  providers: [TenantsService, PrismaService],
  exports: [TenantsService]
})
export class TenantsModule {}
