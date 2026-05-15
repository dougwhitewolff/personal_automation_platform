import { Module } from "@nestjs/common";
import { ConfigModule } from "@nestjs/config";
import { ScheduleModule } from "@nestjs/schedule";
import { PrismaModule } from "./prisma/prisma.module";
import { CapturesModule } from "./captures/captures.module";
import { ReviewsModule } from "./reviews/reviews.module";
import { IntegrationsModule } from "./integrations/integrations.module";
import { AuditModule } from "./audit/audit.module";
import { WorkflowsModule } from "./workflows/workflows.module";
import { AdaptersModule } from "./adapters/adapters.module";
import { OutboxModule } from "./outbox/outbox.module";

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    ScheduleModule.forRoot(),
    PrismaModule,
    OutboxModule,
    IntegrationsModule,
    CapturesModule,
    ReviewsModule,
    AuditModule,
    WorkflowsModule,
    AdaptersModule
  ]
})
export class AppModule {}
