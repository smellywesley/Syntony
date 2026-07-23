import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";

import { activeTimestamp, LANDMARK_SAMPLE_INTERVAL_MS, phaseAt, TOTAL_CAPTURE_MS } from "./protocol";
import {
  acquireResourcePair,
  fetchAuthenticatedHtml,
  guideBoundsForCover,
  landmarksInsideGuide,
  mediaAccessMessage,
  physicalHandedness,
  reacquireMediaResources,
  releaseMediaResources,
  selectRecordingFormat,
  shouldAbortCapture,
  shouldReleaseDevicesAfterCaptureError,
  startRecorderSafely,
  submitRetained,
} from "./capture-lifecycle";
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
  type QualityResult,
  type RetainedParticipant,
  type TaskCode,
} from "./workflow";
import "./styles.css";

type Task = { id: string; task_code: TaskCode; task_name: string; order_index: number };
type Session = { id: string; tasks: Task[] };
type LandmarkFrame = {
  timestamp_ms: number;
  handedness: "left" | "right";
  landmarks_xyz: [number, number, number][];
  median_confidence: number;
  validity: "valid" | "missing_hand" | "out_of_guide";
};
type Recording = { blob: Blob; suffix: string; frames: LandmarkFrame[] };
type Upload = { storage_key: string; sha256: string };
type PendingCapture = { task: Task; recording: Recording; upload?: Upload };
type CheckpointMode = "continue" | "recapture" | "resubmit";

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload: unknown,
  ) {
    super(message);
  }
}

class CaptureInterruptedError extends Error {}

const element = <T extends HTMLElement>(id: string): T => {
  const found = document.getElementById(id);
  if (!found) throw new Error(`Missing element #${id}`);
  return found as T;
};

const operatorSetup = element<HTMLElement>("operator-setup");
const operatorKeyInput = element<HTMLInputElement>("operator-key");
const saveOperatorButton = element<HTMLButtonElement>("save-operator");
const changeOperatorButton = element<HTMLButtonElement>("change-operator");
const operatorStatus = element<HTMLElement>("operator-status");
const operatorKeyError = element<HTMLElement>("operator-key-error");
const sessionSetup = element<HTMLElement>("session-setup");
const studyIdInput = element<HTMLInputElement>("study-id");
const studyIdError = element<HTMLElement>("study-id-error");
const participantRefInput = element<HTMLInputElement>("participant-ref");
const participantRefError = element<HTMLElement>("participant-ref-error");
const privacyConfirmed = element<HTMLInputElement>("privacy-confirmed");
const privacyConfirmedError = element<HTMLElement>("privacy-confirmed-error");
const setupError = element<HTMLElement>("setup-error");
const startReadinessButton = element<HTMLButtonElement>("start-readiness");
const readiness = element<HTMLElement>("readiness");
const readinessChecks = [...document.querySelectorAll<HTMLInputElement>(".readiness-check")];
const readinessHandStatus = element<HTMLElement>("readiness-hand-status");
const deviceStatus = element<HTMLElement>("device-status");
const readinessError = element<HTMLElement>("readiness-error");
const createSessionButton = element<HTMLButtonElement>("create-session");
const captureArea = element<HTMLElement>("capture-area");
const videos = [...document.querySelectorAll<HTMLVideoElement>(".preview")];
const canvases = [...document.querySelectorAll<HTMLCanvasElement>(".overlay")];
const phaseLabel = element<HTMLElement>("phase-label");
const phaseAnnouncement = element<HTMLElement>("phase-announcement");
const timer = element<HTMLElement>("timer");
const statusText = element<HTMLElement>("status");
const taskCode = element<HTMLElement>("task-code");
const taskName = element<HTMLElement>("task-name");
const taskInstructionText = element<HTMLElement>("task-instruction");
const taskPracticeText = element<HTMLElement>("task-practice");
const taskList = element<HTMLOListElement>("task-list");
const practiceComplete = element<HTMLInputElement>("practice-complete");
const operatorReady = element<HTMLInputElement>("operator-ready");
const recordButton = element<HTMLButtonElement>("record-task");
const stopCaptureButton = element<HTMLButtonElement>("stop-capture");
const checkpoint = element<HTMLElement>("checkpoint");
const checkpointTitle = element<HTMLElement>("checkpoint-title");
const checkpointStatus = element<HTMLElement>("checkpoint-status");
const checkpointGuidance = element<HTMLElement>("checkpoint-guidance");
const qualityReasons = element<HTMLUListElement>("quality-reasons");
const qualityValues = element<HTMLDListElement>("quality-values");
const checkpointPrimary = element<HTMLButtonElement>("checkpoint-primary");
const checkpointSecondary = element<HTMLButtonElement>("checkpoint-secondary");
const reportSection = element<HTMLElement>("report");
const results = element<HTMLElement>("results");
const timeline = element<HTMLIFrameElement>("timeline");
const newSessionButton = element<HTMLButtonElement>("new-session");
const endSessionButton = element<HTMLButtonElement>("end-session");

