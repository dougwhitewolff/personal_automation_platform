import { describe, expect, it } from "vitest";
import { fallbackSourceMessageId, parsePlaudEmail } from "../src/captures/plaud-parser";

describe("parsePlaudEmail", () => {
  it("extracts transcript and summary from attachments", () => {
    const result = parsePlaudEmail({
      from: "no-reply@plaud.ai",
      subject: "[Plaud-AutoFlow] 2026-05-06 09:48:05",
      bodyText: "body",
      attachments: [
        { filename: "summary.txt", textContent: "summary text" },
        { filename: "transcript.txt", textContent: "transcript text" }
      ]
    });

    expect(result.isPlaud).toBe(true);
    if (result.isPlaud) {
      expect(result.summaryText).toBe("summary text");
      expect(result.transcriptText).toBe("transcript text");
    }
  });

  it("rejects non-plaud emails", () => {
    const result = parsePlaudEmail({
      from: "alerts@example.com",
      subject: "status",
      attachments: []
    });

    expect(result.isPlaud).toBe(false);
  });

  it("builds deterministic fallback hash id", () => {
    const id1 = fallbackSourceMessageId({ from: "a", to: "b", subject: " S ", bodyText: "x" });
    const id2 = fallbackSourceMessageId({ from: "a", to: "b", subject: "s", bodyText: "x" });
    expect(id1).toBe(id2);
  });
});
