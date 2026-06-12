import { describe, expect, it } from "vitest";
import {
  sanitizeOptionalPostgresText,
  sanitizePostgresText
} from "../src/common/sanitize-postgres-text";
import { decodeAttachmentTextContent, isTextLikeContentType } from "../src/integrations/decode-attachment-text";
import { normalizedEmailToOutboxPayload } from "../src/outbox/to-outbox-payload";

describe("sanitizePostgresText", () => {
  it("removes NUL characters", () => {
    expect(sanitizePostgresText("hello\u0000world")).toBe("helloworld");
  });

  it("passes through clean strings", () => {
    expect(sanitizePostgresText("plain text")).toBe("plain text");
  });

  it("returns undefined for optional helper when input is undefined", () => {
    expect(sanitizeOptionalPostgresText(undefined)).toBeUndefined();
  });
});

describe("decodeAttachmentTextContent", () => {
  it("decodes text attachments and strips NUL bytes", () => {
    const bytes = Buffer.from("line\u0000one", "utf8").toString("base64");
    expect(decodeAttachmentTextContent(bytes, "text/plain")).toBe("lineone");
  });

  it("skips binary attachments", () => {
    const bytes = Buffer.from([0x25, 0x50, 0x44, 0x46]).toString("base64");
    expect(decodeAttachmentTextContent(bytes, "application/pdf")).toBeUndefined();
  });

  it("recognizes text-like MIME types", () => {
    expect(isTextLikeContentType("text/plain; charset=utf-8")).toBe(true);
    expect(isTextLikeContentType("application/json")).toBe(true);
    expect(isTextLikeContentType("application/octet-stream")).toBe(false);
  });
});

describe("normalizedEmailToOutboxPayload", () => {
  it("sanitizes nested email strings before persistence", () => {
    const payload = normalizedEmailToOutboxPayload({
      messageId: "<id@example.com>",
      from: "a\u0000@b.com",
      to: "c@d.com",
      subject: "sub\u0000ject",
      headers: { "X-Test": "val\u0000ue" },
      bodyText: "body\u0000",
      receivedAt: new Date("2026-01-01T00:00:00.000Z"),
      rawSourceRef: "graph:1",
      attachments: [
        {
          filename: "t\u0000.txt",
          contentType: "text/plain",
          textContent: "attach\u0000",
          size: 7
        }
      ]
    });

    expect(payload.from).toBe("a@b.com");
    expect(payload.subject).toBe("subject");
    expect(payload.headers).toEqual({ "X-Test": "value" });
    expect(payload.bodyText).toBe("body");
    expect(payload.attachments[0]?.textContent).toBe("attach");
  });
});
