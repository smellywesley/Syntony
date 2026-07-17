import { defineConfig } from "vite";

export default defineConfig({
  base: "/capture/",
  build: { outDir: "dist", emptyOutDir: true },
});
