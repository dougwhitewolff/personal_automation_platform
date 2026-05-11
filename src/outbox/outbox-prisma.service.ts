import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from "@nestjs/common";
import { PrismaClient } from "@prisma/outbox-client";

@Injectable()
export class OutboxPrismaService extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(OutboxPrismaService.name);

  async onModuleInit(): Promise<void> {
    const url = process.env.DATABASE_URL_OUTBOX;
    if (!url?.trim()) {
      throw new Error("DATABASE_URL_OUTBOX is required for the Postgres outbox (see .env.example).");
    }
    await this.$connect();
    this.logger.log("Postgres outbox connection ready.");
  }

  async onModuleDestroy(): Promise<void> {
    await this.$disconnect();
  }
}
