import { describe, expect, it } from "vitest";

import { activeTimestamp, LANDMARK_SAMPLE_INTERVAL_MS, phaseAt } from "./protocol";

describe("frozen capture timing", () => {
  it("maps only 2000-12000 ms into the active window", () => {
    expect(activeTimestamp(1999)).toBeNull();
    expect(activeTimestamp(2000)).toBe(0);
    expect(activeTimestamp(12000)).toBe(10000);
    expect(activeTimestamp(12001)).toBeNull();
  });

  it("labels each capture phase", () => {
    expect(phaseAt(0)).toBe("Prepare");
    expect(phaseAt(2000)).toBe("Perform task");
    expect(phaseAt(12000)).toBe("Relax");
    expect(phaseAt(15000)).toBe("Complete");
  });

  it("samples landmarks above the frozen 24 fps acceptance threshold", () => {
    expect(1000 / LANDMARK_SAMPLE_INTERVAL_MS).toBeGreaterThan(24);
  });
});
