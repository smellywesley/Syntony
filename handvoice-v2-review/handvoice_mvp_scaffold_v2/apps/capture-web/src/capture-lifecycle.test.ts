import { describe, expect, it, vi } from "vitest";

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

describe("capture capability and lifecycle", () => {
  it("reports unsupported recording without falling through to a broken recorder", () => {
    expect(() => selectRecordingFormat(true, () => false)).toThrow("No supported synchronized recording format");
    expect(() => selectRecordingFormat(false, () => true)).toThrow("cannot record synchronized");
  });

  it("gives a recovery action when permission is denied", () => {
    expect(mediaAccessMessage(new DOMException("denied", "NotAllowedError"))).toContain("Allow both permissions");
  });

  it("aborts for hidden or background visibility states", () => {
    expect(shouldAbortCapture("visible")).toBe(false);
    expect(shouldAbortCapture("hidden")).toBe(true);
  });

  it("normalizes model handedness for the unmirrored camera frames sent to MediaPipe", () => {
    expect(physicalHandedness("Left")).toBe("right");
    expect(physicalHandedness("Right")).toBe("left");
    expect(physicalHandedness("Right", true)).toBe("right");
    expect(physicalHandedness(undefined)).toBe("unknown");
  });

  it("releases devices when a capture fails before a recording can be retained", () => {
    expect(shouldReleaseDevicesAfterCaptureError(false)).toBe(true);
    expect(shouldReleaseDevicesAfterCaptureError(true)).toBe(false);
  });

  it("stops every track, clears previews, and closes vision", () => {
    const stop = vi.fn();
    const videos: Array<{ srcObject: MediaProvider | null }> = [
      { srcObject: {} as MediaStream },
      { srcObject: {} as MediaStream },
    ];
    const close = vi.fn();
    releaseMediaResources({ getTracks: () => [{ stop }] as unknown as MediaStreamTrack[] }, videos, close);
    expect(stop).toHaveBeenCalledOnce();
    expect(videos.every((video) => video.srcObject === null)).toBe(true);
    expect(close).toHaveBeenCalledOnce();
  });

  it("cleans a slow resource that resolves after the other acquisition fails", async () => {
    let resolveVision!: (value: string) => void;
    const releaseCamera = vi.fn();
    const releaseVision = vi.fn();
    const request = acquireResourcePair(
      Promise.reject(new DOMException("denied", "NotAllowedError")),
      new Promise<string>((resolve) => (resolveVision = resolve)),
      releaseCamera,
      releaseVision,
    );
    resolveVision("vision");
    await expect(request).rejects.toMatchObject({ name: "NotAllowedError" });
    expect(releaseCamera).not.toHaveBeenCalled();
    expect(releaseVision).toHaveBeenCalledWith("vision");
  });

  it("cleans capture listeners when MediaRecorder fails during start", () => {
    const cleanup = vi.fn();
    const recorder = { start: vi.fn(() => { throw new DOMException("unsupported", "NotSupportedError"); }) };
    expect(() => startRecorderSafely(recorder, 250, cleanup)).toThrow("unsupported");
    expect(cleanup).toHaveBeenCalledOnce();
  });
});

describe("visible hand guide", () => {
  it("maps the visible CSS guide into source coordinates for a covered video", () => {
    const bounds = guideBoundsForCover(1280, 720, 640, 640);
    expect(bounds.left).toBeCloseTo(0.32, 2);
    expect(bounds.right).toBeCloseTo(0.68, 2);
    expect(bounds.top).toBeCloseTo(0.12, 2);
    expect(bounds.bottom).toBeCloseTo(0.88, 2);
  });

  it("requires every landmark to be inside the visible guide", () => {
    const bounds = guideBoundsForCover(1280, 720, 1280, 720);
    expect(landmarksInsideGuide([{ x: 0.2, y: 0.2 }, { x: 0.8, y: 0.8 }], bounds)).toBe(true);
    expect(landmarksInsideGuide([{ x: 0.2, y: 0.2 }, { x: 0.9, y: 0.8 }], bounds)).toBe(false);
    expect(landmarksInsideGuide([], bounds)).toBe(false);
  });
});

