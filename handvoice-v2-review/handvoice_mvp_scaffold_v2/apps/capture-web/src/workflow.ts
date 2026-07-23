export type TaskCode = "T01" | "T02" | "T03";

export type QualityDecision = "accept" | "retry" | "review_needed";

export type QualityReasonCode =
  | "low_frame_rate"
  | "low_valid_frame_fraction"
  | "hand_out_of_guide"
  | "wrong_hand"
  | "low_audio_snr"
  | "audio_clipping"
  | "av_start_offset"
  | "audio_decode_failed"
  | "speech_not_detected"
  | "insufficient_motor_events"
  | "insufficient_ddk_events"
  | "capture_interrupted";

export type QualityResult = {
  quality_decision: QualityDecision;
  reason_codes: string[];
  quality_values?: Record<string, number | null>;
  guidance_key?: string;
};

export type ReadinessHandState = "missing_hand" | "wrong_hand" | "out_of_guide" | "valid" | "unavailable";

export type DisplayMetric = { label: string; value: string };
export type RetainedParticipant = { id: string; studyId: string; externalReference: string };

export function operatorPanelVisibility(hasKey: boolean): { operatorHidden: boolean; sessionHidden: boolean } {
  return { operatorHidden: hasKey, sessionHidden: !hasKey };
}

export function localDemoMode(search: string): boolean {
  return new URLSearchParams(search).get("demo") === "1";
}

export function operatorRequestHeaders(key: string, demoMode: boolean, json = false): Record<string, string> {
  if (!key && !demoMode) throw new Error("Unlock the operator device first.");
  const headers: Record<string, string> = key ? { Authorization: `Bearer ${key}` } : {};
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

export function retainedParticipantId(
  retained: RetainedParticipant | undefined,
  studyId: string,
  externalReference: string,
): string | undefined {
  return retained?.studyId === studyId && retained.externalReference === externalReference ? retained.id : undefined;
}

function isQualityValues(value: unknown): value is Record<string, number | null> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  return Object.values(value).every((metric) => metric === null || (typeof metric === "number" && Number.isFinite(metric)));
}

const GUIDANCE: Record<QualityReasonCode, string> = {
  low_frame_rate: "Close other apps, keep this screen open, and record again.",
  low_valid_frame_fraction: "Keep the right hand visible inside the guide for the whole task.",
  hand_out_of_guide: "Use only the right hand and keep it centred in the camera guide.",
  wrong_hand: "Pause and show only the participant's right hand. Do not force movement; end the session if they cannot continue comfortably.",
  low_audio_snr: "Move to a quieter space and hold the phone closer to the participant.",
  audio_clipping: "Move the phone slightly farther away and speak at a comfortable volume.",
  av_start_offset: "Keep this screen active and record the task again.",
  audio_decode_failed: "This recording format could not be read. Use a supported browser and retry.",
  speech_not_detected: "Ask the participant to repeat pa-ta-ka clearly throughout the Perform phase.",
  insufficient_motor_events: "Pause and review. Do not ask the participant to speed up; repeat only if they are comfortable, or end the session.",
  insufficient_ddk_events: "Pause and review. Do not ask the participant to speed up; repeat only if they are comfortable, or end the session.",
  capture_interrupted: "The screen was hidden or locked. Keep it visible for the full recording and retry.",
};

const REASON_LABELS: Record<QualityReasonCode, string> = {
  low_frame_rate: "Video frame rate was too low",
  low_valid_frame_fraction: "The right hand was not reliably visible",
  hand_out_of_guide: "The right hand moved outside the guide",
  wrong_hand: "The required right hand was not confirmed",
  low_audio_snr: "Speech was difficult to distinguish from background noise",
  audio_clipping: "The audio level was too loud and distorted",
  av_start_offset: "Audio and video did not start closely enough together",
  audio_decode_failed: "The recorded audio could not be read",
  speech_not_detected: "Speech was not detected",
  insufficient_motor_events: "The algorithm found fewer hand-tapping events than its analysis minimum",
  insufficient_ddk_events: "The algorithm found fewer candidate speech onsets than its analysis minimum",
  capture_interrupted: "The recording was interrupted",
};

const METRIC_LABELS: Record<string, string> = {
  median_fps: "Median video frame rate",
  valid_frame_fraction: "Valid right-hand frames",
  out_of_guide_frame_fraction: "Frames outside the hand guide",
  wrong_hand_frame_fraction: "High-confidence frames labelled as the wrong hand",
  audio_snr_db: "Audio signal-to-noise ratio",
  audio_clipping_fraction: "Clipped audio",
  av_start_offset_ms: "Audio-video start offset",
  motor_event_count: "Hand-tapping event count",
  ddk_event_count: "Candidate speech-onset count (exploratory)",
};

