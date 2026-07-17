import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";

import { ACTIVE_MS, activeTimestamp, phaseAt, TOTAL_CAPTURE_MS } from "./protocol";
import "./styles.css";

type Task = {
  id: string;
  task_code: "T01" | "T02" | "T03";
  task_name: string;
  order_index: number;
};

type Session = { id: string; tasks: Task[] };
type LandmarkFrame = {
  timestamp_ms: number;
  handedness: "right";
  landmarks_xyz: [number, number, number][];
  median_confidence: number;
  validity: "valid" | "missing_hand" | "out_of_guide";
};

const element = <T extends HTMLElement>(id: string): T => {
  const found = document.getElementById(id);
  if (!found) throw new Error(`Missing element #${id}`);
  return found as T;
};

const apiKeyInput = element<HTMLInputElement>("api-key");
const studyIdInput = element<HTMLInputElement>("study-id");
const participantRefInput = element<HTMLInputElement>("participant-ref");
const startButton = element<HTMLButtonElement>("start-session");
const recordButton = element<HTMLButtonElement>("record-task");
const captureArea = element<HTMLElement>("capture-area");
const video = element<HTMLVideoElement>("preview");
const canvas = element<HTMLCanvasElement>("overlay");
const timer = element<HTMLElement>("timer");
const statusText = element<HTMLElement>("status");
const taskCode = element<HTMLElement>("task-code");
const taskName = element<HTMLElement>("task-name");
const taskInstruction = element<HTMLElement>("task-instruction");
const taskList = element<HTMLOListElement>("task-list");
const results = element<HTMLElement>("results");

let stream: MediaStream;
let handLandmarker: HandLandmarker;
let session: Session;
let taskIndex = 0;

function apiHeaders(json = false): HeadersInit {
  const headers: Record<string, string> = { "X-HandVoice-API-Key": apiKeyInput.value };
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Preserve the HTTP status when the server does not return JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function instructionFor(code: Task["task_code"]): string {
  if (code === "T01") return "Tap your right index finger and thumb at a comfortable steady pace.";
  if (code === "T02") return "Repeat pa-ta-ka clearly and steadily until the active period ends.";
  return "Tap your right index finger and thumb while repeating pa-ta-ka at the same time.";
}

function renderTasks(): void {
  const current = session.tasks[taskIndex];
  if (!current) return;
  taskCode.textContent = current.task_code;
  taskName.textContent = current.task_name;
  taskInstruction.textContent = instructionFor(current.task_code);
  taskList.replaceChildren(
    ...session.tasks.map((task, index) => {
      const item = document.createElement("li");
      item.textContent = `${task.task_code} · ${task.task_name}`;
      item.className = index < taskIndex ? "done" : index === taskIndex ? "current" : "";
      return item;
    }),
  );
}

async function initializeVision(): Promise<void> {
  statusText.textContent = "Loading the on-device hand model…";
  const fileset = await FilesetResolver.forVisionTasks("/capture/wasm");
  handLandmarker = await HandLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: "/capture/models/hand_landmarker.task" },
    runningMode: "VIDEO",
    numHands: 1,
    minHandDetectionConfidence: 0.6,
    minHandPresenceConfidence: 0.6,
    minTrackingConfidence: 0.6,
  });
}

async function initializeCamera(): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser cannot access a camera.");
  stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
  });
  video.srcObject = stream;
  await video.play();
}

async function startSession(): Promise<void> {
  if (!apiKeyInput.value.trim()) throw new Error("Enter the local API key.");
  if (!studyIdInput.value.trim()) throw new Error("Enter a study ID.");
  startButton.disabled = true;
  try {
    await Promise.all([initializeCamera(), initializeVision()]);
    const participant = await api<{ id: string }>("/v1/participants", {
      method: "POST",
      headers: apiHeaders(true),
      body: JSON.stringify({
        study_id: studyIdInput.value.trim(),
        external_reference: participantRefInput.value.trim() || null,
      }),
    });
    session = await api<Session>("/v1/sessions", {
      method: "POST",
      headers: apiHeaders(true),
      body: JSON.stringify({ participant_id: participant.id, protocol_version: "1.1.0" }),
    });
    session.tasks.sort((a, b) => a.order_index - b.order_index);
    taskIndex = 0;
    renderTasks();
    captureArea.hidden = false;
    statusText.textContent = "Camera and model ready. Keep the phone still and your hand inside the frame.";
  } finally {
    startButton.disabled = false;
  }
}

function recordingType(): { mimeType?: string; suffix: string } {
  const candidates = [
    ["video/mp4;codecs=avc1.42E01E,mp4a.40.2", ".mp4"],
    ["video/webm;codecs=vp8,opus", ".webm"],
    ["video/webm", ".webm"],
  ] as const;
  const selected = candidates.find(([mime]) => MediaRecorder.isTypeSupported(mime));
  return selected ? { mimeType: selected[0], suffix: selected[1] } : { suffix: ".webm" };
}

function drawLandmarks(points: { x: number; y: number }[] | undefined): void {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!points) return;
  context.fillStyle = "#5eead4";
  for (const point of points) {
    context.beginPath();
    context.arc(point.x * canvas.width, point.y * canvas.height, 4, 0, Math.PI * 2);
    context.fill();
  }
}

function missingFrame(timestamp: number): LandmarkFrame {
  return {
    timestamp_ms: timestamp,
    handedness: "right",
    landmarks_xyz: Array.from({ length: 21 }, () => [0, 0, 0] as [number, number, number]),
    median_confidence: 0,
    validity: "missing_hand",
  };
}

