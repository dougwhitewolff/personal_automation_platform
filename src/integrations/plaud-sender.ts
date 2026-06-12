import { extractAddressFromFromHeader } from "../outbox/extract-source-email";

export function getPlaudSenderEmailFromEnv(): string | undefined {
  const configured = process.env.PLAUD_SENDER_EMAIL?.trim();
  return configured || undefined;
}

/** True when the From header matches PLAUD_SENDER_EMAIL (case-insensitive). */
export function matchesPlaudSender(fromHeader: string | undefined, configuredPlaudSenderEmail?: string): boolean {
  const expected = configuredPlaudSenderEmail?.trim().toLowerCase();
  if (!expected) {
    return false;
  }

  const fromAddress = extractAddressFromFromHeader(fromHeader);
  return fromAddress === expected;
}

export function extractFromFromEmailPayload(emailPayload: unknown): string | undefined {
  if (!emailPayload || typeof emailPayload !== "object") {
    return undefined;
  }
  const from = (emailPayload as { from?: unknown }).from;
  return typeof from === "string" ? from : undefined;
}
