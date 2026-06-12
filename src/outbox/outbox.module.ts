import { Module } from "@nestjs/common";
import { PrismaService } from "../infrastructure/prisma.service";
import { OutboxService } from "./outbox.service";
import { KafkaProducerService } from "./kafka-producer.service";
import { OutboxRelayService } from "./outbox-relay.service";

@Module({
  providers: [
    KafkaProducerService,
    // Explicit factories: tsup bundles dist/main.js and breaks emitDecoratorMetadata for constructors.
    {
      provide: OutboxService,
      inject: [PrismaService],
      useFactory: (prisma: PrismaService) => new OutboxService(prisma),
    },
    {
      provide: OutboxRelayService,
      inject: [PrismaService, KafkaProducerService],
      useFactory: (prisma: PrismaService, kafka: KafkaProducerService) =>
        new OutboxRelayService(prisma, kafka),
    },
  ],
  exports: [OutboxService, KafkaProducerService],
})
export class OutboxModule {}
