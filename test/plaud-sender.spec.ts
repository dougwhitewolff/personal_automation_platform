import { describe, expect, it } from "vitest";
import { matchesPlaudSender } from "../src/integrations/plaud-sender";

describe("matchesPlaudSender", () => {
  it("matches bare and display-name From headers case-insensitively", () => {
    expect(matchesPlaudSender("no-reply@plaud.ai", "no-reply@plaud.ai")).toBe(true);
    expect(matchesPlaudSender("Plaud <NO-REPLY@plaud.ai>", "no-reply@plaud.ai")).toBe(true);
  });

  it("rejects other senders", () => {
    expect(
      matchesPlaudSender("Microsoft365@communication.microsoft.com", "no-reply@plaud.ai")
    ).toBe(false);
  });

  it("returns false when configured sender is missing", () => {
    expect(matchesPlaudSender("no-reply@plaud.ai", undefined)).toBe(false);
  });
});
