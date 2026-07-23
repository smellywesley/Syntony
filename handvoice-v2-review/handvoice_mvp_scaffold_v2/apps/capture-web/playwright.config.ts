import { defineConfig, devices } from "@playwright/test";

const browserChannel =
  process.env.HANDVOICE_E2E_BROWSER_CHANNEL ?? (process.env.CI ? undefined : "chrome");

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  outputDir: "e2e/artifacts/test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: "e2e/artifacts/report", open: "never" }],
    ["junit", { outputFile: "e2e/artifacts/junit.xml" }],
  ],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:4174/capture/",
    ...(browserChannel ? { channel: browserChannel } : {}),
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    reducedMotion: "reduce",
  },
  webServer: {
    command: "npm run dev:e2e",
    url: "http://127.0.0.1:4174/capture/",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
