import { describe, expect, it } from "vitest";
import { HttpAuthentication } from "./authentication";

function transportScript(responses: Response[]) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const transport: typeof fetch = async (input, init) => {
    calls.push({ url: String(input), init });
    const response = responses.shift();
    if (!response) throw new Error("Unexpected request");
    return response;
  };
  return { calls, transport };
}

const guest = () =>
  Response.json({
    user: null,
    csrf_token: "csrf-proof",
    google_enabled: false,
  });

describe("cookie authentication transport", () => {
  it("bootstraps CSRF and supplies it to application mutations", async () => {
    const script = transportScript([guest(), Response.json({ id: "course" })]);
    const auth = new HttpAuthentication(script.transport);
    await auth.fetch("/api/v1/courses", { method: "POST", body: "{}" });
    expect(script.calls.map((c) => c.url)).toEqual([
      "/api/v1/auth/session",
      "/api/v1/courses",
    ]);
    const init = script.calls[1].init!;
    expect(init.credentials).toBe("same-origin");
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf-proof");
    expect(new Headers(init.headers).has("Authorization")).toBe(false);
  });

  it("expires the UI session on server rejection", async () => {
    const script = transportScript([new Response("", { status: 401 })]);
    const auth = new HttpAuthentication(script.transport);
    let expired = false;
    auth.subscribeExpiration(() => {
      expired = true;
    });
    expect((await auth.fetch("/api/v1/courses")).status).toBe(401);
    expect(expired).toBe(true);
  });

  it("rejects destinations outside the application API before sending credentials", async () => {
    const script = transportScript([]);
    const auth = new HttpAuthentication(script.transport);
    await expect(auth.fetch("https://evil.example/api")).rejects.toThrow();
    await expect(auth.fetch("//evil.example/api")).rejects.toThrow();
    expect(script.calls).toHaveLength(0);
  });

  it("explains which field the server rejected without repeating input", async () => {
    const rejected = (field: string) =>
      Response.json(
        { detail: [{ loc: ["body", field], msg: "invalid", type: "value" }] },
        { status: 422 },
      );
    const script = transportScript([
      guest(),
      rejected("password"),
      rejected("email"),
      rejected("first_name"),
    ]);
    const auth = new HttpAuthentication(script.transport);
    const input = {
      email: "ada@example.com",
      password: "secret",
      first_name: "Ada",
      last_name: "Lovelace",
    };
    await expect(auth.signUp(input)).rejects.toThrow(
      "Use a password of 15 to 128 characters.",
    );
    await expect(auth.signUp(input)).rejects.toThrow(
      "Enter a valid email address.",
    );
    await expect(auth.signUp(input)).rejects.toThrow(
      "Please check the fields and try again.",
    );
  });

  it("surfaces failed login without expiring an existing session", async () => {
    const script = transportScript([
      guest(),
      Response.json({ detail: "Invalid credentials" }, { status: 401 }),
    ]);
    const auth = new HttpAuthentication(script.transport);
    let expired = false;
    auth.subscribeExpiration(() => {
      expired = true;
    });
    await expect(
      auth.signIn("person@example.com", "a long unique password"),
    ).rejects.toThrow("Invalid credentials");
    expect(expired).toBe(false);
  });
});
