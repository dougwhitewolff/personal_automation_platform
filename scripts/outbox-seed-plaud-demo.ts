import { PrismaClient } from "@prisma/client";
import * as fs from "fs";
import * as path from "path";
import { extractAddressFromFromHeader } from "../src/outbox/extract-source-email";

const DEMO_FROM = "noreply@plaud.ai";
const PLAUD_BODY_MARKER = "The original audio transcription is as follows:";

/** Demo spoken text for CRM Chad → leads.create (partial fields on purpose). */
const DEMO_TRANSCRIPT_LEAD = `I just finished a site visit with John Smith at Acme Roofing. He's interested in a full roof replacement, around twelve thousand dollars. His phone is 555-123-4567 and email is john.smith@acmeroofing.example. Source was a referral from our BNI group. Follow up next Tuesday.`;

/** Demo spoken text for CRM Chad → tasks.create. */
const DEMO_TRANSCRIPT_TASK = `Reminder for me: call John Smith at Acme Roofing tomorrow at 10 AM about the roof estimate we discussed. Make it a follow-up task, high priority.`;

type DemoScenario = "lead" | "task";

function parseScenarioArg(): DemoScenario {
  const flag = process.argv.find((a) => a.startsWith("--scenario="));
  const value = flag?.split("=")[1]?.toLowerCase();
  if (value === "task") return "task";
  return "lead";
}

function buildPlaudEmailBody(transcript: string): string {
  return [
    "The transcript is brief, no summary is needed.",
    PLAUD_BODY_MARKER,
    "",
    "Speaker 1 00:00:00",
    transcript
  ].join("\n");
}

async function main() {
  const prisma = new PrismaClient();
  const crmTenantId = process.env.CRM_DEMO_TENANT_ID;
  if (!crmTenantId) {
    console.error("CRM_DEMO_TENANT_ID is required in .env (CRM tenants.id UUID)");
    process.exit(1);
  }

  const scenario = parseScenarioArg();
  const transcript =
    scenario === "task" ? DEMO_TRANSCRIPT_TASK : DEMO_TRANSCRIPT_LEAD;

  const fixturePath = path.join(__dirname, "../docs/fixtures/plaud/sample-email-body.txt");
  const fixtureBody = fs.existsSync(fixturePath)
    ? fs.readFileSync(fixturePath, "utf-8")
    : null;
  const bodyText = buildPlaudEmailBody(transcript);

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

  const providerEmailId = `demo-plaud-${scenario}-${Date.now()}`;
  const messageId = `demo-msg-${scenario}-${Date.now()}@plaud.demo`;

  const subject =
    scenario === "task"
      ? "[Plaud-AutoFlow] Demo — follow-up task"
      : "[Plaud-AutoFlow] Demo — new lead site visit";

  const emailPayload = {
    from: `Plaud <${DEMO_FROM}>`,
    to: "user@demo.com",
    subject,
    headers: {},
    bodyText,
    /** Canonical field for CRM Plaud review pipeline (payload.transcript on Kafka). */
    transcript,
    receivedAt: new Date().toISOString(),
    attachments: [],
    demoScenario: scenario
  };

  const row = await prisma.outboxEmail.create({
    data: {
      tenantId: "demo-automation-tenant",
      appId: "demo-app",
      crmTenantId,
      providerEmailId,
      messageId,
      emailPayload: emailPayload as object,
      status: "PENDING"
    }
  });

  console.log(`Created PENDING outbox_emails row: ${row.id}`);
  console.log(`Scenario: ${scenario}`);
  console.log(`Transcript (${transcript.length} chars):`);
  console.log(transcript);
  if (fixtureBody) {
    console.log(`(Fixture file also available at docs/fixtures/plaud/sample-email-body.txt)`);
  }
  console.log(`Run the automation platform so the cron relay publishes to Kafka.`);
  console.log(`CRM expects payload.transcript on plaud.email.inbound events.`);
  console.log(`Usage: npx ts-node scripts/outbox-seed-plaud-demo.ts [--scenario=lead|task]`);
  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
