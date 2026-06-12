import { PrismaClient, TenantRouteKind } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const mailboxAddress = process.env.M365_USER_EMAIL?.trim().toLowerCase();
  const m365TenantId = process.env.M365_TENANT_ID?.trim();
  const m365ClientId = process.env.M365_CLIENT_ID?.trim();
  const m365ClientSecret = process.env.M365_CLIENT_SECRET?.trim();

  if (mailboxAddress && m365TenantId && m365ClientId && m365ClientSecret) {
    const watch = await prisma.mailboxWatch.upsert({
      where: { mailboxAddress },
      update: {
        m365TenantId,
        m365ClientId,
        m365ClientSecret,
        enabled: true,
        label: "Seed mailbox watch"
      },
      create: {
        mailboxAddress,
        m365TenantId,
        m365ClientId,
        m365ClientSecret,
        enabled: true,
        label: "Seed mailbox watch"
      }
    });
    console.log(`Mailbox watch: ${watch.mailboxAddress} (${watch.id})`);
  } else {
    console.warn(
      "Skipped mailbox_watches seed — set M365_USER_EMAIL, M365_TENANT_ID, M365_CLIENT_ID, M365_CLIENT_SECRET"
    );
  }

  const plaudSenderEmail =
    process.env.PLAUD_SENDER_EMAIL?.trim().toLowerCase() ?? "no-reply@plaud.ai";
  const crmTenantId = process.env.CRM_DEMO_TENANT_ID?.trim();

  if (crmTenantId) {
    const router = await prisma.tenantRouter.upsert({
      where: {
        routeKind_routeKey: {
          routeKind: TenantRouteKind.email,
          routeKey: plaudSenderEmail
        }
      },
      update: {
        crmTenantId,
        label: "Plaud sender → CRM tenant"
      },
      create: {
        routeKind: TenantRouteKind.email,
        routeKey: plaudSenderEmail,
        crmTenantId,
        label: "Plaud sender → CRM tenant"
      }
    });
    console.log(`Tenant router: ${router.routeKind}:${router.routeKey} → ${router.crmTenantId}`);
  } else {
    console.warn("Skipped tenant_routers seed — set CRM_DEMO_TENANT_ID");
  }

  console.log("Seed completed");
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