function plainLabel(name: string): string {
  const words = name.replaceAll("_", " ").replace("dtc percent", "dual-task cost");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function qualityReasonLabel(reason: string): string {
  return reason in REASON_LABELS ? REASON_LABELS[reason as QualityReasonCode] : plainLabel(reason);
}

export function displayQualityMetric(name: string, value: number | null): DisplayMetric {
  const label = METRIC_LABELS[name] ?? plainLabel(name);
  if (value === null) return { label, value: "Unavailable" };
  if (name.endsWith("_fraction")) return { label, value: `${(value * 100).toFixed(1)}%` };
  if (name === "median_fps") return { label, value: `${value.toFixed(1)} frames per second` };
  if (name === "audio_snr_db") return { label, value: `${value.toFixed(1)} decibels` };
  if (name === "av_start_offset_ms") return { label, value: `${value.toFixed(1)} milliseconds` };
  if (name.endsWith("_count")) return { label, value: `${Math.round(value)}` };
  return { label, value: value.toFixed(2) };
}

export function readinessHandMessage(state: ReadinessHandState): string {
  if (state === "valid") return "Right hand detected inside the guide.";
  if (state === "out_of_guide") return "Right hand detected outside the guide. Move it inside the outline.";
  if (state === "wrong_hand") return "Right hand not confirmed. Show only the participant's right hand.";
  if (state === "unavailable") return "Automatic hand-position guidance is unavailable. Use the visible guide and operator checks.";
  return "No hand detected. Place the participant's right hand inside the guide.";
}

export function taskInstruction(code: TaskCode): string {
  if (code === "T01") return "Tap the right index finger and thumb at a comfortable, steady pace.";
  if (code === "T02") return "Repeat pa-ta-ka clearly and steadily until the Perform phase ends.";
  return "Continue both tasks at the same comfortable, steady pace. Give equal attention to tapping and saying pa-ta-ka.";
}

export function taskPractice(code: TaskCode): string {
  if (code === "T01") return "Practise three comfortable right-hand taps.";
  if (code === "T02") return "Practise saying pa-ta-ka three times.";
  return "Practise three taps while saying pa-ta-ka three times.";
}

export function qualityHeading(decision: QualityDecision): string {
  if (decision === "accept") return "Accepted";
  if (decision === "review_needed") return "Review needed";
  return "Retry needed";
}

export function guidanceFor(result: QualityResult): string {
  if (result.quality_decision === "accept") return "Recording quality met every configured threshold.";
  const known = result.reason_codes.find((reason): reason is QualityReasonCode => reason in GUIDANCE);
  return known ? GUIDANCE[known] : "Review the setup, then record this task again.";
}

export function normalizedQuality(value: unknown): QualityResult {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid quality response.");
  const candidate = value as Partial<QualityResult> & { measured_quality?: Record<string, number | null> };
  const decision = candidate.quality_decision;
  if (decision !== "accept" && decision !== "retry" && decision !== "review_needed") {
    throw new Error("Quality response is missing a valid decision.");
  }
  if (!Array.isArray(candidate.reason_codes) || !candidate.reason_codes.every((reason) => typeof reason === "string")) {
    throw new Error("Quality response has invalid reason codes.");
  }
  const qualityValues = candidate.measured_quality ?? candidate.quality_values;
  if (qualityValues !== undefined && !isQualityValues(qualityValues)) {
    throw new Error("Quality response has invalid measured values.");
  }
  if (candidate.guidance_key !== undefined && typeof candidate.guidance_key !== "string") {
    throw new Error("Quality response has an invalid guidance key.");
  }
  return {
    quality_decision: decision,
    reason_codes: candidate.reason_codes,
    quality_values: qualityValues,
    guidance_key: candidate.guidance_key,
  };
}

export function nextTaskAfterDecision(currentIndex: number, taskCount: number, decision: QualityDecision): number {
  if (!Number.isInteger(currentIndex) || currentIndex < 0 || currentIndex >= taskCount) {
    throw new Error("Current task index is outside the workflow.");
  }
  return decision === "accept" ? currentIndex + 1 : currentIndex;
}

export function canRecapture(attemptCount: number): boolean {
  return Number.isInteger(attemptCount) && attemptCount >= 0 && attemptCount < 2;
}
