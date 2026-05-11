import { Body, Controller, Post, UseGuards } from "@nestjs/common";
import { IntegrationsService } from "./integrations.service";
import { ApiKeyGuard } from "../common/api-key.guard";
import { RequestAuthContext } from "../common/request-auth-context.decorator";
import { AuthContext } from "../common/auth-context.type";

@Controller("integrations")
@UseGuards(ApiKeyGuard)
export class IntegrationsController {
  constructor(private readonly integrationsService: IntegrationsService) {}

  @Post("plaud/ingest")
  ingestPlaudForDev(
    @RequestAuthContext() ctx: AuthContext,
    @Body()
    body: {
      messageId?: string;
      /** Optional Graph-style id for dedupe in dev (otherwise derived deterministically). */
      providerEmailId?: string;
      from: string;
      to: string;
      subject: string;
      bodyText?: string;
      bodyHtml?: string;
      attachments?: Array<{ filename: string; contentType?: string; textContent?: string; size?: number }>;
    }
  ) {
    return this.integrationsService.ingestDevPayload(ctx, body);
  }
}
