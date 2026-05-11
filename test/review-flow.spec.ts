import { describe, expect, it, vi } from "vitest";
import { ReviewsService } from "../src/reviews/reviews.service";

describe("review flow", () => {
  it("confirms review and calls CRM adapter once", async () => {
    const prisma = {
      reviewItem: {
        findFirst: vi.fn().mockResolvedValue({
          id: "r1",
          tenantId: "t1",
          appId: "a1",
          captureEventId: "c1",
          proposedPayload: { hello: "world" }
        }),
        update: vi.fn().mockResolvedValue({
          id: "r1",
          captureEventId: "c1",
          proposedPayload: { hello: "world" }
        })
      }
    };

    const auditService = { log: vi.fn().mockResolvedValue(undefined) };
    const crmAdapter = { deliver: vi.fn().mockResolvedValue(undefined) };

    const service = new ReviewsService(prisma as never, auditService as never, crmAdapter as never);
    await service.confirm({ tenantId: "t1", appId: "a1", reviewId: "r1" });

    expect(crmAdapter.deliver).toHaveBeenCalledTimes(1);
    expect(auditService.log).toHaveBeenCalledTimes(1);
  });
});