let stream: MediaStream | undefined;
let handLandmarker: HandLandmarker | undefined;
let session: Session | undefined;
let taskIndex = 0;
let pendingCapture: PendingCapture | undefined;
let checkpointMode: CheckpointMode = "continue";
let checkpointActionInFlight = false;
let captureAbort: (() => void) | undefined;
let operatorCredential = "";
let timelineObjectUrl: string | undefined;
let retainedParticipant: RetainedParticipant | undefined;
const taskAttempts = new Map<string, number>();
let readinessAnimationFrame = 0;
let readinessSampleAt = 0;
const isLocalDemo = localDemoMode(window.location.search);

function operatorKey(): string {
  return operatorCredential;
}

function apiHeaders(json = false): HeadersInit {
  return operatorRequestHeaders(operatorKey(), isLocalDemo, json);
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let payload: unknown;
    let detail = `${response.status} ${response.statusText}`;
    try {
      payload = await response.json();
      const body = payload as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // The HTTP status remains useful when a proxy returns a non-JSON response.
    }
    throw new ApiError(detail, response.status, payload);
  }
  return (await response.json()) as T;
}

function setProgress(step: "setup" | "ready" | "capture" | "report"): void {
  const order = ["setup", "ready", "capture", "report"];
  const selected = order.indexOf(step);
  for (const item of document.querySelectorAll<HTMLElement>("[data-progress]")) {
    const index = order.indexOf(item.dataset.progress ?? "");
    const label = item.dataset.label ?? item.textContent ?? "";
    item.className = index < selected ? "done" : index === selected ? "current" : "";
    item.textContent = index < selected ? `${label} — completed` : label;
    if (index === selected) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  }
}

function clearControlError(control: HTMLInputElement, errorElement: HTMLElement): void {
  control.removeAttribute("aria-invalid");
  errorElement.textContent = "";
  errorElement.hidden = true;
}

function showControlError(control: HTMLInputElement, errorElement: HTMLElement, message: string): void {
  control.setAttribute("aria-invalid", "true");
  errorElement.textContent = message;
  errorElement.hidden = false;
}

function showPanelError(errorElement: HTMLElement, message: string): void {
  errorElement.textContent = message;
  errorElement.hidden = false;
}

function clearPanelError(errorElement: HTMLElement): void {
  errorElement.textContent = "";
  errorElement.hidden = true;
}

function reflectOperatorState(): void {
  const hasAccess = isLocalDemo || operatorKey().length > 0;
  const visibility = operatorPanelVisibility(hasAccess);
  operatorSetup.hidden = visibility.operatorHidden;
  sessionSetup.hidden = visibility.sessionHidden;
  changeOperatorButton.hidden = isLocalDemo || !hasAccess;
  startReadinessButton.disabled = !hasAccess;
  operatorStatus.textContent = isLocalDemo
    ? "Local demo mode. Enter a coded participant ID to create a session."
    : hasAccess
    ? "Operator device unlocked. The participant does not handle credentials."
    : "Unlock this device before preparing a participant.";
}

function saveOperator(): void {
  const value = operatorKeyInput.value.trim();
  if (!value) {
    const message = "Enter the operator key provided for this study.";
    showControlError(operatorKeyInput, operatorKeyError, message);
    operatorStatus.textContent = message;
    operatorKeyInput.focus();
    return;
  }
  clearControlError(operatorKeyInput, operatorKeyError);
  operatorCredential = value;
  operatorKeyInput.value = "";
  reflectOperatorState();
  participantRefInput.focus();
}

function changeOperator(): void {
  operatorCredential = "";
  retainedParticipant = undefined;
  clearControlError(operatorKeyInput, operatorKeyError);
  reflectOperatorState();
  operatorKeyInput.focus();
}

function recordingType(): { mimeType?: string; suffix: string } {
  return selectRecordingFormat("MediaRecorder" in window, (mime) => MediaRecorder.isTypeSupported(mime));
}

