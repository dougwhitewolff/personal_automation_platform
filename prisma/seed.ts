import { PrismaClient, TenantRouteKind } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const mailboxAddress = process.env.M365_USER_EMAIL?.trim().toLowerCase();
  const m365TenantId = process.env.M365_TENANT_ID?.trim();
  const m365ClientId = process.env.M365_CLIENT_ID?.trim();
  const m365ClientSecret = process.env.M365_CLIENT_SECRET?.trim();
  const crmTenantId = process.env.CRM_DEMO_TENANT_ID?.trim();

  if (!crmTenantId) {
    console.warn("Skipped mailbox_watches seed — set CRM_DEMO_TENANT_ID");
    console.log("Seed completed");
    return;
  }

  if (!mailboxAddress || !m365TenantId || !m365ClientId || !m365ClientSecret) {
    console.warn(
      "Skipped mailbox_watches seed — set M365_USER_EMAIL, M365_TENANT_ID, M365_CLIENT_ID, M365_CLIENT_SECRET"
    );
    console.log("Seed completed");
    return;
  }

  const router = await prisma.tenantRouter.upsert({
    where: {
      routeKind_routeKey: {
        routeKind: TenantRouteKind.email,
        routeKey: mailboxAddress
      }
    },
    update: {
      crmTenantId,
      label: "Mailbox → CRM tenant"
    },
    create: {
      routeKind: TenantRouteKind.email,
      routeKey: mailboxAddress,
      crmTenantId,
      label: "Mailbox → CRM tenant"
    }
  });
  console.log(`Tenant router: ${router.routeKind}:${router.routeKey} → ${router.crmTenantId}`);

  const watch = await prisma.mailboxWatch.upsert({
    where: { mailboxAddress },
    update: {
      tenantRouterId: router.id,
      m365TenantId,
      m365ClientId,
      m365ClientSecret,
      enabled: true,
      label: "Seed mailbox watch"
    },
    create: {
      tenantRouterId: router.id,
      mailboxAddress,
      m365TenantId,
      m365ClientId,
      m365ClientSecret,
      enabled: true,
      label: "Seed mailbox watch"
    }
  });
  console.log(`Mailbox watch: ${watch.mailboxAddress} (${watch.id}) → router ${router.id}`);

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
