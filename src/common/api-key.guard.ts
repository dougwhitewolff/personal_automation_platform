import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from "@nestjs/common";
import { PrismaService } from "../infrastructure/prisma.service";
import { hashApiKey } from "./api-key.util";

@Injectable()
export class ApiKeyGuard implements CanActivate {
  constructor(private readonly prisma: PrismaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const header = request.headers["x-api-key"];
    if (!header || typeof header !== "string") {
      throw new UnauthorizedException("Missing x-api-key header");
    }

    const salt = process.env.SERVICE_API_KEY_SALT ?? "dev-salt";
    const keyHash = hashApiKey(header, salt);

    const apiKey = await this.prisma.serviceApiKey.findFirst({ where: { keyHash } });
    if (!apiKey) {
      throw new UnauthorizedException("Invalid API key");
    }

    request.authContext = {
      tenantId: apiKey.tenantId,
      appId: apiKey.appId,
      actorUserId: request.headers["x-actor-user-id"] as string | undefined,
      actorEmail: request.headers["x-actor-email"] as string | undefined
    };

    return true;
  }
}