async function acquireVision(): Promise<HandLandmarker> {
  deviceStatus.textContent = "Loading the on-device hand model…";
  const fileset = await FilesetResolver.forVisionTasks("/capture/wasm");
  return await HandLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: "/capture/models/hand_landmarker.task" },
    runningMode: "VIDEO",
    numHands: 1,
    minHandDetectionConfidence: 0.6,
    minHandPresenceConfidence: 0.6,
    minTrackingConfidence: 0.6,
  });
}

async function acquireCamera(): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("This browser cannot access a camera and microphone.");
  recordingType();
  return await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
  });
}

async function initializeCaptureResources(): Promise<void> {
  if (stream?.active && handLandmarker) return;
  const [nextStream, nextLandmarker] = await acquireResourcePair(
    acquireCamera(),
    acquireVision(),
    (value) => value.getTracks().forEach((track) => track.stop()),
    (value) => value.close(),
  );
  try {
    for (const video of videos) {
      video.srcObject = nextStream;
      await video.play();
    }
  } catch (error) {
    releaseMediaResources(nextStream, videos, () => nextLandmarker.close());
    throw error;
  }
  stream = nextStream;
  handLandmarker = nextLandmarker;
}

function updateReadinessHandStatus(message: string): void {
  if (readinessHandStatus.textContent !== message) readinessHandStatus.textContent = message;
}

function stopReadinessMonitoring(): void {
  if (readinessAnimationFrame) cancelAnimationFrame(readinessAnimationFrame);
  readinessAnimationFrame = 0;
  readinessSampleAt = 0;
}

function startReadinessMonitoring(): void {
  stopReadinessMonitoring();
  updateReadinessHandStatus("Checking the participant's right-hand position.");
  const sample = (now: number): void => {
    if (readiness.hidden || !stream?.active || !handLandmarker) {
      readinessAnimationFrame = 0;
      return;
    }
    if (now - readinessSampleAt >= 250) {
      readinessSampleAt = now;
      const preview = videos[0];
      try {
        if (!preview || preview.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
          updateReadinessHandStatus(readinessHandMessage("missing_hand"));
        } else {
          const detected = handLandmarker.detectForVideo(preview, now);
          const landmarks = detected.landmarks[0];
          const category = detected.handedness[0]?.[0];
          if (!landmarks) {
            updateReadinessHandStatus(readinessHandMessage("missing_hand"));
          } else if (physicalHandedness(category?.categoryName) !== "right") {
            updateReadinessHandStatus(readinessHandMessage("wrong_hand"));
          } else {
            const bounds = guideBoundsForCover(
              preview.videoWidth,
              preview.videoHeight,
              preview.clientWidth,
              preview.clientHeight,
            );
            updateReadinessHandStatus(
              readinessHandMessage(landmarksInsideGuide(landmarks, bounds) ? "valid" : "out_of_guide"),
            );
          }
        }
      } catch {
        updateReadinessHandStatus(readinessHandMessage("unavailable"));
      }
    }
    readinessAnimationFrame = requestAnimationFrame(sample);
  };
  readinessAnimationFrame = requestAnimationFrame(sample);
}

function cleanupDevices(): void {
  stopReadinessMonitoring();
  captureAbort?.();
  captureAbort = undefined;
  releaseMediaResources(stream, videos, handLandmarker ? () => handLandmarker?.close() : undefined);
  stream = undefined;
  for (const canvas of canvases) canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  handLandmarker = undefined;
}

function clearTimelineDocument(): void {
  timeline.removeAttribute("src");
  if (timelineObjectUrl) URL.revokeObjectURL(timelineObjectUrl);
  timelineObjectUrl = undefined;
}

function readinessComplete(): boolean {
  return readinessChecks.length > 0 && readinessChecks.every((check) => check.checked);
}

