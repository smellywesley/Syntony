import { RESEARCH_WINDOW_MS } from "./research-extractor-core";

export function activeTimestampMs(
  videoTimeSeconds: number,
  activeStartMs: number,
): number | null {
  const timestamp = Math.round(videoTimeSeconds * 1000 - activeStartMs);
  return timestamp >= 0 && timestamp <= RESEARCH_WINDOW_MS ? timestamp : null;
}

export function addAnnotation(events: number[], timestampMs: number): number[] {
  if (!Number.isInteger(timestampMs) || timestampMs < 0 || timestampMs > RESEARCH_WINDOW_MS) {
    throw new Error("Annotation must fall inside the ten-second active window.");
  }
  return [...new Set([...events, timestampMs])].sort((first, second) => first - second);
}

export function removeAnnotation(events: number[], timestampMs: number): number[] {
  return events.filter((event) => event !== timestampMs);
}
