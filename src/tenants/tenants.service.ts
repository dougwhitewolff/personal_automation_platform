import { Injectable } from "@nestjs/common";
import { PrismaService } from "../infrastructure/prisma.service";

@Injectable()
export class TenantsService {
  constructor(private readonly prisma: PrismaService) {}

  findByClientEmail(clientEmail: string) {
    return this.prisma.tenant.findFirst({
      where: {
        clientEmail: clientEmail.toLowerCase()
      }
    });
  }
}
