import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from "@nestjs/common";
import { Kafka, type Producer } from "kafkajs";
import { buildKafkaJsConfig, isKafkaSaslEnabled, parseKafkaBrokers } from "./kafka-client.config";

@Injectable()
export class KafkaProducerService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(KafkaProducerService.name);
  private kafka: Kafka | null = null;
  private producer: Producer | null = null;

  private get brokers(): string[] {
    return parseKafkaBrokers(process.env.KAFKA_BROKERS ?? "");
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
    this.kafka = new Kafka(
      buildKafkaJsConfig({
        clientId,
        brokers: this.brokers,
        saslUsername: process.env.KAFKA_SASL_USERNAME,
        saslPassword: process.env.KAFKA_SASL_PASSWORD
      })
    );
    this.producer = this.kafka.producer({
      allowAutoTopicCreation: !isKafkaSaslEnabled(process.env.KAFKA_SASL_USERNAME),
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
