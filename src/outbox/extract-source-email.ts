/**
 * Extracts a single RFC-like email address from a From header
 * (e.g. "Plaud <noreply@plaud.ai>" or "noreply@plaud.ai").
 */
export function extractAddressFromFromHeader(from: string | undefined | null): string | null {
  if (!from || typeof from !== "string") {
    return null;
  }
  const trimmed = from.trim();
  const angle = /<([^>]+)>/.exec(trimmed);
  const candidate = (angle?.[1] ?? trimmed).trim();
  const emailMatch = /[^\s<>]+@[^\s<>]+/i.exec(candidate);
  return emailMatch ? emailMatch[0].toLowerCase() : null;
}
