import { createHash } from "node:crypto";

/** Deterministic synthetic Graph-style id for dev ingest when no provider message id exists. */
export function stableDevProviderEmailId(parts: string[]): string {
  const h = createHash("sha256").update(parts.join("|"), "utf8").digest("hex").slice(0, 32);
  return `dev:${h}`;
}
