import { Module } from "@nestjs/common";
import { OutboxPrismaService } from "./outbox-prisma.service";
import { OutboxService } from "./outbox.service";
import { KafkaProducerService } from "./kafka-producer.service";
import { OutboxRelayService } from "./outbox-relay.service";

@Module({
  providers: [OutboxPrismaService, OutboxService, KafkaProducerService, OutboxRelayService],
  exports: [OutboxService, OutboxPrismaService, KafkaProducerService]
})
export class OutboxModule {}
