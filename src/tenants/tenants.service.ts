import { Injectable } from "@nestjs/common";
import { PrismaService } from "../infrastructure/prisma.service";

@Injectable()
export class TenantsService {
  constructor(private readonly prisma: PrismaService) {}

  findByClientEmail(clientEmail: string) {
    return this.prisma.automationTenant.findFirst({
      where: {
        clientEmail: clientEmail.toLowerCase()
      }
    });
  }
}
