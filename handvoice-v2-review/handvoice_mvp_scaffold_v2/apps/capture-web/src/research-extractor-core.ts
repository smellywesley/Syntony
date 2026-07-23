export const RESEARCH_WINDOW_MS = 10_000;
export const RESEARCH_SAMPLE_INTERVAL_MS = 40;

export function validCaseId(value: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(value);
}

export function sampleTimes(
  durationMs = RESEARCH_WINDOW_MS,
  intervalMs = RESEARCH_SAMPLE_INTERVAL_MS,
): number[] {
  if (!Number.isInteger(durationMs) || durationMs <= 0) {
    throw new Error("Duration must be a positive integer.");
  }
  if (!Number.isInteger(intervalMs) || intervalMs <= 0 || intervalMs > durationMs) {
    throw new Error("Sample interval must be a positive integer within the duration.");
  }
  const times: number[] = [];
  for (let timestamp = 0; timestamp <= durationMs; timestamp += intervalMs) {
    times.push(timestamp);
  }
  return times;
}

export function containedWindow(
  videoDurationSeconds: number,
  activeStartMs: number,
  activeDurationMs = RESEARCH_WINDOW_MS,
): boolean {
  return (
    Number.isFinite(videoDurationSeconds)
    && Number.isInteger(activeStartMs)
    && activeStartMs >= 0
    && activeStartMs + activeDurationMs <= videoDurationSeconds * 1000
  );
}