describe("authenticated report", () => {
  it("loads timeline HTML with the in-memory operator credential", async () => {
    const fetcher = vi.fn(async (_path: string | URL | Request, init?: RequestInit) => {
      expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer operator-secret");
      return new Response("<h1>timeline</h1>", { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }) as typeof fetch;
    await expect(fetchAuthenticatedHtml("/visualization", "operator-secret", fetcher)).resolves.toContain("timeline");
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it("fails closed for an unauthorized or non-HTML report", async () => {
    const unauthorized = vi.fn(async () => new Response("denied", { status: 401, statusText: "Unauthorized" })) as unknown as typeof fetch;
    await expect(fetchAuthenticatedHtml("/visualization", "bad-key", unauthorized)).rejects.toThrow("401 Unauthorized");
    const json = vi.fn(async () => new Response("{}", { headers: { "Content-Type": "application/json" } })) as unknown as typeof fetch;
    await expect(fetchAuthenticatedHtml("/visualization", "key", json)).rejects.toThrow("unsupported document type");
  });
});

describe("retained upload retry", () => {
  it("keeps the blob and storage key while a slow measurement is pending", async () => {
    let finish!: (value: string) => void;
    const measure = vi.fn(() => new Promise<string>((resolve) => (finish = resolve)));
    const retained: { recording: string; upload?: string } = { recording: "blob" };
    const request = submitRetained(retained, async () => "storage/key", measure);
    await Promise.resolve();
    expect(retained).toEqual({ recording: "blob", upload: "storage/key" });
    finish("accepted");
    await expect(request).resolves.toBe("accepted");
  });

  it("does not upload twice when measurement retry follows a network failure", async () => {
    const upload = vi.fn(async () => "storage/key");
    const measure = vi.fn().mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce("accepted");
    const retained: { recording: string; upload?: string } = { recording: "blob" };
    await expect(submitRetained(retained, upload, measure)).rejects.toThrow("offline");
    await expect(submitRetained(retained, upload, measure)).resolves.toBe("accepted");
    expect(upload).toHaveBeenCalledOnce();
    expect(measure).toHaveBeenCalledTimes(2);
  });

  it("re-uploads the retained blob once when the cached storage key is terminally stale", async () => {
    const upload = vi.fn().mockResolvedValueOnce("fresh/key");
    const stale = Object.assign(new Error("missing media"), { status: 404 });
    const measure = vi.fn().mockRejectedValueOnce(stale).mockResolvedValueOnce("accepted");
    const retained: { recording: string; upload?: string } = { recording: "blob", upload: "dead/key" };

    await expect(
      submitRetained(retained, upload, measure, (error) => (error as { status?: number }).status === 404),
    ).resolves.toBe("accepted");

    expect(upload).toHaveBeenCalledOnce();
    expect(upload).toHaveBeenCalledWith("blob");
    expect(measure).toHaveBeenNthCalledWith(1, "dead/key", "blob");
    expect(measure).toHaveBeenNthCalledWith(2, "fresh/key", "blob");
    expect(retained.upload).toBe("fresh/key");
  });

  it("invalidates a replacement key when the terminal storage error repeats", async () => {
    const stale = Object.assign(new Error("missing media"), { status: 422 });
    const retained: { recording: string; upload?: string } = { recording: "blob", upload: "dead/key" };
    await expect(
      submitRetained(
        retained,
        async () => "replacement/key",
        async () => { throw stale; },
        (error) => (error as { status?: number }).status === 422,
      ),
    ).rejects.toThrow("missing media");
    expect(retained.upload).toBeUndefined();
  });
});

describe("interrupted capture recovery", () => {
  it("releases existing camera and vision resources before reacquiring them", async () => {
    const calls: string[] = [];
    const result = await reacquireMediaResources(
      () => calls.push("release"),
      async () => {
        calls.push("acquire");
        return "ready";
      },
    );
    expect(result).toBe("ready");
    expect(calls).toEqual(["release", "acquire"]);
  });
});
