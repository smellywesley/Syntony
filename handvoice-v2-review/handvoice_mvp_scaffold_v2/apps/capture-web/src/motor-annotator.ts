import {
  activeTimestampMs,
  addAnnotation,
  removeAnnotation,
} from "./motor-annotator-core";
import {
  containedWindow,
  RESEARCH_WINDOW_MS,
  validCaseId,
} from "./research-extractor-core";

const element = <T extends HTMLElement>(id: string): T => {
  const found = document.getElementById(id);
  if (!found) throw new Error(`Missing element #${id}`);
  return found as T;
};

const caseIdInput = element<HTMLInputElement>("case-id");
const raterIdInput = element<HTMLInputElement>("rater-id");
const videoInput = element<HTMLInputElement>("video-file");
const activeStartInput = element<HTMLInputElement>("active-start-ms");
const preview = element<HTMLVideoElement>("preview");
const currentTime = element<HTMLElement>("active-time");
const markButton = element<HTMLButtonElement>("mark");
const undoButton = element<HTMLButtonElement>("undo");
const eventList = element<HTMLOListElement>("events");
const status = element<HTMLElement>("status");
const download = element<HTMLAnchorElement>("download");
let videoUrl: string | undefined;
let events: number[] = [];

function renderEvents(): void {
  eventList.replaceChildren(
    ...events.map((timestamp) => {
      const item = document.createElement("li");
      item.textContent = `${timestamp} ms `;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        events = removeAnnotation(events, timestamp);
        renderEvents();
      });
      item.append(remove);
      return item;
    }),
  );
  undoButton.disabled = events.length === 0;
  download.hidden = true;
}

function annotationTime(): number {
  const timestamp = activeTimestampMs(
    preview.currentTime,
    Number(activeStartInput.value),
  );
  if (timestamp === null) {
    throw new Error("Move the video into the selected ten-second active window.");
  }
  return timestamp;
}

function mark(): void {
  try {
    events = addAnnotation(events, annotationTime());
    renderEvents();
    status.textContent = `Marked ${events.length} maximal tap openings.`;
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : String(error);
  }
}

function prepareDownload(): void {
  const caseId = caseIdInput.value.trim();
  const raterId = raterIdInput.value.trim();
  if (!validCaseId(caseId) || !validCaseId(raterId)) {
    throw new Error("Case and rater IDs must be pseudonymous safe identifiers.");
  }
  if (events.length === 0) throw new Error("Mark at least one event before export.");
  const payload = {
    schema_version: "1.0",
    profile_version: "handvoice-motor-annotation-v1",
    case_id: caseId,
    rater_id: raterId,
    annotator_blinded_to_detector: true,
    active_window_ms: RESEARCH_WINDOW_MS,
    event_times_ms: events,
  };
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], {
    type: "application/json",
  });
  download.href = URL.createObjectURL(blob);
  download.download = `${caseId}.${raterId}.events.json`;
  download.hidden = false;
}

videoInput.addEventListener("change", () => {
  const file = videoInput.files?.[0];
  if (!file) return;
  if (videoUrl) URL.revokeObjectURL(videoUrl);
  videoUrl = URL.createObjectURL(file);
  preview.src = videoUrl;
  events = [];
  renderEvents();
});

preview.addEventListener("loadedmetadata", () => {
  const activeStart = Number(activeStartInput.value);
  if (!containedWindow(preview.duration, activeStart)) {
    status.textContent = "The selected ten-second active window does not fit inside this video.";
    return;
  }
  preview.currentTime = activeStart / 1000;
  status.textContent = "Ready. Rater must remain blinded to all detector output.";
});

preview.addEventListener("timeupdate", () => {
  const timestamp = activeTimestampMs(
    preview.currentTime,
    Number(activeStartInput.value),
  );
  currentTime.textContent = timestamp === null ? "Outside active window" : `${timestamp} ms`;
  if (timestamp !== null && timestamp >= RESEARCH_WINDOW_MS) preview.pause();
});

markButton.addEventListener("click", mark);
undoButton.addEventListener("click", () => {
  events = events.slice(0, -1);
  renderEvents();
});

document.addEventListener("keydown", (event) => {
  const target = event.target;
  if (
    event.code === "Space"
    && !(target instanceof HTMLInputElement)
    && !(target instanceof HTMLButtonElement)
  ) {
    event.preventDefault();
    mark();
  }
});

element<HTMLButtonElement>("prepare-download").addEventListener("click", () => {
  try {
    prepareDownload();
    status.textContent = "Annotation file prepared.";
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : String(error);
  }
});

renderEvents();
