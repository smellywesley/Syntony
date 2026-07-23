import { describe, expect, it } from "vitest";

import {
  containedWindow,
  RESEARCH_SAMPLE_INTERVAL_MS,
  RESEARCH_WINDOW_MS,
  sampleTimes,
  validCaseId,
} from "./research-extractor-core";

describe("research landmark extraction contract", () => {
  it("creates a fixed monotonic ten-second timebase", () => {
    const times = sampleTimes();
    expect(times[0]).toBe(0);
    expect(times.at(-1)).toBe(RESEARCH_WINDOW_MS);
    expect(times).toHaveLength(RESEARCH_WINDOW_MS / RESEARCH_SAMPLE_INTERVAL_MS + 1);
    expect(times[1]).toBe(RESEARCH_SAMPLE_INTERVAL_MS);
  });

  it("rejects identifying or path-like case labels", () => {
    expect(validCaseId("motor-001")).toBe(true);
    expect(validCaseId("../patient-name")).toBe(false);
    expect(validCaseId("name with spaces")).toBe(false);
  });

  it("requires the selected active window to fit inside the video", () => {
    expect(containedWindow(20.2, 2_000)).toBe(true);
    expect(containedWindow(11, 2_000)).toBe(false);
    expect(containedWindow(20, -1)).toBe(false);
  });
});
