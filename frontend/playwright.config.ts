import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: "authentication/**",
  fullyParallel: false,
  workers: 1,
  projects: [
    {
      name: "chromium",
      testIgnore: ["authentication/**", "mobile-navigation.spec.ts"],
    },
    {
      name: "mobile-chrome",
      testMatch: ["account-menu.spec.ts", "mobile-navigation.spec.ts"],
      use: { ...devices["Pixel 7"], browserName: "chromium" },
    },
    {
      name: "mobile-safari",
      testMatch: ["account-menu.spec.ts", "mobile-navigation.spec.ts"],
      use: { ...devices["iPhone 13"], browserName: "webkit" },
    },
  ],
  use: {
    baseURL: "http://127.0.0.1:5180",
    browserName: "chromium",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "PYTHONPATH=src:tests poetry run python tests/browser/serve_guides.py",
      cwd: "../backend",
      url: "http://127.0.0.1:5181/docs",
      timeout: 120000,
      reuseExistingServer: false,
    },
    {
      command:
        "npm run build && npm run preview -- --host 127.0.0.1 --port 5180 --strictPort",
      env: {
        COURSE_MAKER_API_URL: "http://127.0.0.1:5181",
        VITE_COURSE_CREATION: process.env.VITE_COURSE_CREATION ?? "true",
      },
      url: "http://127.0.0.1:5180",
      reuseExistingServer: false,
    },
  ],
});
