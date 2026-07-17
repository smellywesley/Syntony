export const PRE_ROLL_MS = 2_000;
export const ACTIVE_MS = 10_000;
export const POST_ROLL_MS = 3_000;
export const TOTAL_CAPTURE_MS = PRE_ROLL_MS + ACTIVE_MS + POST_ROLL_MS;

export function phaseAt(elapsedMs: number): string {
  if (elapsedMs < PRE_ROLL_MS) return "Prepare";
  if (elapsedMs < PRE_ROLL_MS + ACTIVE_MS) return "Perform task";
  if (elapsedMs < TOTAL_CAPTURE_MS) return "Hold";
  return "Complete";
}

export function activeTimestamp(elapsedMs: number): number | null {
  const timestamp = elapsedMs - PRE_ROLL_MS;
  return timestamp >= 0 && timestamp <= ACTIVE_MS ? Math.round(timestamp) : null;
}
