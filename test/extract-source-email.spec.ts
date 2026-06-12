import { describe, expect, it } from "vitest";
import { extractAddressFromFromHeader } from "../src/outbox/extract-source-email";

describe("extractAddressFromFromHeader", () => {
  it("parses angle-bracket form", () => {
    expect(extractAddressFromFromHeader("Plaud <noreply@plaud.ai>")).toBe("noreply@plaud.ai");
  });

  it("parses plain email", () => {
    expect(extractAddressFromFromHeader("noreply@plaud.ai")).toBe("noreply@plaud.ai");
  });

  it("lowercases result", () => {
    expect(extractAddressFromFromHeader("User <User@Example.COM>")).toBe("user@example.com");
  });

  it("returns null for empty", () => {
    expect(extractAddressFromFromHeader("")).toBeNull();
    expect(extractAddressFromFromHeader(null)).toBeNull();
  });
});
