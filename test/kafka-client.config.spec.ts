import { describe, expect, it } from "vitest";
import {
  buildKafkaJsConfig,
  isKafkaSaslEnabled,
  parseKafkaBrokers
} from "../src/outbox/kafka-client.config";

describe("kafka-client.config", () => {
  it("parses comma-separated brokers", () => {
    expect(parseKafkaBrokers(" localhost:9092 , pkc-1.aws.confluent.cloud:9092 ")).toEqual([
      "localhost:9092",
      "pkc-1.aws.confluent.cloud:9092"
    ]);
  });

  it("uses plaintext when SASL username is unset", () => {
    const config = buildKafkaJsConfig({
      clientId: "test",
      brokers: ["localhost:9092"]
    });
    expect(config.ssl).toBeUndefined();
    expect(config.sasl).toBeUndefined();
  });

  it("enables SASL_SSL when API key is set", () => {
    const config = buildKafkaJsConfig({
      clientId: "test",
      brokers: ["pkc-1.aws.confluent.cloud:9092"],
      saslUsername: "api-key",
      saslPassword: "api-secret"
    });
    expect(config.ssl).toBe(true);
    expect(config.sasl).toEqual({
      mechanism: "plain",
      username: "api-key",
      password: "api-secret"
    });
    expect(isKafkaSaslEnabled("api-key")).toBe(true);
  });
});
