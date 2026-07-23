import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => ({
  base: "/capture/",
  build: { outDir: "dist", emptyOutDir: true },
  resolve: {
    alias: mode === "e2e"
      ? {
          "@mediapipe/tasks-vision": fileURLToPath(new URL("./e2e/mediapipe-mock.ts", import.meta.url)),
        }
      : {},
  },
}));
