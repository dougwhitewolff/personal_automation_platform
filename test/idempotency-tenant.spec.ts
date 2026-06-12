import { describe, expect, it } from "vitest";

type CaptureRow = { id: string; tenantId: string; sourceMessageId: string };

function upsertCapture(rows: CaptureRow[], tenantId: string, sourceMessageId: string): CaptureRow[] {
  const exists = rows.find((x) => x.tenantId === tenantId && x.sourceMessageId === sourceMessageId);
  if (exists) return rows;
  return [...rows, { id: `${tenantId}-${sourceMessageId}`, tenantId, sourceMessageId }];
}

describe("idempotency and tenant isolation invariants", () => {
  it("does not duplicate capture for same tenant and source message", () => {
    let rows: CaptureRow[] = [];
    rows = upsertCapture(rows, "t1", "m1");
    rows = upsertCapture(rows, "t1", "m1");
    expect(rows).toHaveLength(1);
  });

  it("allows same source message across different tenants", () => {
    let rows: CaptureRow[] = [];
    rows = upsertCapture(rows, "t1", "m1");
    rows = upsertCapture(rows, "t2", "m1");
    expect(rows).toHaveLength(2);
  });
});
