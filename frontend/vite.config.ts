import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // Keep the legacy service key at the server-side gateway; never expose it in VITE_*.
  const backend = loadEnv(
    mode,
    fileURLToPath(new URL("../backend", import.meta.url)),
    "COURSE_MAKER_",
  );
  const apiKey =
    process.env.COURSE_MAKER_API_KEY || backend.COURSE_MAKER_API_KEY;
  const authEnabled = ["true", "1", "yes", "on"].includes(
    (
      process.env.COURSE_MAKER_AUTH_ENABLED ??
      backend.COURSE_MAKER_AUTH_ENABLED ??
      "false"
    ).toLowerCase(),
  );
  const target =
    process.env.COURSE_MAKER_API_URL ||
    process.env.COURSE_MAKER_API_TARGET ||
    backend.COURSE_MAKER_API_URL ||
    "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      port: process.env.PORT ? Number(process.env.PORT) : 5173,
      allowedHosts: [
        "3e93-2601-645-8800-c460-a8b1-7652-325b-7e0c.ngrok-free.app",
      ],
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
          timeout: 1200000,
          proxyTimeout: 1200000,
          headers:
            !authEnabled && apiKey ? { Authorization: `Bearer ${apiKey}` } : {},
        },
      },
    },
  };
});
