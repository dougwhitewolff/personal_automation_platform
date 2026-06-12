import { sanitizePostgresText } from "../common/sanitize-postgres-text";

export function isTextLikeContentType(contentType: string): boolean {
  const normalized = contentType.toLowerCase().split(";")[0]?.trim() ?? "";
  return (
    normalized.startsWith("text/") ||
    normalized === "application/json" ||
    normalized === "application/xml" ||
    normalized === "application/javascript" ||
    normalized === "message/rfc822"
  );
}

/** Decode attachment bytes as UTF-8 text only when the MIME type is text-like. */
export function decodeAttachmentTextContent(
  contentBytes: string,
  contentType: string
): string | undefined {
  if (!isTextLikeContentType(contentType)) {
    return undefined;
  }

  return sanitizePostgresText(Buffer.from(contentBytes, "base64").toString("utf8"));
}
