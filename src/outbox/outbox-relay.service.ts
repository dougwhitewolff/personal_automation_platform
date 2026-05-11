import { Injectable, Logger } from "@nestjs/common";
import { Cron, CronExpression } from "@nestjs/schedule";
import { OutboxPrismaService } from "./outbox-prisma.service";
import { KafkaProducerService } from "./kafka-producer.service";

/** Placeholder for future enrichment between poll and Kafka. */
export type OutboxProcessingHook = (row: {
  id: string;
  tenantId: string;
  appId: string;
  integrationId: string | null;
  messageId: string;
  providerEmailId: string;
  emailPayload: unknown;
}) => Promise<{ emailPayload: unknown } | void>;

@Injectable()
export class OutboxRelayService {
  private readonly logger = new Logger(OutboxRelayService.name);

  constructor(
    private readonly outboxPrisma: OutboxPrismaService,
    private readonly kafka: KafkaProducerService
  ) {}

  /** Override in tests or future module wiring. */
  protected processingHook: OutboxProcessingHook | undefined;

  @Cron(CronExpression.EVERY_MINUTE)
  async relayPendingToKafka(): Promise<void> {
    if (!this.kafka.enabled) {
      return;
    }

    const batchSize = Number(process.env.OUTBOX_RELAY_BATCH_SIZE ?? "20");
    const maxAttempts = Number(process.env.OUTBOX_RELAY_MAX_ATTEMPTS ?? "15");
    const topic = process.env.KAFKA_OUTBOX_TOPIC ?? "automation.email.outbox.v1";

    const rows = await this.outboxPrisma.outboxEmail.findMany({
      where: { status: "PENDING" },
      orderBy: { createdAt: "asc" },
      take: Number.isFinite(batchSize) && batchSize > 0 ? batchSize : 20
    });

    for (const row of rows) {
      try {
        let emailPayload: unknown = row.emailPayload;
        if (this.processingHook) {
          const result = await this.processingHook({
            id: row.id,
            tenantId: row.tenantId,
            appId: row.appId,
            integrationId: row.integrationId,
            messageId: row.messageId,
            providerEmailId: row.providerEmailId,
            emailPayload: row.emailPayload
          });
          if (result?.emailPayload !== undefined) {
            emailPayload = result.emailPayload;
          }
        }

        const kafkaKey = `${row.tenantId}:${row.messageId}`;
        await this.kafka.sendJsonRecord({
          topic,
          key: kafkaKey,
          value: {
            messageId: row.messageId,
            tenantId: row.tenantId,
            appId: row.appId,
            integrationId: row.integrationId,
            outboxEmailId: row.id,
            providerEmailId: row.providerEmailId,
            email: emailPayload
          }
        });

        await this.outboxPrisma.outboxEmail.update({
          where: { id: row.id },
          data: {
            status: "SENT",
            publishedAt: new Date(),
            lastError: null
          }
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        const nextAttempts = row.attempts + 1;
        await this.outboxPrisma.outboxEmail.update({
          where: { id: row.id },
          data: {
            attempts: nextAttempts,
            lastError: message.slice(0, 2000),
            status: nextAttempts >= maxAttempts ? "FAILED" : "PENDING"
          }
        });
        this.logger.warn(`Outbox relay failed for ${row.id}: ${message}`);
      }
    }

    if (rows.length > 0) {
      this.logger.log(`Outbox relay processed ${rows.length} row(s)`);
    }
  }
}
