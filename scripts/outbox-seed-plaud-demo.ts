import { PrismaClient, TenantRouteKind } from "@prisma/client";
import * as fs from "fs";
import * as path from "path";
import { extractAddressFromFromHeader } from "../src/outbox/extract-source-email";

const DEMO_FROM = "noreply@plaud.ai";
const PLAUD_BODY_MARKER = "The original audio transcription is as follows:";

/** Demo spoken text for CRM Chad → leads.create (partial fields on purpose). */
const DEMO_TRANSCRIPT_LEAD = `I just finished a site visit with John Smith at Acme Roofing. He's interested in a full roof replacement, around twelve thousand dollars. His phone is 555-123-4567 and email is john.smith@acmeroofing.example. Source was a referral from our BNI group. Follow up next Tuesday.`;

/** Demo spoken text for CRM Chad → tasks.create. */
const DEMO_TRANSCRIPT_TASK = `Reminder for me: call John Smith at Acme Roofing tomorrow at 10 AM about the roof estimate we discussed. Make it a follow-up task, high priority.`;

/**
 * One transcript → multi-step plan: contacts.create → leads.create → tasks.create
 * (step refs like {{step1.id}}). Use for Plaud review queue end-to-end testing.
 */
const DEMO_TRANSCRIPT_COMBO = `Just met Maria Lopez from Lopez Fencing at the home show. Her phone is 555-987-6543 and email is maria@lopezfencing.example. They want a perimeter fence quote, around twenty thousand dollars. Set a follow-up for me next Friday to call her back about the estimate.`;

type DemoScenario = "lead" | "task" | "combo";

function parseScenarioArg(): DemoScenario {
  const flag = process.argv.find((a) => a.startsWith("--scenario="));
  const value = flag?.split("=")[1]?.toLowerCase();
  if (value === "lead") return "lead";
  if (value === "task") return "task";
  if (value === "combo" || value === "full" || value === "all") return "combo";
  return "combo";
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

function scenarioMeta(scenario: DemoScenario): {
  transcript: string;
  subject: string;
  expectHint: string;
} {
  switch (scenario) {
    case "task":
      return {
        transcript: DEMO_TRANSCRIPT_TASK,
        subject: "[Plaud-AutoFlow] Demo — follow-up task",
        expectHint: "Plan should include tasks.create (optionally linked to an existing lead)."
      };
    case "combo":
      return {
        transcript: DEMO_TRANSCRIPT_COMBO,
        subject: "[Plaud-AutoFlow] Demo — contact + lead + task",
        expectHint:
          "Plan should include contacts.create → leads.create → tasks.create with {{stepN.id}} dependencies. Confirm once to create all three."
      };
    default:
      return {
        transcript: DEMO_TRANSCRIPT_LEAD,
        subject: "[Plaud-AutoFlow] Demo — new lead site visit",
        expectHint: "Plan should center on leads.create (may include contact/task depending on LLM)."
      };
  }
}

async function main() {
  const prisma = new PrismaClient();
  const crmTenantId = process.env.CRM_DEMO_TENANT_ID;
  if (!crmTenantId) {
    console.error("CRM_DEMO_TENANT_ID is required in .env (CRM tenants.id UUID)");
    process.exit(1);
  }

  const scenario = parseScenarioArg();
  const { transcript, subject, expectHint } = scenarioMeta(scenario);

  const fixturePath = path.join(__dirname, "../docs/fixtures/plaud/sample-email-body.txt");
  const fixtureBody = fs.existsSync(fixturePath)
    ? fs.readFileSync(fixturePath, "utf-8")
    : null;
  const bodyText = buildPlaudEmailBody(transcript);

  const sourceEmail = extractAddressFromFromHeader(DEMO_FROM) ?? DEMO_FROM.toLowerCase();

  await prisma.tenantRouter.upsert({
    where: {
      routeKind_routeKey: { routeKind: TenantRouteKind.email, routeKey: sourceEmail }
    },
    create: {
      routeKind: TenantRouteKind.email,
      routeKey: sourceEmail,
      crmTenantId,
      label: "Demo Plaud → CRM tenant (seed script)"
    },
    update: {
      crmTenantId,
      label: "Demo Plaud → CRM tenant (seed script)"
    }
  });
  console.log(`Upserted tenant_routers: email:${sourceEmail} → ${crmTenantId}`);

  const providerEmailId = `demo-plaud-${scenario}-${Date.now()}`;
  const messageId = `demo-msg-${scenario}-${Date.now()}@plaud.demo`;

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
  console.log(`Expect: ${expectHint}`);
  console.log(`Transcript (${transcript.length} chars):`);
  console.log(transcript);
  if (fixtureBody) {
    console.log(`(Fixture file also available at docs/fixtures/plaud/sample-email-body.txt)`);
  }
  console.log(`Run the automation platform so the cron relay publishes to Kafka.`);
  console.log(`CRM expects payload.transcript on plaud.email.inbound events.`);
  console.log(
    `Usage: npx tsx scripts/outbox-seed-plaud-demo.ts [--scenario=combo|lead|task]`
  );
  console.log(`  combo (default): contact + lead + task in one plan`);
  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
