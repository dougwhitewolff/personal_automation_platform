import type { NormalizedEmail } from "../integrations/normalized-email.type";
import type { OutboxEmailPayload } from "./outbox-email-payload.type";

export function normalizedEmailToOutboxPayload(email: NormalizedEmail): OutboxEmailPayload {
  return {
    from: email.from,
    to: email.to,
    subject: email.subject,
    headers: email.headers,
    bodyText: email.bodyText,
    bodyHtml: email.bodyHtml,
    receivedAt: email.receivedAt.toISOString(),
    rawSourceRef: email.rawSourceRef,
    attachments: email.attachments
  };
}
