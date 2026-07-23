export type RecordingFormat = { mimeType?: string; suffix: string };

export function selectRecordingFormat(
  recorderAvailable: boolean,
  isTypeSupported: (mime: string) => boolean,
): RecordingFormat {
  if (!recorderAvailable) throw new Error("This browser cannot record synchronized camera and microphone media.");
  const candidates = [
    ["video/mp4;codecs=avc1.42E01E,mp4a.40.2", ".mp4"],
    ["video/webm;codecs=vp8,opus", ".webm"],
    ["video/webm", ".webm"],
  ] as const;
  const selected = candidates.find(([mime]) => isTypeSupported(mime));
  if (!selected) throw new Error("No supported synchronized recording format is available in this browser.");
  return { mimeType: selected[0], suffix: selected[1] };
}

export function mediaAccessMessage(error: unknown): string {
  if (error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "SecurityError")) {
    return "Camera or microphone permission was denied. Allow both permissions in browser settings, then try again.";
  }
  if (error instanceof DOMException && error.name === "NotFoundError") {
    return "A camera and microphone are required, but one was not found on this device.";
  }
  return error instanceof Error ? error.message : String(error);
}

export function shouldAbortCapture(visibilityState: DocumentVisibilityState): boolean {
  return visibilityState !== "visible";
}

export type PhysicalHandedness = "left" | "right" | "unknown";

export function physicalHandedness(
  modelLabel: string | undefined,
  inputMirrored = false,
): PhysicalHandedness {
  const label = modelLabel?.toLowerCase();
  if (label !== "left" && label !== "right") return "unknown";
  if (inputMirrored) return label;
  return label === "left" ? "right" : "left";
}

export function shouldReleaseDevicesAfterCaptureError(hasRetainedRecording: boolean): boolean {
  return !hasRetainedRecording;
}

export type GuideBounds = { left: number; right: number; top: number; bottom: number };

const FALLBACK_GUIDE: GuideBounds = { left: 0.18, right: 0.82, top: 0.12, bottom: 0.88 };

export function guideBoundsForCover(
  videoWidth: number,
  videoHeight: number,
  containerWidth: number,
  containerHeight: number,
): GuideBounds {
  if (videoWidth <= 0 || videoHeight <= 0 || containerWidth <= 0 || containerHeight <= 0) {
    return FALLBACK_GUIDE;
  }
  const scale = Math.max(containerWidth / videoWidth, containerHeight / videoHeight);
  const renderedWidth = videoWidth * scale;
  const renderedHeight = videoHeight * scale;
  const croppedX = (renderedWidth - containerWidth) / 2;
  const croppedY = (renderedHeight - containerHeight) / 2;
  return {
    left: (croppedX + containerWidth * FALLBACK_GUIDE.left) / renderedWidth,
    right: (croppedX + containerWidth * FALLBACK_GUIDE.right) / renderedWidth,
    top: (croppedY + containerHeight * FALLBACK_GUIDE.top) / renderedHeight,
    bottom: (croppedY + containerHeight * FALLBACK_GUIDE.bottom) / renderedHeight,
  };
}

export function landmarksInsideGuide(
  points: ReadonlyArray<{ x: number; y: number }>,
  bounds: GuideBounds,
): boolean {
  return points.length > 0 && points.every(
    ({ x, y }) => x >= bounds.left && x <= bounds.right && y >= bounds.top && y <= bounds.bottom,
  );
}

export async function acquireResourcePair<First, Second>(
  first: Promise<First>,
  second: Promise<Second>,
  releaseFirst: (value: First) => void,
  releaseSecond: (value: Second) => void,
): Promise<readonly [First, Second]> {
  const [firstResult, secondResult] = await Promise.allSettled([first, second]);
  if (firstResult.status === "fulfilled" && secondResult.status === "fulfilled") {
    return [firstResult.value, secondResult.value] as const;
  }
  if (firstResult.status === "fulfilled") releaseFirst(firstResult.value);
  if (secondResult.status === "fulfilled") releaseSecond(secondResult.value);
  if (firstResult.status === "rejected") throw firstResult.reason;
  if (secondResult.status === "rejected") throw secondResult.reason;
  throw new Error("Resource acquisition failed without an error.");
}

export function startRecorderSafely(
  recorder: Pick<MediaRecorder, "start">,
  timeslice: number,
  cleanup: () => void,
): void {
  try {
    recorder.start(timeslice);
  } catch (error) {
    cleanup();
    throw error;
  }
}

export async function fetchAuthenticatedHtml(
  path: string,
  operatorKey: string,
  fetcher: typeof fetch = fetch,
): Promise<string> {
  if (!operatorKey) throw new Error("The operator device must be unlocked before loading a report.");
  const response = await fetcher(path, { headers: { Authorization: `Bearer ${operatorKey}` } });
  if (!response.ok) throw new Error(`Report request failed: ${response.status} ${response.statusText}`);
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().includes("text/html")) {
    throw new Error("The report endpoint returned an unsupported document type.");
  }
  return await response.text();
}

export type RetainedSubmission<Recording, Upload> = {
  recording: Recording;
  upload?: Upload;
};

export async function submitRetained<Recording, Upload, Result>(
  retained: RetainedSubmission<Recording, Upload>,
  upload: (recording: Recording) => Promise<Upload>,
  measure: (upload: Upload, recording: Recording) => Promise<Result>,
  shouldRefreshUpload: (error: unknown) => boolean = () => false,
): Promise<Result> {
  retained.upload ??= await upload(retained.recording);
  try {
    return await measure(retained.upload, retained.recording);
  } catch (error) {
    if (!shouldRefreshUpload(error)) throw error;
  }

  retained.upload = undefined;
  retained.upload = await upload(retained.recording);
  try {
    return await measure(retained.upload, retained.recording);
  } catch (error) {
    if (shouldRefreshUpload(error)) retained.upload = undefined;
    throw error;
  }
}

export async function reacquireMediaResources<Result>(
  release: () => void,
  acquire: () => Promise<Result>,
): Promise<Result> {
  release();
  return await acquire();
}

export function releaseMediaResources(
  stream: Pick<MediaStream, "getTracks"> | undefined,
  videos: Array<Pick<HTMLVideoElement, "srcObject">>,
  closeVision: (() => void) | undefined,
): void {
  stream?.getTracks().forEach((track) => track.stop());
  for (const video of videos) video.srcObject = null;
  closeVision?.();
}
