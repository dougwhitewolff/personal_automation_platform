import { Injectable, Logger } from "@nestjs/common";
import { GraphAttachment, GraphMessage } from "./m365.types";

@Injectable()
export class M365GraphClient {
  private readonly logger = new Logger(M365GraphClient.name);

  async fetchRecentMessages(userEmail: string): Promise<GraphMessage[]> {
    const token = await this.getToken();
    if (!token) return [];

    const endpoint = `https://graph.microsoft.com/v1.0/users/${encodeURIComponent(userEmail)}/messages?$top=10&$orderby=receivedDateTime desc`;
    const response = await fetch(endpoint, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (!response.ok) {
      this.logger.warn(`Graph messages fetch failed: ${response.status}`);
      return [];
    }

    const json = (await response.json()) as { value?: GraphMessage[] };
    return json.value ?? [];
  }

  async fetchAttachments(userEmail: string, messageId: string): Promise<GraphAttachment[]> {
    const token = await this.getToken();
    if (!token) return [];

    const endpoint = `https://graph.microsoft.com/v1.0/users/${encodeURIComponent(userEmail)}/messages/${messageId}/attachments`;
    const response = await fetch(endpoint, {
      headers: { Authorization: `Bearer ${token}` }
    });

    if (!response.ok) {
      this.logger.warn(`Graph attachment fetch failed: ${response.status}`);
      return [];
    }

    const json = (await response.json()) as { value?: GraphAttachment[] };
    return json.value ?? [];
  }

  private async getToken(): Promise<string | null> {
    const tenantId = process.env.M365_TENANT_ID;
    const clientId = process.env.M365_CLIENT_ID;
    const clientSecret = process.env.M365_CLIENT_SECRET;
    if (!tenantId || !clientId || !clientSecret) {
      this.logger.warn("M365 creds are missing; skipping mailbox poll");
      return null;
    }

    const tokenResponse = await fetch(`https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "client_credentials",
        client_id: clientId,
        client_secret: clientSecret,
        scope: "https://graph.microsoft.com/.default"
      })
    });

    if (!tokenResponse.ok) {
      this.logger.warn(`Token request failed: ${tokenResponse.status}`);
      return null;
    }

    const tokenJson = (await tokenResponse.json()) as { access_token?: string };
    return tokenJson.access_token ?? null;
  }
}
