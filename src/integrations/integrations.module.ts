import { Module } from "@nestjs/common";
import { IntegrationsService } from "./integrations.service";
import { IntegrationsController } from "./integrations.controller";
import { PrismaService } from "../infrastructure/prisma.service";
import { M365GraphClient } from "./m365/m365-graph.client";
import { TenantsModule } from "../tenants/tenants.module";
import { OutboxModule } from "../outbox/outbox.module";

@Module({
  imports: [TenantsModule, OutboxModule],
  controllers: [IntegrationsController],
  providers: [IntegrationsService, PrismaService, M365GraphClient],
  exports: [IntegrationsService]
})
export class IntegrationsModule {}