async function beginReadiness(): Promise<void> {
  clearPanelError(setupError);
  clearControlError(studyIdInput, studyIdError);
  clearControlError(participantRefInput, participantRefError);
  clearControlError(privacyConfirmed, privacyConfirmedError);
  let firstInvalid: HTMLInputElement | undefined;
  if (!studyIdInput.value.trim()) {
    showControlError(studyIdInput, studyIdError, "Enter the study ID.");
    firstInvalid = studyIdInput;
  }
  if (!participantRefInput.value.trim()) {
    showControlError(participantRefInput, participantRefError, "Enter a non-identifying participant code.");
    firstInvalid ??= participantRefInput;
  }
  if (!privacyConfirmed.checked) {
    showControlError(
      privacyConfirmed,
      privacyConfirmedError,
      "Confirm that the protocol, privacy limits, and right to stop were explained.",
    );
    firstInvalid ??= privacyConfirmed;
  }
  if (firstInvalid) {
    firstInvalid.focus();
    return;
  }
  if (!operatorKey()) {
    changeOperator();
    return;
  }
  startReadinessButton.disabled = true;
  sessionSetup.setAttribute("aria-busy", "true");
  statusText.textContent = "Requesting camera and microphone access…";
  try {
    await initializeCaptureResources();
    sessionSetup.hidden = true;
    readiness.hidden = false;
    setProgress("ready");
    deviceStatus.textContent = "Camera, microphone, and on-device hand model are ready.";
    statusText.textContent = "Complete the three operator checks before creating the session.";
    startReadinessMonitoring();
    readiness.querySelector<HTMLElement>("h2")?.focus();
  } catch (error) {
    cleanupDevices();
    throw error;
  } finally {
    startReadinessButton.disabled = false;
    sessionSetup.setAttribute("aria-busy", "false");
  }
}

async function createSession(): Promise<void> {
  if (!readinessComplete()) throw new Error("Complete every recording setup check.");
  clearPanelError(readinessError);
  createSessionButton.disabled = true;
  readiness.setAttribute("aria-busy", "true");
  statusText.textContent = "Creating the coded participant session…";
  try {
    const studyId = studyIdInput.value.trim();
    const externalReference = participantRefInput.value.trim();
    let participantId = retainedParticipantId(retainedParticipant, studyId, externalReference);
    if (!participantId) {
      const participant = await api<{ id: string }>("/v1/participants", {
        method: "POST",
        headers: apiHeaders(true),
        body: JSON.stringify({ study_id: studyId, external_reference: externalReference }),
      });
      participantId = participant.id;
      retainedParticipant = { id: participant.id, studyId, externalReference };
    }
    session = await api<Session>("/v1/sessions", {
      method: "POST",
      headers: apiHeaders(true),
      body: JSON.stringify({ participant_id: participantId, protocol_version: "1.1.0" }),
    });
    retainedParticipant = undefined;
    session.tasks.sort((a, b) => a.order_index - b.order_index);
    taskIndex = 0;
    stopReadinessMonitoring();
    readiness.hidden = true;
    captureArea.hidden = false;
    setProgress("capture");
    renderTask();
    statusText.textContent = "Review the instruction, complete the short practice, and confirm readiness.";
    taskName.focus();
  } finally {
    createSessionButton.disabled = false;
    readiness.setAttribute("aria-busy", "false");
  }
}

function renderTask(): void {
  const current = session?.tasks[taskIndex];
  if (!current || !session) return;
  taskCode.textContent = current.task_code;
  taskName.textContent = current.task_name;
  taskInstructionText.textContent = taskInstruction(current.task_code);
  taskPracticeText.textContent = taskPractice(current.task_code);
  practiceComplete.checked = false;
  operatorReady.checked = false;
  recordButton.disabled = true;
  recordButton.textContent = "Record this task";
  phaseLabel.textContent = "Ready";
  timer.textContent = "15.0 s";
  taskList.replaceChildren(
    ...session.tasks.map((task, index) => {
      const item = document.createElement("li");
      const label = `${task.task_code} · ${task.task_name}`;
      item.textContent = index < taskIndex ? `${label} — completed` : label;
      item.className = index < taskIndex ? "done" : index === taskIndex ? "current" : "";
      if (index === taskIndex) item.setAttribute("aria-current", "step");
      return item;
    }),
  );
}

function updateRecordEnabled(): void {
  recordButton.disabled = !(practiceComplete.checked && operatorReady.checked) || Boolean(pendingCapture);
}

