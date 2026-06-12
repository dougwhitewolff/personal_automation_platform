import { Module } from "@nestjs/common";
import { PrismaService } from "../infrastructure/prisma.service";
import { IntegrationsService } from "./integrations.service";
import { IntegrationsController } from "./integrations.controller";
import { M365GraphClient } from "./m365/m365-graph.client";
import { OutboxModule } from "../outbox/outbox.module";
import { OutboxService } from "../outbox/outbox.service";

@Module({
  imports: [OutboxModule],
  controllers: [IntegrationsController],
  providers: [
    M365GraphClient,
    {
      provide: IntegrationsService,
      inject: [PrismaService, OutboxService, M365GraphClient],
      useFactory: (
        prisma: PrismaService,
        outboxService: OutboxService,
        graphClient: M365GraphClient,
      ) => new IntegrationsService(prisma, outboxService, graphClient),
    },
  ],
  exports: [IntegrationsService],
})
export class IntegrationsModule {}
