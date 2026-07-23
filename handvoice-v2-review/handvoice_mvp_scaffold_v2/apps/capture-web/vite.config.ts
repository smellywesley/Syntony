import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";
import { resolve } from "node:path";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig(({ mode }) => ({
  base: "/capture/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        capture: resolve(root, "index.html"),
        motorAnnotator: resolve(root, "motor-annotator.html"),
        researchExtractor: resolve(root, "research-extractor.html"),
      },
    },
  },
  resolve: {
    alias: mode === "e2e"
      ? {
          "@mediapipe/tasks-vision": fileURLToPath(new URL("./e2e/mediapipe-mock.ts", import.meta.url)),
        }
      : {},
  },
}));
