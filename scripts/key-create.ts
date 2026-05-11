import { PrismaClient } from "@prisma/client";
import { generateApiKey, hashApiKey } from "../src/common/api-key.util";

const prisma = new PrismaClient();

async function main() {
  const tenantId = process.argv[2];
  const appId = process.argv[3];
  const label = process.argv[4] ?? "manual-key";

  if (!tenantId || !appId) {
    throw new Error("Usage: npm run key:create -- <tenantId> <appId> [label]");
  }

  const key = generateApiKey();
  const salt = process.env.SERVICE_API_KEY_SALT ?? "dev-salt";

  await prisma.serviceApiKey.create({
    data: {
      tenantId,
      appId,
      keyHash: hashApiKey(key.plaintext, salt),
      keyPrefix: key.prefix,
      label,
      scopes: ["reviews:read", "reviews:write", "ingest:write"]
    }
  });

  console.log(`Created API key: ${key.plaintext}`);
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
