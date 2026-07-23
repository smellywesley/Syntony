import { describe, expect, it } from "vitest";

import {
  canRecapture,
  displayQualityMetric,
  guidanceFor,
  nextTaskAfterDecision,
  normalizedQuality,
  localDemoMode,
  operatorPanelVisibility,
  operatorRequestHeaders,
  qualityHeading,
  qualityReasonLabel,
  readinessHandMessage,
  retainedParticipantId,
  taskInstruction,
  taskPractice,
} from "./workflow";

describe("guided capture copy", () => {
  it("makes the right-hand restriction explicit for motor tasks", () => {
    expect(taskInstruction("T01")).toContain("right index finger");
    expect(taskInstruction("T03")).toContain("equal attention");
    expect(taskInstruction("T03")).toContain("comfortable");
    expect(taskPractice("T03")).toContain("three taps");
  });

  it("uses non-diagnostic quality labels", () => {
    expect(qualityHeading("accept")).toBe("Accepted");
    expect(qualityHeading("retry")).toBe("Retry needed");
    expect(qualityHeading("review_needed")).toBe("Review needed");
  });

  it("provides plain-language quality labels, values, and hand-position guidance", () => {
    expect(qualityReasonLabel("low_audio_snr")).toBe("Speech was difficult to distinguish from background noise");
    expect(displayQualityMetric("valid_frame_fraction", 0.856)).toEqual({
      label: "Valid right-hand frames",
      value: "85.6%",
    });
    expect(displayQualityMetric("av_start_offset_ms", 42)).toEqual({
      label: "Audio-video start offset",
      value: "42.0 milliseconds",
    });
    expect(readinessHandMessage("valid")).toContain("inside the guide");
    expect(readinessHandMessage("out_of_guide")).toContain("Move it inside");
  });

  it("shows participant setup only after the operator device is unlocked", () => {
    expect(operatorPanelVisibility(false)).toEqual({ operatorHidden: false, sessionHidden: true });
    expect(operatorPanelVisibility(true)).toEqual({ operatorHidden: true, sessionHidden: false });
  });

  it("bypasses the key only for an explicit local-demo URL", () => {
    expect(localDemoMode("?demo=1")).toBe(true);
    expect(localDemoMode("?demo=0")).toBe(false);
    expect(operatorRequestHeaders("", true, true)).toEqual({ "Content-Type": "application/json" });
    expect(() => operatorRequestHeaders("", false)).toThrow("Unlock");
    expect(operatorRequestHeaders("study-key", false)).toEqual({ Authorization: "Bearer study-key" });
  });

  it("reuses a retained participant only for the same study and external reference", () => {
    const retained = { id: "participant-1", studyId: "study-a", externalReference: "demo-001" };
    expect(retainedParticipantId(retained, "study-a", "demo-001")).toBe("participant-1");
    expect(retainedParticipantId(retained, "study-a", "demo-002")).toBeUndefined();
    expect(retainedParticipantId(retained, "study-b", "demo-001")).toBeUndefined();
  });
});

describe("quality response normalization", () => {
  it("keeps structured review results and selects one recovery action", () => {
    const result = normalizedQuality({
      quality_decision: "review_needed",
      reason_codes: ["low_audio_snr", "speech_not_detected"],
      measured_quality: { audio_snr_db: 8.5 },
    });
    expect(result.quality_decision).toBe("review_needed");
    expect(result.reason_codes).toEqual(["low_audio_snr", "speech_not_detected"]);
    expect(result.quality_values).toEqual({ audio_snr_db: 8.5 });
    expect(guidanceFor(result)).toContain("quieter space");
  });

  it("fails closed when a response omits or invents a decision", () => {
    expect(() => normalizedQuality({ status: "analyzed_synchronously" })).toThrow("valid decision");
    expect(() => normalizedQuality({ quality_decision: "maybe", reason_codes: [] })).toThrow("valid decision");
    expect(() => normalizedQuality(null)).toThrow("Invalid quality response");
  });

  it("falls back safely for unknown reason codes", () => {
    const result = normalizedQuality({ quality_decision: "retry", reason_codes: ["future_reason"] });
    expect(guidanceFor(result)).toContain("Review the setup");
  });
});

describe("three-task workflow", () => {
  it("limits each task to two recording attempts", () => {
    expect(canRecapture(0)).toBe(true);
    expect(canRecapture(1)).toBe(true);
    expect(canRecapture(2)).toBe(false);
    expect(canRecapture(3)).toBe(false);
  });

  it("advances T01 to T02 to T03 only after accepted quality", () => {
    let index = 0;
    index = nextTaskAfterDecision(index, 3, "review_needed");
    expect(index).toBe(0);
    index = nextTaskAfterDecision(index, 3, "accept");
    expect(index).toBe(1);
    index = nextTaskAfterDecision(index, 3, "retry");
    expect(index).toBe(1);
    index = nextTaskAfterDecision(index, 3, "accept");
    expect(index).toBe(2);
    index = nextTaskAfterDecision(index, 3, "accept");
    expect(index).toBe(3);
  });
});
