/// <reference types="node" />
import { createServer } from "node:http";
import { expect, it } from "vitest";
import { HttpAuthentication } from "./authentication";

function session(user = "user-one") {
  return Response.json({
    user: {
      id: user,
      email: "person@example.com",
      first_name: "Ada",
      last_name: "User",
      verified: true,
    },
    csrf_token: "proof-" + user,
    google_enabled: false,
  });
}

function pendingResponse() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function transportFor(privateRequest: typeof fetch): typeof fetch {
  return async (url, init) => {
    if (String(url).endsWith("/auth/session")) return session();
    if (String(url).endsWith("/auth/signout"))
      return new Response(null, { status: 204 });
    if (String(url).endsWith("/auth/signin")) return session("user-two");
    return privateRequest(url, init);
  };
}

it("rejects late successful data from before an account switch", async () => {
  const pending = pendingResponse();
  const auth = new HttpAuthentication(
    transportFor(async () => pending.promise),
  );
  await auth.session();
  let cached: unknown;
  const earlier = auth
    .fetch("/api/v1/lessons", { method: "POST", body: "{}" })
    .then((response) => response.json())
    .then((data) => {
      cached = data;
    });
  const rejected = expect(earlier).rejects.toMatchObject({
    name: "AbortError",
  });
  await auth.signOut();
  await auth.signIn("other@example.com", "another unique passphrase");
  pending.resolve(Response.json({ title: "Previous account private draft" }));
  await rejected;
  expect(cached).toBeUndefined();
});

async function withStreamingResponse(
  run: (transport: typeof fetch) => Promise<void>,
) {
  const server = createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "application/json" });
    response.write('{"private":');
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string")
    throw new Error("No test server port");
  try {
    await run((_url, init) =>
      fetch(`http://127.0.0.1:${address.port}/`, { signal: init?.signal }),
    );
  } finally {
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
}

it("cancels unread private response bodies when signing out", async () => {
  await withStreamingResponse(async (streaming) => {
    const auth = new HttpAuthentication(transportFor(streaming));
    await auth.session();
    const response = await auth.fetch("/api/v1/lessons/private");
    const rejected = expect(response.json()).rejects.toMatchObject({
      name: "AbortError",
    });
    await auth.signOut();
    await rejected;
  });
});

it("still honors cancellation supplied by the caller", async () => {
  await withStreamingResponse(async (streaming) => {
    const auth = new HttpAuthentication(transportFor(streaming));
    await auth.session();
    const controller = new AbortController();
    const response = await auth.fetch("/api/v1/lessons/private", {
      signal: controller.signal,
    });
    const rejected = expect(response.json()).rejects.toMatchObject({
      name: "AbortError",
    });
    controller.abort();
    await rejected;
  });
});

it("rejects old account data when a session refresh discovers a different user", async () => {
  const pending = pendingResponse();
  let currentUser = "user-one";
  const auth = new HttpAuthentication(async (url) =>
    String(url).endsWith("/auth/session")
      ? session(currentUser)
      : pending.promise,
  );
  await auth.session();
  const earlier = auth.fetch("/api/v1/lessons");
  const rejected = expect(earlier).rejects.toMatchObject({
    name: "AbortError",
  });
  currentUser = "user-two";
  await auth.session();
  pending.resolve(Response.json({ title: "Previous account private draft" }));
  await rejected;
});

it("keeps current private requests valid when sign-in fails", async () => {
  const pending = pendingResponse();
  const normal = transportFor(async () => pending.promise);
  const auth = new HttpAuthentication((url, init) =>
    String(url).endsWith("/auth/signin")
      ? Promise.resolve(
          Response.json({ detail: "Invalid credentials" }, { status: 401 }),
        )
      : normal(url, init),
  );
  await auth.session();
  const earlier = auth.fetch("/api/v1/lessons");
  await expect(
    auth.signIn("other@example.com", "another unique passphrase"),
  ).rejects.toThrow("Invalid credentials");
  pending.resolve(Response.json({ title: "Current account draft" }));
  expect(await (await earlier).json()).toEqual({
    title: "Current account draft",
  });
});

it("does not send an old private write when CSRF bootstrap discovers a different user", async () => {
  let sessionChecks = 0;
  let writes = 0;
  const auth = new HttpAuthentication(async (url, init) => {
    if (String(url).endsWith("/auth/session"))
      return session(++sessionChecks === 1 ? "user-one" : "user-two");
    if (init?.method === "POST") {
      writes++;
      return Response.json({ title: "Should not be saved to the new account" });
    }
    return new Response(null, { status: 401 });
  });
  await auth.session();
  await auth.fetch("/api/v1/expired");
  await expect(
    auth.fetch("/api/v1/lessons", { method: "POST", body: "{}" }),
  ).rejects.toMatchObject({ name: "AbortError" });
  expect(writes).toBe(0);
});
