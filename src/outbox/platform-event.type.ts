export type PlatformEventV1 = {
  schemaVersion: 1;
  eventType: string;
  source: string;
  occurredAt: string;
  correlationId: string;
  tenantId: string;
  payload: unknown;
};
