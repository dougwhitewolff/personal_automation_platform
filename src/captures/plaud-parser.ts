import { createHash } from "crypto";

export type PlaudParseResult =
  | {
      isPlaud: true;
      summaryText: string | null;
      transcriptText: string | null;
    }
  | {
      isPlaud: false;
      reason: string;
    };

export function parsePlaudEmail(input: {
  from: string;
  subject: string;
  bodyText?: string;
  attachments: Array<{ filename: string; textContent?: string }>;
}): PlaudParseResult {
  const fromLower = input.from.toLowerCase();
  const subjectLower = input.subject.toLowerCase();
  const looksPlaud = fromLower.includes("plaud") || subjectLower.includes("plaud-autoflow");

  if (!looksPlaud) {
    return { isPlaud: false, reason: "Sender/subject did not match Plaud pattern" };
  }

  const transcriptAttachment = input.attachments.find((x) => x.filename.toLowerCase() === "transcript.txt");
  const summaryAttachment = input.attachments.find((x) => x.filename.toLowerCase() === "summary.txt");

  return {
    isPlaud: true,
    summaryText: summaryAttachment?.textContent?.trim() || null,
    transcriptText: transcriptAttachment?.textContent?.trim() || extractTranscriptFromBody(input.bodyText)
  };
}

export function fallbackSourceMessageId(input: {
  from: string;
  to: string;
  subject: string;
  bodyText?: string;
}): string {
  return createHash("sha256")
    .update(`${input.from}|${input.to}|${input.subject.trim().toLowerCase()}|${(input.bodyText ?? "").trim()}`)
    .digest("hex");
}

function extractTranscriptFromBody(bodyText?: string): string | null {
  if (!bodyText) return null;
  const marker = "The original audio transcription is as follows:";
  const idx = bodyText.indexOf(marker);
  if (idx === -1) return null;
  return bodyText.slice(idx + marker.length).trim() || null;
}
