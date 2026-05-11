import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from "@nestjs/common";
import { Kafka, logLevel, type Producer } from "kafkajs";

@Injectable()
export class KafkaProducerService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(KafkaProducerService.name);
  private kafka: Kafka | null = null;
  private producer: Producer | null = null;

  private get brokers(): string[] {
    const raw = process.env.KAFKA_BROKERS ?? "";
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  get enabled(): boolean {
    return this.brokers.length > 0;
  }

  async onModuleInit(): Promise<void> {
    if (!this.enabled) {
      this.logger.warn("KAFKA_BROKERS not set — outbox relay will not publish (messages stay PENDING).");
      return;
    }
    const clientId = process.env.KAFKA_CLIENT_ID ?? "personal-automation-platform";
    this.kafka = new Kafka({
      clientId,
      brokers: this.brokers,
      logLevel: logLevel.WARN
    });
    this.producer = this.kafka.producer({
      allowAutoTopicCreation: true,
      idempotent: true,
      maxInFlightRequests: 1
    });
    await this.producer.connect();
    this.logger.log(`Kafka producer connected to ${this.brokers.join(", ")}`);
  }

  async onModuleDestroy(): Promise<void> {
    if (this.producer) {
      await this.producer.disconnect();
    }
  }

  async sendJsonRecord(params: { topic: string; key: string; value: object }): Promise<void> {
    if (!this.producer) {
      throw new Error("Kafka producer is not configured (set KAFKA_BROKERS).");
    }
    const value = JSON.stringify(params.value);
    await this.producer.send({
      topic: params.topic,
      messages: [{ key: params.key, value }]
    });
  }
}