function drawLandmarks(points: { x: number; y: number }[] | undefined): void {
  const canvas = canvases[1];
  const video = videos[1];
  if (!canvas || !video) return;
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!points) return;
  for (const point of points) {
    context.beginPath();
    context.fillStyle = "#000";
    context.arc(point.x * canvas.width, point.y * canvas.height, 8, 0, Math.PI * 2);
    context.fill();
    context.beginPath();
    context.fillStyle = "#5eead4";
    context.arc(point.x * canvas.width, point.y * canvas.height, 5, 0, Math.PI * 2);
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

async function capture(task: Task): Promise<Recording> {
  if (!stream?.active) throw new Error("Camera and microphone are no longer available. Start a new session.");
  const format = recordingType();
  const recorder = new MediaRecorder(stream, format.mimeType ? { mimeType: format.mimeType } : undefined);
  const chunks: BlobPart[] = [];
  const frames: LandmarkFrame[] = [];
  const startedAt = performance.now();
  let running = true;
  let interrupted = false;
  let lastSampleAt = 0;
  let previousPhase = "";
  let animationFrame = 0;
  let finishTimer = 0;

  recorder.addEventListener("dataavailable", (event) => {
    if (event.data.size) chunks.push(event.data);
  });

  return await new Promise<Recording>((resolve, reject) => {
    const cleanup = (): void => {
      running = false;
      window.clearTimeout(finishTimer);
      cancelAnimationFrame(animationFrame);
      document.removeEventListener("visibilitychange", visibilityChanged);
      captureAbort = undefined;
      drawLandmarks(undefined);
    };
    const stop = (wasInterrupted = false): void => {
      if (!running) return;
      interrupted = wasInterrupted;
      running = false;
      if (recorder.state !== "inactive") recorder.stop();
    };
    const visibilityChanged = (): void => {
      if (shouldAbortCapture(document.visibilityState)) stop(true);
    };
    captureAbort = () => stop(true);
    document.addEventListener("visibilitychange", visibilityChanged);
    recorder.addEventListener(
      "stop",
      () => {
        cleanup();
        if (interrupted) reject(new CaptureInterruptedError("Capture stopped because the screen was hidden or locked."));
        else resolve({ blob: new Blob(chunks, { type: recorder.mimeType }), suffix: format.suffix, frames });
      },
      { once: true },
    );
    recorder.addEventListener(
      "error",
      () => {
        cleanup();
        reject(new Error("Browser media recording failed."));
      },
      { once: true },
    );
    startRecorderSafely(recorder, 250, cleanup);

    const sample = (now: number): void => {
      if (!running) return;
      const elapsed = now - startedAt;
      const phase = phaseAt(elapsed);
      if (phase !== previousPhase) {
        previousPhase = phase;
        phaseLabel.textContent = phase;
        phaseAnnouncement.textContent = `${phase} phase`;
      }
      timer.textContent = `${Math.max(0, (TOTAL_CAPTURE_MS - elapsed) / 1000).toFixed(1)} s`;
      const timestamp = activeTimestamp(elapsed);
      const captureVideo = videos[1];
      if (
        timestamp !== null
        && task.task_code !== "T02"
        && now - lastSampleAt >= LANDMARK_SAMPLE_INTERVAL_MS
        && handLandmarker
        && captureVideo
      ) {
        lastSampleAt = now;
        const detected = handLandmarker.detectForVideo(captureVideo, now);
        const landmarks = detected.landmarks[0];
        const category = detected.handedness[0]?.[0];
        drawLandmarks(landmarks);
        const guideBounds = guideBoundsForCover(
          captureVideo.videoWidth,
          captureVideo.videoHeight,
          captureVideo.clientWidth,
          captureVideo.clientHeight,
        );
        const handedness = physicalHandedness(category?.categoryName);
        frames.push(
          landmarks
            ? {
                timestamp_ms: timestamp,
                handedness: handedness === "unknown" ? "left" : handedness,
                landmarks_xyz: landmarks.map((point) => [point.x, point.y, point.z]),
                median_confidence: category?.score ?? 0,
                validity:
                  handedness === "right" && landmarksInsideGuide(landmarks, guideBounds)
                    ? "valid"
                    : "out_of_guide",
              }
            : missingFrame(timestamp),
        );
      }
      animationFrame = requestAnimationFrame(sample);
    };
    animationFrame = requestAnimationFrame(sample);
    finishTimer = window.setTimeout(() => stop(false), TOTAL_CAPTURE_MS);
  });
}

function qualityFromError(error: ApiError): QualityResult | undefined {
  const payload = error.payload as { detail?: unknown } | undefined;
  const candidate = payload?.detail && typeof payload.detail === "object" ? payload.detail : error.payload;
  if (!candidate || typeof candidate !== "object" || !("quality_decision" in candidate)) return undefined;
  try {
    return normalizedQuality(candidate);
  } catch {
    return undefined;
  }
}

async function submitPending(): Promise<QualityResult> {
  if (!pendingCapture || !stream) throw new Error("No captured recording is waiting to be submitted.");
  const facingMode = stream.getVideoTracks()[0]?.getSettings().facingMode;
  const response = await submitRetained(
    pendingCapture,
    async (recording) => {
      const form = new FormData();
      form.append("file", recording.blob, `${pendingCapture?.task.task_code.toLowerCase()}${recording.suffix}`);
      return await api<Upload>("/v1/media", { method: "POST", headers: apiHeaders(), body: form });
    },
    async (uploaded, recording) =>
      await api<unknown>(`/v1/task-instances/${pendingCapture?.task.id}/measure`, {
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
            capture_app_version: "capture-web-0.2.0",
          },
          landmark_frames: recording.frames,
          voiced_intervals: [],
          ddk_event_ms: [],
        }),
      }),
    (error) => isStaleUploadedMediaError(error),
  );
  return normalizedQuality(response);
}

