export type GraphMessage = {
  id: string;
  internetMessageId?: string;
  from?: { emailAddress?: { address?: string } };
  toRecipients?: Array<{ emailAddress?: { address?: string } }>;
  subject?: string;
  body?: { contentType?: string; content?: string };
  bodyPreview?: string;
  receivedDateTime?: string;
};

export type GraphAttachment = {
  name?: string;
  contentType?: string;
  size?: number;
  contentBytes?: string;
};
