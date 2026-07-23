import { describe, expect, it } from "vitest";

import {
  activeTimestampMs,
  addAnnotation,
  removeAnnotation,
} from "./motor-annotator-core";

describe("blinded motor annotation", () => {
  it("maps video time onto the fixed active-window clock", () => {
    expect(activeTimestampMs(2.5, 2_000)).toBe(500);
    expect(activeTimestampMs(1.9, 2_000)).toBeNull();
    expect(activeTimestampMs(12.1, 2_000)).toBeNull();
  });

  it("keeps event timestamps unique and ordered", () => {
    expect(addAnnotation([800, 400], 600)).toEqual([400, 600, 800]);
    expect(addAnnotation([400], 400)).toEqual([400]);
    expect(removeAnnotation([400, 600], 400)).toEqual([600]);
  });
});