async function capture(task: Task): Promise<{ blob: Blob; suffix: string; frames: LandmarkFrame[] }> {
  const format = recordingType();
  const recorder = new MediaRecorder(stream, format.mimeType ? { mimeType: format.mimeType } : undefined);
  const chunks: BlobPart[] = [];
  const frames: LandmarkFrame[] = [];
  const startedAt = performance.now();
  let active = true;
  let lastSampleAt = 0;
  recorder.addEventListener("dataavailable", (event) => {
    if (event.data.size) chunks.push(event.data);
  });
  const stopped = new Promise<void>((resolve, reject) => {
    recorder.addEventListener("stop", () => resolve(), { once: true });
    recorder.addEventListener("error", () => reject(new Error("Browser media recording failed.")), { once: true });
  });
  recorder.start(250);

  const sample = (now: number): void => {
    if (!active) return;
    const elapsed = now - startedAt;
    const remaining = Math.max(0, TOTAL_CAPTURE_MS - elapsed);
    timer.textContent = `${phaseAt(elapsed)} · ${(remaining / 1000).toFixed(1)} s`;
    const timestamp = activeTimestamp(elapsed);
    if (timestamp !== null && task.task_code !== "T02" && now - lastSampleAt >= 66) {
      lastSampleAt = now;
      const detected = handLandmarker.detectForVideo(video, now);
      const landmarks = detected.landmarks[0];
      const category = detected.handedness[0]?.[0];
      drawLandmarks(landmarks);
      if (!landmarks) {
        frames.push(missingFrame(timestamp));
      } else {
        frames.push({
          timestamp_ms: timestamp,
          handedness: "right",
          landmarks_xyz: landmarks.map((point) => [point.x, point.y, point.z]),
          median_confidence: category?.score ?? 0,
          validity: category?.categoryName.toLowerCase() === "right" ? "valid" : "out_of_guide",
        });
      }
    }
    requestAnimationFrame(sample);
  };
  requestAnimationFrame(sample);
  await new Promise((resolve) => setTimeout(resolve, TOTAL_CAPTURE_MS));
  active = false;
  recorder.stop();
  await stopped;
  drawLandmarks(undefined);
  timer.textContent = "Processing";
  return { blob: new Blob(chunks, { type: recorder.mimeType }), suffix: format.suffix, frames };
}

async function submitCapture(task: Task, recording: Awaited<ReturnType<typeof capture>>): Promise<void> {
  const form = new FormData();
  form.append("file", recording.blob, `${task.task_code.toLowerCase()}${recording.suffix}`);
  const uploaded = await api<{ storage_key: string; sha256: string }>("/v1/media", {
    method: "POST",
    headers: apiHeaders(),
    body: form,
  });
  const facingMode = stream.getVideoTracks()[0]?.getSettings().facingMode;
  await api(`/v1/task-instances/${task.id}/measure`, {
    method: "POST",
    headers: apiHeaders(true),
    body: JSON.stringify({
      storage_key: uploaded.storage_key,
      sha256: uploaded.sha256,
      manifest: {
        protocol_version: "1.1.0",
        active_start_ms: 2000,
        active_end_ms: 12000,
        camera_facing: facingMode === "environment" ? "rear" : "front",
        capture_app_version: "capture-web-0.1.0",
      },
      landmark_frames: recording.frames,
      voiced_intervals: [],
      ddk_event_ms: [],
    }),
  });
}

function metricLabel(name: string): string {
  return name.replaceAll("_", " ").replace("dtc percent", "dual-task cost");
}

async function renderReport(): Promise<void> {
  const report = await api<{ metrics: Record<string, number | null>; exploratory_coupling: Record<string, number | null> }>(
    `/v1/sessions/${session.id}/report`,
    { headers: apiHeaders() },
  );
  const entries = Object.entries(report.metrics);
  results.hidden = false;
  results.innerHTML = `<div class="metric-grid">${entries
    .map(([name, value]) => `<div class="metric">${metricLabel(name)}<strong>${value === null ? "Unavailable" : `${value.toFixed(1)}%`}</strong></div>`)
    .join("")}</div><p><a href="/v1/sessions/${session.id}/visualization" target="_blank" rel="noreferrer">Open synchronized event timeline</a></p>`;
  statusText.textContent = "Three-task session complete. Results describe task performance, not disease.";
}

async function recordCurrentTask(): Promise<void> {
  const task = session.tasks[taskIndex];
  if (!task) return;
  recordButton.disabled = true;
  try {
    statusText.textContent = `Recording ${task.task_code}. Do not switch apps or lock the screen.`;
    const recording = await capture(task);
    statusText.textContent = `Uploading and measuring ${task.task_code}…`;
    await submitCapture(task, recording);
    taskIndex += 1;
    if (taskIndex < session.tasks.length) {
      renderTasks();
      timer.textContent = "Ready";
      statusText.textContent = "Task accepted. Review the next instruction before recording.";
    } else {
      renderTasks();
      timer.textContent = "Complete";
      await renderReport();
    }
  } finally {
    recordButton.disabled = taskIndex >= session.tasks.length;
  }
}

startButton.addEventListener("click", () => {
  startSession().catch((error: unknown) => {
    statusText.textContent = `Setup failed: ${error instanceof Error ? error.message : String(error)}`;
  });
});

recordButton.addEventListener("click", () => {
  recordCurrentTask().catch((error: unknown) => {
    timer.textContent = "Retry needed";
    statusText.textContent = `Capture rejected: ${error instanceof Error ? error.message : String(error)}`;
    recordButton.disabled = false;
  });
});
