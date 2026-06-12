import { logLevel, type KafkaConfig } from "kafkajs";

/** Split comma-separated broker list (Confluent bootstrap server or local). */
export function parseKafkaBrokers(raw: string): string[] {
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/** True when Confluent Cloud SASL credentials are configured. */
export function isKafkaSaslEnabled(saslUsername?: string | null): boolean {
  return Boolean(saslUsername?.trim());
}

/**
 * KafkaJS client config. Plaintext for local Docker; SASL_SSL when API key is set.
 */
export function buildKafkaJsConfig(params: {
  clientId: string;
  brokers: string[];
  saslUsername?: string | null;
  saslPassword?: string | null;
}): KafkaConfig {
  const config: KafkaConfig = {
    clientId: params.clientId,
    brokers: params.brokers,
    logLevel: logLevel.WARN
  };

  const username = params.saslUsername?.trim();
  if (username) {
    config.ssl = true;
    config.sasl = {
      mechanism: "plain",
      username,
      password: params.saslPassword?.trim() ?? ""
    };
  }

  return config;
}
