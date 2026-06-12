import { Body, Controller, Post } from "@nestjs/common";
import { IntegrationsService } from "./integrations.service";

@Controller("integrations")
export class IntegrationsController {
  constructor(private readonly integrationsService: IntegrationsService) {}

  @Post("plaud/ingest")
  ingestPlaudForDev(
    @Body()
    body: {
      messageId?: string;
      providerEmailId?: string;
      from: string;
      to: string;
      subject: string;
      bodyText?: string;
      bodyHtml?: string;
      attachments?: Array<{ filename: string; contentType?: string; textContent?: string; size?: number }>;
    }
  ) {
    return this.integrationsService.ingestDevPayload(body);
  }
}
