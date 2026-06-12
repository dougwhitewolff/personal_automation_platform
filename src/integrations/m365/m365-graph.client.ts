import { Injectable, Logger } from "@nestjs/common";
import { GraphAttachment, GraphMessage } from "./m365.types";

export type M365MailboxCredentials = {
  m365TenantId: string;
  m365ClientId: string;
  m365ClientSecret: string;
};

@Injectable()
export class M365GraphClient {
  private readonly logger = new Logger(M365GraphClient.name);

  async fetchRecentMessages(
    credentials: M365MailboxCredentials,
    userEmail: string
  ): Promise<GraphMessage[]> {
    const token = await this.getToken(credentials);
    if (!token) return [];

    const endpoint = `https://graph.microsoft.com/v1.0/users/${encodeURIComponent(userEmail)}/messages?$top=10&$orderby=receivedDateTime desc`;
    const response = await fetch(endpoint, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (!response.ok) {
      this.logger.warn(`Graph messages fetch failed for ${userEmail}: ${response.status}`);
      return [];
    }

    const json = (await response.json()) as { value?: GraphMessage[] };
    return json.value ?? [];
  }

  async fetchAttachments(
    credentials: M365MailboxCredentials,
    userEmail: string,
    messageId: string
  ): Promise<GraphAttachment[]> {
    const token = await this.getToken(credentials);
    if (!token) return [];

    const endpoint = `https://graph.microsoft.com/v1.0/users/${encodeURIComponent(userEmail)}/messages/${messageId}/attachments`;
    const response = await fetch(endpoint, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (!response.ok) {
      this.logger.warn(`Graph attachment fetch failed for ${userEmail}: ${response.status}`);
      return [];
    }

    const json = (await response.json()) as { value?: GraphAttachment[] };
    return json.value ?? [];
  }

  private async getToken(credentials: M365MailboxCredentials): Promise<string | null> {
    const { m365TenantId, m365ClientId, m365ClientSecret } = credentials;
    if (!m365TenantId || !m365ClientId || !m365ClientSecret) {
      this.logger.warn("M365 mailbox credentials are incomplete; skipping Graph call");
      return null;
    }

    const tokenResponse = await fetch(
      `https://login.microsoftonline.com/${m365TenantId}/oauth2/v2.0/token`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "client_credentials",
          client_id: m365ClientId,
          client_secret: m365ClientSecret,
          scope: "https://graph.microsoft.com/.default"
        })
      }
    );

    if (!tokenResponse.ok) {
      this.logger.warn(`Token request failed for tenant ${m365TenantId}: ${tokenResponse.status}`);
      return null;
    }

    const tokenJson = (await tokenResponse.json()) as { access_token?: string };
    return tokenJson.access_token ?? null;
  }
}