function isStaleUploadedMediaError(error: unknown): boolean {
  if (!(error instanceof ApiError) || ![404, 409].includes(error.status)) return false;
  const payload = error.payload as { detail?: unknown } | undefined;
  const detail = typeof payload?.detail === "string" ? payload.detail.toLowerCase() : "";
  return detail.includes("uploaded media does not exist") || detail.includes("already been claimed");
}

function renderQualityValues(values: Record<string, number | null> | undefined): void {
  qualityValues.replaceChildren();
  if (!values) return;
  for (const [name, value] of Object.entries(values)) {
    const display = displayQualityMetric(name, value);
    const term = document.createElement("dt");
    term.textContent = display.label;
    const detail = document.createElement("dd");
    detail.textContent = display.value;
    qualityValues.append(term, detail);
  }
}

function showCheckpoint(result: QualityResult, mode: CheckpointMode, guidance?: string): void {
  checkpointMode = mode;
  captureArea.setAttribute("aria-busy", "false");
  checkpoint.setAttribute("aria-busy", "false");
  captureArea.hidden = true;
  checkpoint.hidden = false;
  checkpointTitle.textContent = `${pendingCapture?.task.task_code ?? session?.tasks[taskIndex]?.task_code ?? "Task"} recording check`;
  checkpointStatus.textContent = qualityHeading(result.quality_decision);
  checkpointStatus.dataset.decision = result.quality_decision;
  checkpointGuidance.textContent = guidance ?? guidanceFor(result);
  checkpointPrimary.hidden = false;
  qualityReasons.replaceChildren(
    ...result.reason_codes.map((reason) => {
      const item = document.createElement("li");
      item.textContent = qualityReasonLabel(reason);
      return item;
    }),
  );
  renderQualityValues(result.quality_values);
  checkpointPrimary.textContent = mode === "continue" ? "Continue to next task" : mode === "resubmit" ? "Retry upload" : "Record task again";
  if (result.quality_decision === "review_needed") {
    checkpointPrimary.textContent = "Record again only if comfortable";
  }
  const activeTaskId = pendingCapture?.task.id ?? session?.tasks[taskIndex]?.id;
  if (mode === "recapture" && activeTaskId && !canRecapture(taskAttempts.get(activeTaskId) ?? 0)) {
    checkpointPrimary.hidden = true;
    checkpointGuidance.textContent = `${checkpointGuidance.textContent ?? ""} The two-attempt limit has been reached; end the session rather than asking the participant to repeat again.`;
  }
  if (mode === "continue" && session && taskIndex === session.tasks.length - 1) checkpointPrimary.textContent = "View synchronized report";
  checkpointTitle.focus();
}

