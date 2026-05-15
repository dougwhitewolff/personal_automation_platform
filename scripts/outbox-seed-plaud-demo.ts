import { PrismaClient } from "@prisma/client";
import * as fs from "fs";
import * as path from "path";
import { extractAddressFromFromHeader } from "../src/outbox/extract-source-email";

const DEMO_FROM = "noreply@plaud.ai";

async function main() {
  const prisma = new PrismaClient();
  const crmTenantId = process.env.CRM_DEMO_TENANT_ID;
  if (!crmTenantId) {
    console.error("CRM_DEMO_TENANT_ID is required in .env (CRM tenants.id UUID)");
    process.exit(1);
  }

  const fixturePath = path.join(__dirname, "../docs/fixtures/plaud/sample-email-body.txt");
  const bodyText = fs.existsSync(fixturePath) ? fs.readFileSync(fixturePath, "utf-8") : "Sample Plaud transcript...";

  const sourceEmail = extractAddressFromFromHeader(DEMO_FROM) ?? DEMO_FROM.toLowerCase();

  await prisma.crmTenantEmailMapping.upsert({
    where: { sourceEmail },
    create: {
      sourceEmail,
      crmTenantId,
      label: "Demo Plaud → CRM tenant (seed script)"
    },
    update: {
      crmTenantId,
      label: "Demo Plaud → CRM tenant (seed script)"
    }
  });
  console.log(`Upserted crm_tenant_email_mappings: ${sourceEmail} → ${crmTenantId}`);

  const providerEmailId = `demo-plaud-${Date.now()}`;
  const messageId = `demo-msg-${Date.now()}@plaud.demo`;

  const emailPayload = {
    from: `Plaud <${DEMO_FROM}>`,
    to: "user@demo.com",
    subject: "Your Plaud Note: Meeting with Client",
    headers: {},
    bodyText,
    receivedAt: new Date().toISOString(),
    attachments: []
  };

  const row = await prisma.outboxEmail.create({
    data: {
      tenantId: "demo-automation-tenant",
      appId: "demo-app",
      providerEmailId,
      messageId,
      emailPayload: emailPayload as object,
      status: "PENDING"
    }
  });

  console.log(`Created PENDING outbox_emails row: ${row.id}`);
  console.log(`Run the automation platform so the cron relay publishes to Kafka.`);
  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
