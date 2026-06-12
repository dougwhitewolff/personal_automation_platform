import {
  sanitizeOptionalPostgresText,
  sanitizePostgresText
} from "../common/sanitize-postgres-text";
import type { NormalizedEmail } from "../integrations/normalized-email.type";
import type { OutboxEmailPayload } from "./outbox-email-payload.type";

function sanitizeHeaders(headers: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(headers).map(([key, value]) => [sanitizePostgresText(key), sanitizePostgresText(value)])
  );
}

export function normalizedEmailToOutboxPayload(email: NormalizedEmail): OutboxEmailPayload {
  return {
    from: sanitizePostgresText(email.from),
    to: sanitizePostgresText(email.to),
    subject: sanitizePostgresText(email.subject),
    headers: sanitizeHeaders(email.headers),
    bodyText: sanitizeOptionalPostgresText(email.bodyText),
    bodyHtml: sanitizeOptionalPostgresText(email.bodyHtml),
    receivedAt: email.receivedAt.toISOString(),
    rawSourceRef: sanitizeOptionalPostgresText(email.rawSourceRef),
    attachments: email.attachments.map((attachment) => ({
      filename: sanitizePostgresText(attachment.filename),
      contentType: sanitizePostgresText(attachment.contentType),
      textContent: sanitizeOptionalPostgresText(attachment.textContent),
      size: attachment.size
    }))
  };
}
