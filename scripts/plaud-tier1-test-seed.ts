/**
 * Plaud Tier 1 — sequential test seeds for the CRM review pipeline.
 *
 * Creates outbox_emails rows (same path as real Plaud mail). The platform relay
 * publishes plaud.email.inbound to Kafka; the CRM consumer parses and stages plans.
 *
 * All transcripts use natural language (names / companies only — no tracking codes).
 *
 * Usage (from personal_automation_platform_v2/):
 *   npx tsx scripts/plaud-tier1-test-seed.ts list
 *   npx tsx scripts/plaud-tier1-test-seed.ts seed --scenario=new-customer
 *   npx tsx scripts/plaud-tier1-test-seed.ts run --suite=happy-path
 *   npx tsx scripts/plaud-tier1-test-seed.ts run --suite=edge-cases
 *
 * Env (.env):
 *   CRM_DEMO_TENANT_ID  — CRM tenants.id UUID (required)
 *   PLAUD_SEED_DELAY_MS — pause between sequential seeds (default 0)
 */

import { PrismaClient, TenantRouteKind } from "@prisma/client";
import { extractAddressFromFromHeader } from "../src/outbox/extract-source-email";

const DEMO_FROM = "noreply@plaud.ai";
const PLAUD_BODY_MARKER = "The original audio transcription is as follows:";

/** Fictional customer used across the happy-path suite (create → interact → update). */
const MARIA = {
  name: "Maria Lopez",
  company: "Lopez Fencing",
  phone: "555-987-6543",
  email: "maria@lopezfencing.example",
};

export type ScenarioId =
  | "new-customer"
  | "log-interaction"
  | "update-lead"
  | "follow-up-task"
  | "add-site"
  | "roof-estimate"
  | "update-missing-person"
  | "vague-follow-up";

type ScenarioDef = {
  order: number;
  suite: "happy-path" | "edge-cases";
  label: string;
  subject: string;
  transcript: string;
  /** What to verify in CRM after ~15–30s */
  expectHint: string;
  /** Run only after these scenario ids (happy-path chain) */
  after?: ScenarioId[];
};

