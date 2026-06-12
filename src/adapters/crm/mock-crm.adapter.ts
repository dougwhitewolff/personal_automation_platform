import { Injectable } from "@nestjs/common";
import { AuditService } from "../../audit/audit.service";

@Injectable()
export class MockCrmAdapter {
  constructor(private readonly auditService: AuditService) {}

  async deliver(params: {
    tenantId: string;
    appId: string;
    reviewItemId: string;
    payload: unknown;
  }): Promise<void> {
    await this.auditService.log({
      tenantId: params.tenantId,
      appId: params.appId,
      reviewItemId: params.reviewItemId,
      eventType: "crm_delivery_succeeded",
      payload: params.payload
    });
  }
}
