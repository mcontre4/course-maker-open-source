import type { ModelPreferences } from "../../application/model-preferences";
import type { HttpTransport } from "./course-backend";

export function withModelOverride(
  transport: HttpTransport,
  preferences: ModelPreferences,
): HttpTransport {
  return (url, init) => {
    const model = preferences.get();
    if (!model || !url.startsWith("/api/v1/")) return transport(url, init);
    const headers = new Headers(init?.headers);
    headers.set("X-Generation-Model", model);
    return transport(url, { ...init, headers });
  };
}
