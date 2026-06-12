# Plaud Tier 1 — Sequential test script (automation platform → CRM)

Natural-language voice transcripts are seeded from the **automation platform** (real Plaud path: `outbox_emails` → relay → Kafka → CRM). No tracking codes — only names and companies, as field staff would speak.

## Prerequisites

| Service | Command |
|---------|---------|
| Automation platform DB | `cd personal_automation_platform_v2 && npx prisma migrate dev` |
| Platform app + Kafka | `npm run start:dev` (Kafka + `KAFKA_*` in `.env`) |
| CRM Docker | `cd 4TradesCRM/backend && docker compose up -d` |
| CRM backend | `npm run start:dev` — `OPENAI_API_KEY`, `KAFKA_BROKERS=localhost:9092` |
| CRM frontend | `npm run dev` — Dashboard → **Plaud Action Review Queue** |

**`.env` (automation platform):**

```env
CRM_DEMO_TENANT_ID=<uuid-from-4TradesCRM tenants table>
```

List scenarios:

```powershell
cd d:\personal_automation_platform_v2
npx tsx scripts/plaud-tier1-test-seed.ts list
```

---

## Suite A — Happy path (run in order)

Use one fictional customer throughout: **Maria Lopez** at **Lopez Fencing**.  
**Confirm each plan in the CRM before seeding the next step** so she exists for link/update/interaction tests.

| Step | Command | What you say (via Plaud) | What to verify in CRM |
|------|---------|------------------------|------------------------|
| **1** | `seed --scenario=new-customer` | New meeting + phone/email + fence quote + follow-up Friday | Multi-step plan: `contacts.create` → `leads.create` → `tasks.create` with `{{stepN.id}}`. **No** extra create steps prepended by backend. Confirm → creates Maria. |
| **2** | `seed --scenario=log-interaction` | Phone call today, cedar vs vinyl, log as call | `interactions.create` on Maria. No **Needs linking** if step 1 done. |
| **3** | `seed --scenario=update-lead` | Update Maria at Lopez Fencing — next stage + note about estimate email | `leads.update` with resolved id (name only). |
| **4** | `seed --scenario=follow-up-task` | Reminder: call Maria tomorrow 10 AM about fence quote | `tasks.create` with resolved `lead_id`. |
| **5** | `seed --scenario=add-site` | New site Backyard Gate, 220 Elm St, Round Rock TX | `sites.create` linked to Maria's contact. |

### One-shot happy path (optional)

Seeds all five outbox rows back-to-back (you still confirm each plan in CRM in order):

```powershell
npx tsx scripts/plaud-tier1-test-seed.ts run --suite=happy-path --delay-ms=3000
```

After each relay (~1 min), open the review queue, complete or reject, then wait for the next item.

---

## Suite B — Edge cases (independent)

Do **not** depend on Maria. Run anytime.

| Step | Command | Intent | Expected in CRM |
|------|---------|--------|-----------------|
| **E1** | `seed --scenario=update-missing-person` | Update **Robert McAllister** at **Northwind Builders** (never created) | `entityLink` / **Needs linking** on update step. Search or **Create Lead**. Confirm **blocked** until UUID. |
| **E2** | `seed --scenario=vague-follow-up` | "That guy from yesterday… call him back sometime" | Thin plan or `tasks.create` with `entityLink` / unsure. Review fallback — **not** backend auto-prepend of contact+lead. |

```powershell
npx tsx scripts/plaud-tier1-test-seed.ts run --suite=edge-cases
```

---

## Per-scenario seed commands

```powershell
cd d:\personal_automation_platform_v2

npx tsx scripts/plaud-tier1-test-seed.ts seed --scenario=new-customer
npx tsx scripts/plaud-tier1-test-seed.ts seed --scenario=log-interaction
npx tsx scripts/plaud-tier1-test-seed.ts seed --scenario=update-lead
npx tsx scripts/plaud-tier1-test-seed.ts seed --scenario=follow-up-task
npx tsx scripts/plaud-tier1-test-seed.ts seed --scenario=add-site
npx tsx scripts/plaud-tier1-test-seed.ts seed --scenario=update-missing-person
npx tsx scripts/plaud-tier1-test-seed.ts seed --scenario=vague-follow-up
```

---

## Verify relay + CRM ingest

**Automation platform**

- Outbox row `status` → `SENT` after relay cron (~1 minute)
- Logs: outbox relay + Kafka publish to `automation.platform.events.v1`

**CRM**

- Log: `Processed inbound event plaud.email.inbound`
- Log: Plaud processor staged execution plan
- UI: new row on **Plaud Action Review Queue**
- API: `GET http://localhost:4000/plaud-review?status=pending` (as admin)

**CRM automated checks**

```powershell
cd d:\4TradesCRM\backend
npm run test -- src/plaud-review/plaud-processor.service.spec.ts
cd d:\4TradesCRM\frontend
npx playwright test e2e/plaud-review-queue.spec.ts
```

---

## Regression checks

- [ ] No tracking codes required in any transcript
- [ ] Happy path 1→5: create, interact, update, task, site all work after confirm
- [ ] E1: update unknown name → linking UI, confirm blocked without UUID
- [ ] E2: vague note → fallback review, not automatic contact+lead prepend
- [ ] `leads.update` / `interactions.create` allowed (Tier 1 allowlist)

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No CRM plan | `OPENAI_API_KEY` missing; relay not run; wrong `CRM_DEMO_TENANT_ID` |
| Step 2+ links wrong person | Confirm step 1 first; check open leads list includes Maria |
| Outbox stuck PENDING | Platform not running or Kafka disabled |
| Duplicate skipped | Normal (idempotent correlation); use fresh seed |
