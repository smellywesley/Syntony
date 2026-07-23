import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";

import { physicalHandedness } from "./capture-lifecycle";
import {
  containedWindow,
  sampleTimes,
  validCaseId,
} from "./research-extractor-core";

type LandmarkFrame = {
  timestamp_ms: number;
  handedness: "left" | "right";
  landmarks_xyz: [number, number, number][];
  median_confidence: number;
  validity: "valid" | "missing_hand" | "out_of_guide";
};

const element = <T extends HTMLElement>(id: string): T => {
  const found = document.getElementById(id);
  if (!found) throw new Error(`Missing element #${id}`);
  return found as T;
};

const caseIdInput = element<HTMLInputElement>("case-id");
const videoInput = element<HTMLInputElement>("video-file");
const activeStartInput = element<HTMLInputElement>("active-start-ms");
const inputMirrored = element<HTMLInputElement>("input-mirrored");
const extractButton = element<HTMLButtonElement>("extract");
const status = element<HTMLElement>("status");
const progress = element<HTMLProgressElement>("progress");
const preview = element<HTMLVideoElement>("preview");
const download = element<HTMLAnchorElement>("download");
const sourceHash = element<HTMLElement>("source-hash");
const trackingSummary = element<HTMLElement>("tracking-summary");
let videoUrl: string | undefined;
let handLandmarker: HandLandmarker | undefined;

function waitForVideoEvent(name: "loadedmetadata" | "seeked"): Promise<void> {
  return new Promise((resolve, reject) => {
    const failed = (): void => reject(new Error("The selected video could not be decoded."));
    preview.addEventListener(name, () => resolve(), { once: true });
    preview.addEventListener("error", failed, { once: true });
  });
}

async function loadVideo(file: File): Promise<void> {
  if (videoUrl) URL.revokeObjectURL(videoUrl);
  videoUrl = URL.createObjectURL(file);
  const loaded = waitForVideoEvent("loadedmetadata");
  preview.src = videoUrl;
  preview.load();
  await loaded;
}

async function seek(seconds: number): Promise<void> {
  if (Math.abs(preview.currentTime - seconds) < 0.0005) return;
  const completed = waitForVideoEvent("seeked");
  preview.currentTime = seconds;
  await completed;
}

async function acquireVision(): Promise<HandLandmarker> {
  if (handLandmarker) return handLandmarker;
  const fileset = await FilesetResolver.forVisionTasks("wasm");
  const options = {
    baseOptions: {
      modelAssetPath: "models/hand_landmarker.task",
    },
    runningMode: "VIDEO",
    numHands: 1,
    minHandDetectionConfidence: 0.5,
    minHandPresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
  } as const;
  try {
    handLandmarker = await HandLandmarker.createFromOptions(fileset, {
      ...options,
      baseOptions: { ...options.baseOptions, delegate: "GPU" },
    });
  } catch {
    status.textContent = "GPU tracking unavailable; continuing with the CPU tracker.";
    handLandmarker = await HandLandmarker.createFromOptions(fileset, options);
  }
  return handLandmarker;
}

function missingFrame(timestampMs: number): LandmarkFrame {
  return {
    timestamp_ms: timestampMs,
    handedness: "right",
    landmarks_xyz: Array.from(
      { length: 21 },
      () => [0, 0, 0] as [number, number, number],
    ),
    median_confidence: 0,
    validity: "missing_hand",
  };
}

async function sha256Hex(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function saveJson(caseId: string, frames: LandmarkFrame[]): void {
  const payload = {
    schema_version: "1.0",
    case_id: caseId,
    frames,
  };
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], {
    type: "application/json",
  });
  download.href = URL.createObjectURL(blob);
  download.download = `${caseId}.json`;
  download.hidden = false;
}

async function extract(): Promise<void> {
  const caseId = caseIdInput.value.trim();
  const file = videoInput.files?.[0];
  const activeStartMs = Number(activeStartInput.value);
  if (!validCaseId(caseId)) {
    throw new Error("Use a pseudonymous case ID containing letters, numbers, dot, dash or underscore.");
  }
  if (!file) throw new Error("Choose an approved local video.");
  await loadVideo(file);
  if (!containedWindow(preview.duration, activeStartMs)) {
    throw new Error("The fixed ten-second active window must fit inside the selected video.");
  }

  const vision = await acquireVision();
  const timestamps = sampleTimes();
  const frames: LandmarkFrame[] = [];
  progress.max = timestamps.length;
  progress.value = 0;
  for (const timestampMs of timestamps) {
    await seek((activeStartMs + timestampMs) / 1000);
    const detected = vision.detectForVideo(preview, timestampMs);
    const landmarks = detected.landmarks[0];
    const category = detected.handedness[0]?.[0];
    if (!landmarks) {
      frames.push(missingFrame(timestampMs));
    } else {
      const handedness = physicalHandedness(
        category?.categoryName,
        inputMirrored.checked,
      );
      frames.push({
        timestamp_ms: timestampMs,
        handedness: handedness === "right" ? "right" : "left",
        landmarks_xyz: landmarks.map((point) => [point.x, point.y, point.z]),
        median_confidence: category?.score ?? 0,
        validity: handedness === "right" ? "valid" : "out_of_guide",
      });
    }
    progress.value += 1;
    status.textContent = `Processed ${progress.value} of ${progress.max} frames locally.`;
  }
  saveJson(caseId, frames);
  sourceHash.textContent = await sha256Hex(file);
  const validCount = frames.filter((frame) => frame.validity === "valid").length;
  const missingCount = frames.filter(
    (frame) => frame.validity === "missing_hand",
  ).length;
  trackingSummary.textContent = (
    `${validCount} of ${frames.length} frames tracked as the expected right hand; `
    + `${missingCount} frames had no hand.`
  );
  status.textContent = "Landmark extraction complete. Review tracking quality before annotation.";
}

extractButton.addEventListener("click", () => {
  extractButton.disabled = true;
  download.hidden = true;
  sourceHash.textContent = "";
  trackingSummary.textContent = "";
  status.textContent = "Preparing local extraction…";
  extract()
    .catch((error: unknown) => {
      status.textContent = error instanceof Error ? error.message : String(error);
    })
    .finally(() => {
      extractButton.disabled = false;
    });
});