async function recordCurrentTask(): Promise<void> {
  const task = session?.tasks[taskIndex];
  const activeSessionId = session?.id;
  if (!task || !activeSessionId) return;
  taskAttempts.set(task.id, (taskAttempts.get(task.id) ?? 0) + 1);
  recordButton.disabled = true;
  stopCaptureButton.hidden = false;
  statusText.textContent = `Recording ${task.task_code}. Keep this screen visible and unlocked. The Stop capture and end session action is available.`;
  try {
    const recording = await capture(task);
    stopCaptureButton.hidden = true;
    pendingCapture = { task, recording };
    phaseLabel.textContent = "Processing";
    statusText.textContent = `Uploading and measuring ${task.task_code}…`;
    captureArea.setAttribute("aria-busy", "true");
    const quality = await submitPending();
    if (quality.quality_decision === "accept") showCheckpoint(quality, "continue");
    else {
      pendingCapture = undefined;
      showCheckpoint(quality, "recapture");
    }
  } catch (error) {
    stopCaptureButton.hidden = true;
    if (!session || session.id !== activeSessionId) return;
    if (error instanceof CaptureInterruptedError) {
      cleanupDevices();
      pendingCapture = undefined;
      showCheckpoint(
        { quality_decision: "retry", reason_codes: ["capture_interrupted"] },
        "recapture",
      );
    } else if (error instanceof ApiError) {
      const quality = qualityFromError(error);
      if (quality) {
        pendingCapture = undefined;
        showCheckpoint(quality, "recapture");
      } else if ([404, 409, 422].includes(error.status)) {
        pendingCapture = undefined;
        showCheckpoint(
          { quality_decision: "retry", reason_codes: [] },
          "recapture",
          "The retained recording could not be restored safely. Reopen the devices and record this task again.",
        );
      } else {
        showCheckpoint(
          { quality_decision: "retry", reason_codes: [] },
          "resubmit",
          "The recording is still held in memory. Check the connection, then retry without recording again.",
        );
      }
    } else {
      if (shouldReleaseDevicesAfterCaptureError(Boolean(pendingCapture))) cleanupDevices();
      showCheckpoint(
        { quality_decision: "retry", reason_codes: [] },
        pendingCapture ? "resubmit" : "recapture",
        error instanceof Error ? error.message : String(error),
      );
    }
  }
}

async function retrySubmission(): Promise<void> {
  checkpointPrimary.disabled = true;
  checkpoint.setAttribute("aria-busy", "true");
  checkpointGuidance.textContent = "Retrying the retained recording…";
  try {
    const quality = await submitPending();
    if (quality.quality_decision === "accept") showCheckpoint(quality, "continue");
    else {
      pendingCapture = undefined;
      showCheckpoint(quality, "recapture");
    }
  } catch (error) {
    checkpointGuidance.textContent = error instanceof Error ? error.message : String(error);
  } finally {
    checkpointPrimary.disabled = false;
    checkpoint.setAttribute("aria-busy", "false");
  }
}

function metricLabel(name: string): string {
  const words = name.replaceAll("_", " ").replace("dtc percent", "dual-task cost");
  const label = words.charAt(0).toUpperCase() + words.slice(1);
  return name.startsWith("speech_") ? `${label} (exploratory)` : label;
}

async function renderReport(): Promise<void> {
  if (!session) return;
  const [report, timelineHtml] = await Promise.all([
    api<{ metrics: Record<string, number | null>; note: string }>(`/v1/sessions/${session.id}/report`, {
      headers: apiHeaders(),
    }),
    fetchAuthenticatedHtml(`/v1/sessions/${session.id}/visualization`, operatorKey()),
  ]);
  results.replaceChildren();
  const metricGrid = document.createElement("div");
  metricGrid.className = "metric-grid";
  for (const [name, value] of Object.entries(report.metrics)) {
    const metric = document.createElement("div");
    metric.className = "metric";
    const label = document.createElement("span");
    label.textContent = metricLabel(name);
    const number = document.createElement("strong");
    number.textContent = value === null ? "Unavailable" : `${value.toFixed(1)}%`;
    metric.append(label, number);
    metricGrid.append(metric);
  }
  const limitations = document.createElement("p");
  limitations.className = "notice";
  limitations.textContent = report.note;
  results.append(metricGrid, limitations);
  clearTimelineDocument();
  timelineObjectUrl = URL.createObjectURL(new Blob([timelineHtml], { type: "text/html" }));
  timeline.src = timelineObjectUrl;
  checkpoint.hidden = true;
  reportSection.hidden = false;
  setProgress("report");
  cleanupDevices();
  statusText.textContent = "Session complete. Results describe task performance, not disease.";
  reportSection.querySelector<HTMLElement>("h2")?.focus();
}

