-- Link each mailbox watch to the tenant router that resolves its CRM tenant.

ALTER TABLE "mailbox_watches" ADD COLUMN "tenant_router_id" TEXT;

ALTER TABLE "mailbox_watches"
ADD CONSTRAINT "mailbox_watches_tenant_router_id_fkey"
FOREIGN KEY ("tenant_router_id") REFERENCES "tenant_routers"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
