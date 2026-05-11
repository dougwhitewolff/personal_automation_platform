import { createHash, randomBytes } from "crypto";

export function hashApiKey(value: string, salt: string): string {
  return createHash("sha256").update(`${salt}:${value}`).digest("hex");
}

export function generateApiKey(): { plaintext: string; prefix: string } {
  const plaintext = `pap_${randomBytes(24).toString("hex")}`;
  return { plaintext, prefix: plaintext.slice(0, 12) };
}
