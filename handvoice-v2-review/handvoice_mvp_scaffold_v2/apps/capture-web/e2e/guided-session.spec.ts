import { expect, test, type Page, type Route } from "@playwright/test";

const tasks = [
  { id: "task-t01", task_code: "T01", task_name: "Right-hand tapping", order_index: 1 },
  { id: "task-t02", task_code: "T02", task_name: "Speech rhythm", order_index: 2 },
  { id: "task-t03", task_code: "T03", task_name: "Combined tapping and speech", order_index: 3 },
];

function json(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installBrowserMediaMock(page: Page): Promise<void> {
  await page.addInitScript(() => {
    let currentStreamActive = true;
    const track = {
      stop: () => { currentStreamActive = false; },
      getSettings: () => ({ facingMode: "environment" }),
    };
    const stream = {
      get active() { return currentStreamActive; },
      getTracks: () => [track, track],
      getVideoTracks: () => [track],
    };

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => {
          const controls = window as unknown as {
            __handvoiceDelayNextMedia?: boolean;
            __handvoiceRejectNextMedia?: boolean;
          };
          if (controls.__handvoiceDelayNextMedia) {
            controls.__handvoiceDelayNextMedia = false;
            await new Promise((resolve) => window.setTimeout(resolve, 1_000));
          }
          if (controls.__handvoiceRejectNextMedia) {
            controls.__handvoiceRejectNextMedia = false;
            throw new DOMException("Simulated media reacquisition failure", "NotAllowedError");
          }
          currentStreamActive = true;
          return stream;
        },
      },
    });
    Object.defineProperties(HTMLMediaElement.prototype, {
      readyState: { configurable: true, get: () => 4 },
      videoWidth: { configurable: true, get: () => 1280 },
      videoHeight: { configurable: true, get: () => 720 },
    });
    const assignedStreams = new WeakMap<HTMLMediaElement, unknown>();
    Object.defineProperty(HTMLMediaElement.prototype, "srcObject", {
      configurable: true,
      get() { return assignedStreams.get(this); },
      set(value) { assignedStreams.set(this, value); },
    });
    HTMLMediaElement.prototype.play = async () => undefined;

    class DeterministicMediaRecorder extends EventTarget {
      static isTypeSupported(): boolean { return true; }
      readonly mimeType = "video/webm";
      state: "inactive" | "recording" = "inactive";

      start(): void { this.state = "recording"; }

      stop(): void {
        if (this.state === "inactive") return;
        this.state = "inactive";
        const dataEvent = new Event("dataavailable") as Event & { data: Blob };
        dataEvent.data = new Blob(["deterministic-e2e-media"], { type: this.mimeType });
        this.dispatchEvent(dataEvent);
        queueMicrotask(() => this.dispatchEvent(new Event("stop")));
      }
    }

    Object.defineProperty(window, "MediaRecorder", {
      configurable: true,
      value: DeterministicMediaRecorder,
    });
  });
}

async function completeTask(page: Page, expectedCode: string): Promise<void> {
  await expect(page.locator("#task-code")).toHaveText(expectedCode);
  await page.locator("#practice-complete").check();
  await page.locator("#operator-ready").check();
  await page.getByRole("button", { name: "Record this task" }).click();
  await expect(page.getByRole("button", { name: "Stop capture and end session" })).toBeVisible();
  await page.clock.runFor(15_100);
  await expect(page.getByRole("button", { name: "Stop capture and end session" })).toBeHidden();
}

