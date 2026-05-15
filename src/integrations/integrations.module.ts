import { Module } from "@nestjs/common";
import { PrismaService } from "../infrastructure/prisma.service";
import { IntegrationsService } from "./integrations.service";
import { IntegrationsController } from "./integrations.controller";
import { M365GraphClient } from "./m365/m365-graph.client";
import { TenantsModule } from "../tenants/tenants.module";
import { OutboxModule } from "../outbox/outbox.module";
import { OutboxService } from "../outbox/outbox.service";
import { TenantsService } from "../tenants/tenants.service";

@Module({
  imports: [TenantsModule, OutboxModule],
  controllers: [IntegrationsController],
  providers: [
    M365GraphClient,
    {
      provide: IntegrationsService,
      inject: [PrismaService, OutboxService, M365GraphClient, TenantsService],
      useFactory: (
        prisma: PrismaService,
        outboxService: OutboxService,
        graphClient: M365GraphClient,
        tenantsService: TenantsService,
      ) => new IntegrationsService(prisma, outboxService, graphClient, tenantsService),
    },
  ],
  exports: [IntegrationsService],
})
export class IntegrationsModule {}