const SCENARIOS: Record<ScenarioId, ScenarioDef> = {
  "new-customer": {
    order: 1,
    suite: "happy-path",
    label: "1 — New customer (contacts + lead + task in one plan)",
    subject: "[Plaud-AutoFlow] Tier1 — new customer Maria Lopez",
    transcript: `Just met ${MARIA.name} from ${MARIA.company} at the home show. Her phone is ${MARIA.phone} and email is ${MARIA.email}. They want a perimeter fence quote, around twenty thousand dollars. Set a follow-up for me next Friday to call her back about the estimate.`,
    expectHint:
      "Plan should include contacts.create → leads.create → tasks.create with {{stepN.id}} deps. No extra prepend steps from backend.",
  },
  "log-interaction": {
    order: 2,
    suite: "happy-path",
    label: "2 — Log call on existing customer (interactions.create)",
    subject: "[Plaud-AutoFlow] Tier1 — log call Maria Lopez",
    transcript: `Had a good phone call with ${MARIA.name} at ${MARIA.company} today. We talked about cedar versus vinyl and she wants material samples sent over. Log that as a call.`,
    expectHint:
      "interactions.create linked to Maria (UUID from open leads). No entityLink if she exists from step 1.",
    after: ["new-customer"],
  },
  "update-lead": {
    order: 3,
    suite: "happy-path",
    label: "3 — Update existing lead by name (leads.update)",
    subject: "[Plaud-AutoFlow] Tier1 — update Maria Lopez lead",
    transcript: `Update ${MARIA.name} at ${MARIA.company} — move her to the next pipeline stage and add a note that we emailed the estimate yesterday.`,
    expectHint:
      "leads.update with resolved id (name match). No tracking code in transcript.",
    after: ["new-customer"],
  },
  "follow-up-task": {
    order: 4,
    suite: "happy-path",
    label: "4 — Task on existing lead (tasks.create)",
    subject: "[Plaud-AutoFlow] Tier1 — follow-up task Maria Lopez",
    transcript: `Reminder for me: call ${MARIA.name} at ${MARIA.company} tomorrow at ten in the morning about the fence quote we discussed.`,
    expectHint: "tasks.create with lead_id resolved to Maria's lead. Assignee defaults to actor.",
    after: ["new-customer"],
  },
  "add-site": {
    order: 5,
    suite: "happy-path",
    label: "5 — New site for existing contact (sites.create)",
    subject: "[Plaud-AutoFlow] Tier1 — site for Maria Lopez",
    transcript: `Add another job site for ${MARIA.name} at ${MARIA.company} — backyard gate area, name Backyard Gate, address 220 Elm Street, Round Rock Texas 78664.`,
    expectHint: "sites.create with contact_id linked to Maria. Confirm in review then check Sites.",
    after: ["new-customer"],
  },
  "roof-estimate": {
    order: 6,
    suite: "happy-path",
    label: "6 — Roof site visit → Estimate Builder (estimates.review)",
    subject: "[Plaud-AutoFlow] Tier1 — roof estimate Maria Lopez",
    transcript: `Vance here, inspecting the front elevation field area. Wind uplift has completely sheared off a massive section of 3-tab shingles, easily a 10-by-12-foot patch. The asphalt underlayment is exposed and showing signs of dry rot, meaning water has been getting through for a minute. The plywood decking beneath looks stable but we have exposed nail heads rusted out. Will need to include full deck inspection and re-shingling of this entire slope on the estimate. Checking the western valley intersection. The metal valley lining is badly deteriorated, heavily weathered, and lifting away from the shingles on both sides. Slate tiles flanking the valley are cracking, and several edges have completely broken off into the channel. This is the primary bottleneck where the interior leak is originating. We need a clean tear-out of this valley, new ice and water shield, and full flashing replacement.`,
    expectHint:
      "estimates.review (and possibly interactions.create). CRM needs features.estimateBuilder enabled. Review queue → pick lead/estimate → Open Estimate Builder with transcript prefilled.",
    after: ["new-customer"],
  },
  "update-missing-person": {
    order: 1,
    suite: "edge-cases",
    label: "E1 — Update someone not in CRM (entityLink fallback)",
    subject: "[Plaud-AutoFlow] Tier1 — update unknown Robert",
    transcript: `Update Robert McAllister at Northwind Builders — change his phone to 555-000-9999 and set next follow-up to next Monday.`,
    expectHint:
      "leads.update or contacts.update with entityLink / Needs linking. Confirm blocked until UUID. No auto-prepend of create steps unless LLM explicitly plans them.",
  },
  "vague-follow-up": {
    order: 2,
    suite: "edge-cases",
    label: "E2 — Vague reference (entityLink or thin plan)",
    subject: "[Plaud-AutoFlow] Tier1 — vague follow-up",
    transcript: `Need to follow up with that guy from yesterday about the thing we talked about. Maybe call him back sometime next week.`,
    expectHint:
      "tasks.create or defer: entityLink with unsure/not_found, or skipped/failed if LLM cannot plan. Review UI should offer search + Create Lead — not backend prepend.",
  },
};

function buildPlaudEmailBody(transcript: string): string {
  return [
    "The transcript is brief, no summary is needed.",
    PLAUD_BODY_MARKER,
    "",
    "Speaker 1 00:00:00",
    transcript,
  ].join("\n");
}