test("staff completes T01 to T03, recovers from QC retry, and reviews the inline timeline", async ({ page }, testInfo) => {
  await page.clock.install();
  await installBrowserMediaMock(page);

  let mediaSequence = 0;
  let t01Measurements = 0;
  let forceT01Retry = false;
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    expect(request.headers().authorization).toBe("Bearer e2e-operator-key");

    if (request.method() === "POST" && url.pathname.endsWith("/v1/participants")) {
      const body = request.postDataJSON();
      expect(body.study_id).toBe("HV-DEMO");
      expect(body.external_reference).toMatch(/^DEMO-CODE-(001|STOP|RACE|RACEFAIL|LIMIT)$/);
      await json(route, { id: "participant-demo" });
      return;
    }
    if (request.method() === "POST" && url.pathname.endsWith("/v1/sessions")) {
      await json(route, { id: "session-demo", tasks });
      return;
    }
    if (request.method() === "POST" && url.pathname.endsWith("/v1/media")) {
      mediaSequence += 1;
      await json(route, { storage_key: `e2e/media-${mediaSequence}.webm`, sha256: `sha-${mediaSequence}` });
      return;
    }
    if (request.method() === "POST" && url.pathname.includes("/measure")) {
      const taskId = url.pathname.split("/").at(-2);
      if (taskId === "task-t01" && forceT01Retry) {
        t01Measurements += 1;
        await json(route, {
          quality_decision: "review_needed",
          reason_codes: ["insufficient_motor_events"],
          quality_values: { motor_event_count: 2 },
          guidance_key: "quality.review_needed.insufficient_motor_events",
        });
        return;
      }
      if (taskId === "task-t01" && t01Measurements++ === 0) {
        await json(route, {
          quality_decision: "retry",
          reason_codes: ["low_audio_snr"],
          quality_values: { audio_snr_db: 8.2 },
          guidance_key: "retry.low_audio_snr",
        });
        return;
      }
      await json(route, {
        quality_decision: "accept",
        reason_codes: [],
        quality_values: { audio_snr_db: 21.4, valid_frame_fraction: 0.97 },
        guidance_key: "accept.capture_quality",
      });
      return;
    }
    if (request.method() === "GET" && url.pathname.endsWith("/report")) {
      await json(route, {
        metrics: { motor_dual_task_cost_percent: 12.3, speech_dual_task_cost_percent: 8.7 },
        note: "Candidate speech outputs are exploratory and unvalidated; no diagnosis is generated.",
      });
      return;
    }
    if (request.method() === "GET" && url.pathname.endsWith("/visualization")) {
      await route.fulfill({
        status: 200,
        contentType: "text/html; charset=utf-8",
        body: "<!doctype html><html><body><h1>Synchronized hand and speech timeline</h1><p>Deterministic demo events</p></body></html>",
      });
      return;
    }
    await route.abort("blockedbyclient");
  });

  await page.goto("./");
  await expect(page.getByText(/synthetic or prerecorded material only/i)).toBeVisible();
  await page.getByLabel("Operator key").fill("e2e-operator-key");
  await page.getByRole("button", { name: "Unlock device" }).click();
  await expect(page.getByText("Operator device unlocked", { exact: false })).toBeVisible();

  await page.getByLabel("Participant code (required)").fill("DEMO-CODE-001");
  await page.getByLabel(/I have explained the protocol/).check();
  await page.getByRole("button", { name: "Check camera and microphone" }).click();
  await expect(page.getByRole("heading", { name: "Check the recording setup" })).toBeVisible();
  for (const check of await page.locator(".readiness-check").all()) await check.check();
  await page.getByRole("button", { name: "Create session" }).click();

  await completeTask(page, "T01");
  await expect(page.getByText("Retry needed", { exact: true })).toBeVisible();
  await expect(page.getByText(/Speech was difficult to distinguish/)).toBeVisible();
  await page.locator("#checkpoint-primary").evaluate((button) => {
    button.click();
    button.click();
  });

  await completeTask(page, "T01");
  await expect(page.getByText("Accepted", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Continue to next task" }).click();

  await completeTask(page, "T02");
  await page.getByRole("button", { name: "Continue to next task" }).click();

  await completeTask(page, "T03");
  await page.getByRole("button", { name: "View synchronized report" }).click();

  await expect(page.getByRole("heading", { name: "Synchronized session report" })).toBeVisible();
  await expect(page.getByText("12.3%", { exact: true })).toBeVisible();
  await expect(page.getByText(/exploratory and unvalidated/i)).toBeVisible();
  const timeline = page.locator("#timeline");
  await expect(timeline).toHaveAttribute("src", /^blob:/);
  await expect(page.getByText(/not disease/)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("inline-report.png"), fullPage: true });

  // The participant/operator stop control must abort capture, release the
  // session and return the shared device to its locked state.
  await page.getByRole("button", { name: "Start another participant" }).click();
  await page.getByLabel("Participant code (required)").fill("DEMO-CODE-STOP");
  await page.getByLabel(/I have explained the protocol/).check();
  await page.getByRole("button", { name: "Check camera and microphone" }).click();
  for (const check of await page.locator(".readiness-check").all()) await check.check();
  await page.getByRole("button", { name: "Create session" }).click();
  await page.locator("#practice-complete").check();
  await page.locator("#operator-ready").check();
  await page.getByRole("button", { name: "Record this task" }).click();
  await page.getByRole("button", { name: "Stop capture and end session" }).click();
  await expect(page.getByRole("heading", { name: "Unlock this operator device" })).toBeVisible();

  // Two nonaccepted attempts must end in a safe stop, not an unlimited retry loop.
  forceT01Retry = true;
  await page.getByLabel("Operator key").fill("e2e-operator-key");
  await page.getByRole("button", { name: "Unlock device" }).click();
  await page.getByLabel("Participant code (required)").fill("DEMO-CODE-RACE");
  await page.getByLabel(/I have explained the protocol/).check();
  await page.getByRole("button", { name: "Check camera and microphone" }).click();
  for (const check of await page.locator(".readiness-check").all()) await check.check();
  await page.getByRole("button", { name: "Create session" }).click();
  await completeTask(page, "T01");
  await page.evaluate(() => {
    (window as unknown as { __handvoiceDelayNextMedia?: boolean }).__handvoiceDelayNextMedia = true;
  });
  await page.getByRole("button", { name: "Record again only if comfortable" }).click();
  await page.getByRole("button", { name: "End session" }).click();
  await page.clock.runFor(1_100);
  await expect(page.getByRole("heading", { name: "Unlock this operator device" })).toBeVisible();
  await expect(page.locator("#capture-area")).toBeHidden();

  await page.getByLabel("Operator key").fill("e2e-operator-key");
  await page.getByRole("button", { name: "Unlock device" }).click();
  await page.getByLabel("Participant code (required)").fill("DEMO-CODE-RACEFAIL");
  await page.getByLabel(/I have explained the protocol/).check();
  await page.getByRole("button", { name: "Check camera and microphone" }).click();
  for (const check of await page.locator(".readiness-check").all()) await check.check();
  await page.getByRole("button", { name: "Create session" }).click();
  await completeTask(page, "T01");
  await page.evaluate(() => {
    const controls = window as unknown as {
      __handvoiceDelayNextMedia?: boolean;
      __handvoiceRejectNextMedia?: boolean;
    };
    controls.__handvoiceDelayNextMedia = true;
    controls.__handvoiceRejectNextMedia = true;
  });
  await page.getByRole("button", { name: "Record again only if comfortable" }).click();
  await page.getByRole("button", { name: "End session" }).click();
  await page.clock.runFor(1_100);
  await expect(page.getByRole("heading", { name: "Unlock this operator device" })).toBeVisible();
  await expect(page.locator("#checkpoint")).toBeHidden();

  await page.getByLabel("Operator key").fill("e2e-operator-key");
  await page.getByRole("button", { name: "Unlock device" }).click();
  await page.getByLabel("Participant code (required)").fill("DEMO-CODE-LIMIT");
  await page.getByLabel(/I have explained the protocol/).check();
  await page.getByRole("button", { name: "Check camera and microphone" }).click();
  for (const check of await page.locator(".readiness-check").all()) await check.check();
  await page.getByRole("button", { name: "Create session" }).click();
  await completeTask(page, "T01");
  await page.getByRole("button", { name: "Record again only if comfortable" }).click();
  await completeTask(page, "T01");
  await expect(page.getByText(/two-attempt limit has been reached/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Record again only if comfortable" })).toBeHidden();
  await expect(page.getByRole("button", { name: "End session" })).toBeVisible();

  expect(t01Measurements).toBe(6);
  expect(mediaSequence).toBe(8);
});
