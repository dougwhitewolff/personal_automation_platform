/**
 * Serializable email blob stored in Postgres `outbox_emails.email_payload` (jsonb).
 * Dates are ISO strings for JSON compatibility.
 */
export type OutboxEmailPayload = {
  from: string;
  to: string;
  subject: string;
  headers: Record<string, string>;
  bodyText?: string;
  bodyHtml?: string;
  /** ISO 8601 */
  receivedAt: string;
  rawSourceRef?: string;
  attachments: Array<{
    filename: string;
    contentType: string;
    textContent?: string;
    size: number;
  }>;
};
