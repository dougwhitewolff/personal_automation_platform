import type { PrismaService } from "../infrastructure/prisma.service";
import { extractAddressFromFromHeader } from "../outbox/extract-source-email";
import { TenantRouteKind } from "@prisma/client";

export async function resolveCrmTenantIdFromRouter(
  prisma: PrismaService,
  routeKind: TenantRouteKind,
  routeKey: string
): Promise<string | null> {
  const normalizedKey = routeKey.trim().toLowerCase();
  if (!normalizedKey) {
    return null;
  }

  const row = await prisma.tenantRouter.findUnique({
    where: {
      routeKind_routeKey: {
        routeKind,
        routeKey: normalizedKey
      }
    }
  });

  return row?.crmTenantId ?? null;
}

export async function resolveCrmTenantIdFromEmailFrom(
  prisma: PrismaService,
  fromHeader: string | undefined
): Promise<string | null> {
  const address = extractAddressFromFromHeader(fromHeader);
  if (!address) {
    return null;
  }

  return resolveCrmTenantIdFromRouter(prisma, TenantRouteKind.email, address);
}
