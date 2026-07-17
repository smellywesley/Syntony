import { createHash } from "node:crypto";
import { access, cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const publicDir = resolve(root, "public");
const wasmSource = resolve(root, "node_modules/@mediapipe/tasks-vision/wasm");
const wasmTarget = resolve(publicDir, "wasm");
const modelTarget = resolve(publicDir, "models/hand_landmarker.task");
const modelUrl = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
const expectedSha256 = process.env.HANDVOICE_HAND_MODEL_SHA256
  ?? "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1";

await mkdir(resolve(publicDir, "models"), { recursive: true });
try {
  await access(resolve(wasmTarget, "vision_wasm_internal.wasm"));
} catch {
  await cp(wasmSource, wasmTarget, { recursive: true, force: false });
}

let model;
try {
  model = await readFile(modelTarget);
} catch {
  const response = await fetch(modelUrl);
  if (!response.ok) throw new Error(`Model download failed: ${response.status}`);
  model = Buffer.from(await response.arrayBuffer());
  await writeFile(modelTarget, model);
}

const digest = createHash("sha256").update(model).digest("hex");
if (expectedSha256 && digest !== expectedSha256) {
  throw new Error(`Hand model checksum mismatch: ${digest}`);
}
console.log(`Prepared MediaPipe assets; hand model sha256=${digest}`);
