import { defineConfig } from "@playwright/test";

export default defineConfig({
  testMatch: "accounts.spec.ts",
  testDir: "./e2e/authentication",
  outputDir: "./test-results/authentication",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5182",
    browserName: "chromium",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "PYTHONPATH=src:tests .venv/bin/python tests/browser/serve_authentication.py",
      cwd: "../backend",
      url: "http://127.0.0.1:5183/__test/ready",
      timeout: 120000,
    },
    {
      command:
        "npm run build && npm run preview -- --host 127.0.0.1 --port 5182 --strictPort",
      env: { COURSE_MAKER_API_URL: "http://127.0.0.1:5183" },
      url: "http://127.0.0.1:5182",
      timeout: 120000,
    },
  ],
});
