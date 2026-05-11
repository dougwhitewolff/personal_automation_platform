import { PrismaClient } from "@prisma/client";
import { generateApiKey, hashApiKey } from "../src/common/api-key.util";

const prisma = new PrismaClient();

async function main() {
  const tenant = await prisma.tenant.upsert({
    where: { id: "seed-tenant" },
    update: { clientEmail: "client@example.com" },
    create: { id: "seed-tenant", name: "Default Tenant", clientEmail: "client@example.com" }
  });

  const app = await prisma.clientApp.upsert({
    where: { tenantId_slug: { tenantId: tenant.id, slug: "crm" } },
    update: {},
    create: {
      tenantId: tenant.id,
      name: "CRM",
      slug: "crm"
    }
  });

  await prisma.integration.upsert({
    where: { provider_mailboxAddress: { provider: "m365-graph", mailboxAddress: "doug@4trades.ai" } },
    update: { tenantId: tenant.id, appId: app.id },
    create: {
      tenantId: tenant.id,
      appId: app.id,
      provider: "m365-graph",
      mailboxAddress: "doug@4trades.ai"
    }
  });

  const key = generateApiKey();
  const salt = process.env.SERVICE_API_KEY_SALT ?? "dev-salt";
  const keyHash = hashApiKey(key.plaintext, salt);

  await prisma.serviceApiKey.create({
    data: {
      tenantId: tenant.id,
      appId: app.id,
      keyHash,
      keyPrefix: key.prefix,
      label: "seed-key",
      scopes: ["reviews:read", "reviews:write", "ingest:write"]
    }
  });

  console.log("Seed completed");
  console.log(`Tenant: ${tenant.id}`);
  console.log(`App: ${app.id}`);
  console.log(`API Key: ${key.plaintext}`);
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
