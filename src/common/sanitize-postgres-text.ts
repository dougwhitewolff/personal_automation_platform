/** PostgreSQL rejects U+0000 in text, varchar, and JSON string values. */
const NUL = /\u0000/g;

export function sanitizePostgresText(value: string): string {
  return value.replace(NUL, "");
}

export function sanitizeOptionalPostgresText(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  return sanitizePostgresText(value);
}
