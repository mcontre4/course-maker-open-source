import { expect, it } from "vitest";
import {
  HttpAuthentication,
  accountAuthenticationEnabled,
} from "./authentication";

function pendingResponse() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function guest() {
  return Response.json({
    user: null,
    csrf_token: "guest-proof",
    google_enabled: false,
  });
}

it("shares in-flight session checks so initial cookie responses cannot race", async () => {
  const pending = pendingResponse();
  let calls = 0;
  const transport: typeof fetch = async () => {
    calls++;
    return pending.promise;
  };
  const auth = new HttpAuthentication(transport);
  const first = auth.session();
  const second = auth.session();
  expect(calls).toBe(1);
  pending.resolve(guest());
  expect(await first).toEqual(await second);
});

it("ignores a late unauthorized response issued before a successful sign-in", async () => {
  const pending = pendingResponse();
  const transport: typeof fetch = async (input) => {
    const url = String(input);
    if (url.endsWith("/session")) return guest();
    if (url.endsWith("/signin"))
      return Response.json({
        user: {
          id: "user-one",
          email: "person@example.com",
          first_name: "Ada",
          last_name: "User",
          verified: true,
        },
        csrf_token: "signed-in-proof",
        google_enabled: false,
      });
    return pending.promise;
  };
  const auth = new HttpAuthentication(transport);
  await auth.session();
  let expirations = 0;
  auth.subscribeExpiration(() => {
    expirations++;
  });
  const earlier = auth.fetch("/api/v1/courses");
  await auth.signIn("person@example.com", "a unique long passphrase");
  pending.resolve(new Response("", { status: 401 }));
  await expect(earlier).rejects.toMatchObject({ name: "AbortError" });
  expect(expirations).toBe(0);
});

it("uses the server rollout mode without accepting malformed or failed configuration", async () => {
  for (const enabled of [false, true]) {
    expect(
      await accountAuthenticationEnabled(async () =>
        Response.json({ enabled }),
      ),
    ).toBe(enabled);
  }
  for (const response of [
    Response.json({}),
    Response.json({ enabled: "false" }),
    new Response("", { status: 503 }),
  ]) {
    await expect(
      accountAuthenticationEnabled(async () => response),
    ).rejects.toThrow();
  }
});