async function checkpointAction(): Promise<void> {
  if (checkpointMode === "resubmit") {
    await retrySubmission();
    return;
  }
  if (checkpointMode === "recapture") {
    const recaptureSessionId = session?.id;
    if (!recaptureSessionId) return;
    checkpoint.setAttribute("aria-busy", "true");
    checkpointGuidance.textContent = "Reopening the camera, microphone, and hand-position model…";
    try {
      await reacquireMediaResources(cleanupDevices, initializeCaptureResources);
      if (session?.id !== recaptureSessionId) {
        cleanupDevices();
        return;
      }
      checkpoint.hidden = true;
      pendingCapture = undefined;
      captureArea.hidden = false;
      renderTask();
      statusText.textContent = "Review the recovery instruction, practise, and record this task again.";
      taskName.focus();
    } catch (error) {
      if (session?.id !== recaptureSessionId) {
        cleanupDevices();
        return;
      }
      throw error;
    } finally {
      checkpoint.setAttribute("aria-busy", "false");
    }
    return;
  }
  if (!session) return;
  if (taskIndex === session.tasks.length - 1) {
    checkpoint.setAttribute("aria-busy", "true");
    checkpointGuidance.textContent = "Preparing the synchronized report…";
    try {
      await renderReport();
      pendingCapture = undefined;
      taskIndex = session.tasks.length;
    } finally {
      checkpoint.setAttribute("aria-busy", "false");
    }
    return;
  }
  const nextTaskIndex = nextTaskAfterDecision(taskIndex, session.tasks.length, "accept");
  pendingCapture = undefined;
  taskIndex = nextTaskIndex;
  if (taskIndex < session.tasks.length) {
    checkpoint.hidden = true;
    captureArea.hidden = false;
    renderTask();
    statusText.textContent = "Recording accepted. Prepare the participant for the next task.";
    taskName.focus();
  }
}

function resetSession(startAnother: boolean): void {
  captureAbort?.();
  cleanupDevices();
  session = undefined;
  pendingCapture = undefined;
  retainedParticipant = undefined;
  taskAttempts.clear();
  taskIndex = 0;
  clearTimelineDocument();
  reportSection.hidden = true;
  stopCaptureButton.hidden = true;
  checkpoint.hidden = true;
  captureArea.hidden = true;
  readiness.hidden = true;
  sessionSetup.hidden = false;
  participantRefInput.value = "";
  privacyConfirmed.checked = false;
  readinessChecks.forEach((check) => (check.checked = false));
  createSessionButton.disabled = true;
  clearPanelError(setupError);
  clearPanelError(readinessError);
  clearControlError(studyIdInput, studyIdError);
  clearControlError(participantRefInput, participantRefError);
  clearControlError(privacyConfirmed, privacyConfirmedError);
  updateReadinessHandStatus("Waiting to check the participant's right-hand position.");
  setProgress("setup");
  statusText.textContent = startAnother ? "Ready for another coded participant." : "Session ended and camera and microphone access closed.";
  if (startAnother) {
    participantRefInput.focus();
  } else {
    if (!isLocalDemo) {
      operatorCredential = "";
      operatorKeyInput.focus();
    }
    reflectOperatorState();
  }
}

saveOperatorButton.addEventListener("click", saveOperator);
changeOperatorButton.addEventListener("click", changeOperator);
startReadinessButton.addEventListener("click", () => {
  beginReadiness().catch((error: unknown) => {
    const message = mediaAccessMessage(error);
    showPanelError(setupError, message);
    statusText.textContent = `Setup failed: ${message}`;
    startReadinessButton.focus();
  });
});
readinessChecks.forEach((check) => check.addEventListener("change", () => (createSessionButton.disabled = !readinessComplete())));
createSessionButton.addEventListener("click", () => {
  createSession().catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    showPanelError(readinessError, message);
    statusText.textContent = `Session creation failed: ${message}`;
    createSessionButton.focus();
  });
});
[practiceComplete, operatorReady].forEach((check) => check.addEventListener("change", updateRecordEnabled));
recordButton.addEventListener("click", () => void recordCurrentTask());
stopCaptureButton.addEventListener("click", () => resetSession(false));
checkpointPrimary.addEventListener("click", () => {
  if (checkpointActionInFlight) return;
  checkpointActionInFlight = true;
  checkpointPrimary.disabled = true;
  checkpointAction()
    .catch((error: unknown) => {
      checkpoint.hidden = false;
      checkpoint.setAttribute("aria-busy", "false");
      checkpointGuidance.textContent = error instanceof Error ? error.message : String(error);
      checkpointTitle.focus();
    })
    .finally(() => {
      checkpointActionInFlight = false;
      checkpointPrimary.disabled = false;
    });
});
checkpointSecondary.addEventListener("click", () => resetSession(false));
newSessionButton.addEventListener("click", () => resetSession(true));
endSessionButton.addEventListener("click", () => resetSession(false));
window.addEventListener("pagehide", () => {
  cleanupDevices();
  clearTimelineDocument();
});

reflectOperatorState();
setProgress("setup");