function parseArgs(argv: string[]) {
  const cmd = argv[0] ?? "help";
  const flags: Record<string, string> = {};
  for (const arg of argv.slice(1)) {
    if (arg.startsWith("--")) {
      const [k, v] = arg.slice(2).split("=");
      flags[k] = v ?? "true";
    }
  }
  return { cmd, flags };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function seedScenario(
  prisma: PrismaClient,
  crmTenantId: string,
  scenarioId: ScenarioId
): Promise<string> {
  const def = SCENARIOS[scenarioId];
  const bodyText = buildPlaudEmailBody(def.transcript);
  const sourceEmail = extractAddressFromFromHeader(DEMO_FROM) ?? DEMO_FROM.toLowerCase();

  await prisma.tenantRouter.upsert({
    where: {
      routeKind_routeKey: { routeKind: TenantRouteKind.email, routeKey: sourceEmail },
    },
    create: {
      routeKind: TenantRouteKind.email,
      routeKey: sourceEmail,
      crmTenantId,
      label: "Plaud Tier 1 test → CRM tenant",
    },
    update: { crmTenantId, label: "Plaud Tier 1 test → CRM tenant" },
  });

  const providerEmailId = `tier1-${scenarioId}-${Date.now()}`;
  const messageId = `tier1-msg-${scenarioId}-${Date.now()}@plaud.demo`;

  const emailPayload = {
    from: `Plaud <${DEMO_FROM}>`,
    to: "user@demo.com",
    subject: def.subject,
    headers: {},
    bodyText,
    transcript: def.transcript,
    receivedAt: new Date().toISOString(),
    attachments: [],
    tier1Scenario: scenarioId,
  };

  const row = await prisma.outboxEmail.create({
    data: {
      tenantId: "demo-automation-tenant",
      appId: "demo-app",
      crmTenantId,
      providerEmailId,
      messageId,
      emailPayload: emailPayload as object,
      status: "PENDING",
    },
  });

  return row.id;
}

function printList() {
  console.log("\n=== Happy path (run in order; confirm each in CRM before the next) ===\n");
  const happy = Object.entries(SCENARIOS)
    .filter(([, d]) => d.suite === "happy-path")
    .sort((a, b) => a[1].order - b[1].order);
  for (const [id, d] of happy) {
    const deps = d.after?.length ? `  (after: ${d.after.join(", ")})` : "";
    console.log(`  ${d.order}. ${id}${deps}`);
    console.log(`     ${d.label}`);
    console.log(`     Expect: ${d.expectHint}\n`);
  }

  console.log("=== Edge cases (any order; separate from Maria) ===\n");
  const edge = Object.entries(SCENARIOS)
    .filter(([, d]) => d.suite === "edge-cases")
    .sort((a, b) => a[1].order - b[1].order);
  for (const [id, d] of edge) {
    console.log(`  ${d.order}. ${id}`);
    console.log(`     ${d.label}`);
    console.log(`     Expect: ${d.expectHint}\n`);
  }
}

function printHelp() {
  console.log(`
Plaud Tier 1 test seed (automation platform → Kafka → CRM)

Commands:
  list
  seed --scenario=<id>
  run --suite=happy-path|edge-cases|all

Scenarios:
${Object.keys(SCENARIOS)
  .map((id) => `  ${id}`)
  .join("\n")}

Prerequisites:
  1. CRM_DEMO_TENANT_ID in .env
  2. Automation platform running (npm run start:dev) with Kafka enabled
  3. CRM backend running with OPENAI_API_KEY and Kafka consumer
  4. For happy-path steps 2–5: confirm step 1 in CRM first so Maria exists

Example:
  npx tsx scripts/plaud-tier1-test-seed.ts run --suite=happy-path --delay-ms=5000
`);
}

async function main() {
  const { cmd, flags } = parseArgs(process.argv.slice(2));

  if (cmd === "help" || cmd === "--help") {
    printHelp();
    return;
  }

  if (cmd === "list") {
    printList();
    return;
  }

  const crmTenantId = process.env.CRM_DEMO_TENANT_ID;
  if (!crmTenantId) {
    console.error("CRM_DEMO_TENANT_ID is required in .env");
    process.exit(1);
  }

  const prisma = new PrismaClient();
  const delayMs = Number(process.env.PLAUD_SEED_DELAY_MS ?? flags["delay-ms"] ?? 0);

  try {
    if (cmd === "seed") {
      const scenarioId = flags.scenario as ScenarioId;
      if (!scenarioId || !SCENARIOS[scenarioId]) {
        console.error("Use --scenario=<id>. Run `list` for ids.");
        process.exit(1);
      }
      const def = SCENARIOS[scenarioId];
      console.log(def.label);
      const outboxId = await seedScenario(prisma, crmTenantId, scenarioId);
      console.log(`Created outbox_emails: ${outboxId}`);
      console.log(`Transcript:\n${def.transcript}\n`);
      console.log("Wait for relay (~1 min) or trigger relay cron, then check CRM Plaud Review Queue.");
      return;
    }

    if (cmd === "run") {
      const suite = flags.suite ?? "happy-path";
      const ids = Object.entries(SCENARIOS)
        .filter(([, d]) => suite === "all" || d.suite === suite)
        .sort((a, b) => a[1].order - b[1].order)
        .map(([id]) => id as ScenarioId);

      if (ids.length === 0) {
        console.error(`Unknown suite: ${suite}`);
        process.exit(1);
      }

      console.log(`Seeding suite "${suite}" (${ids.length} scenario(s))…\n`);
      if (suite === "happy-path") {
        console.log(
          "IMPORTANT: After each seed, confirm the plan in CRM before the next step so Maria Lopez exists for link/update tests.\n"
        );
      }

      for (let i = 0; i < ids.length; i++) {
        const id = ids[i];
        const def = SCENARIOS[id];
        console.log(`--- [${i + 1}/${ids.length}] ${def.label} ---`);
        const outboxId = await seedScenario(prisma, crmTenantId, id);
        console.log(`  outbox id: ${outboxId}`);
        console.log(`  expect: ${def.expectHint}`);
        if (i < ids.length - 1 && delayMs > 0) {
          console.log(`  waiting ${delayMs}ms…`);
          await sleep(delayMs);
        }
      }

      console.log("\nDone. Ensure automation platform relay published rows (status SENT).");
      return;
    }

    printHelp();
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
