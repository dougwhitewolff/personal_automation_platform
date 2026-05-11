export type NormalizedEmail = {
  messageId: string;
  from: string;
  to: string;
  subject: string;
  headers: Record<string, string>;
  bodyText?: string;
  bodyHtml?: string;
  receivedAt: Date;
  rawSourceRef?: string;
  attachments: Array<{
    filename: string;
    contentType: string;
    textContent?: string;
    size: number;
  }>;
};
