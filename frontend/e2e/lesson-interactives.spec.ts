import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("a preview pause stops playback and discards an outstanding play response", async ({
  page,
}) => {
  const bridge = await readFile(
    new URL(
      "../../backend/src/app/courses/adapters/video/preview_bridge.js",
      import.meta.url,
    ),
    "utf8",
  );
  // Supply the player boundary before loading the real host bridge.
  const player =
    '<button id="play">Play</button><input id="scrub" value="0">' +
    '<input id="loop" type="checkbox"><nav></nav><script>' +
    "window.ready=Promise.resolve(); window.DURATION=60; window.seek=()=>{};" +
    'document.querySelector("#play").onclick=()=>{const b=document.querySelector("#play");' +
    'b.textContent=b.textContent==="Pause"?"Play":"Pause";};</script>';
  await page.setContent('<iframe sandbox="allow-scripts"></iframe>');
  await page.locator("iframe").evaluate(
    (frame: HTMLIFrameElement, html) => {
      frame.srcdoc = html;
    },
    "<!doctype html><html><head></head><body>" +
      player +
      "<script>" +
      bridge +
      "</script></body></html>",
  );
  const frame = page.frameLocator("iframe");
  await expect(
    frame.getByRole("button", { name: "Fullscreen", exact: true }),
  ).toBeVisible();
  const send = (type: string) =>
    page
      .locator("iframe")
      .evaluate(
        (node: HTMLIFrameElement, message) =>
          node.contentWindow!.postMessage(
            { channel: "lesson-preview", type: message },
            "*",
          ),
        type,
      );
  await send("pause");
  await expect(
    frame.getByRole("button", { name: "Play", exact: true }),
  ).toBeVisible();
  await frame.getByRole("button", { name: "Play", exact: true }).click();
  await send("play-code");
  await expect(
    frame.getByRole("button", { name: "Pause", exact: true }),
  ).toBeVisible();
  await send("pause");
  await send("pause");
  await send("play-code");
  await expect(
    frame.getByRole("button", { name: "Play", exact: true }),
  ).toBeVisible();
  await frame.getByRole("button", { name: "Play", exact: true }).click();
  await send("play-code");
  await expect(
    frame.getByRole("button", { name: "Pause", exact: true }),
  ).toBeVisible();
});

test("builds, refines and publishes through the real API; learners keep the selected version", async ({
  page,
  request,
  browser,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const discovery = await (
    await request.get("/api/v1/published/discovery")
  ).json();
  const lessonId = discovery.lessons.find(
    (item: { title: string }) => item.title === "Newest public lesson",
  ).id as string;
  const root = "/api/v1/lessons/" + lessonId + "/interactives";
  await page.goto("/lessons/" + lessonId + "/interactives/new");
  await page
    .getByLabel("Describe your interactive", { exact: true })
    .fill(
      "A gravity lab where learners change gravity and observe the result.",
    );
  await page
    .getByRole("button", { name: "Build interactive", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Gravity lab", exact: true }),
  ).toBeVisible();
  const id = new URL(page.url()).pathname.split("/").at(-1)!;
  const path = root + "/" + id;
  const frame = page.frameLocator('iframe[title="Gravity lab"]');
  await frame.getByRole("button", { name: "Change gravity" }).click();
  await expect(frame.locator("output")).toHaveText("1.6");
  await page.getByRole("button", { name: "For learners", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("My gravity lab");
  await page.getByRole("button", { name: "Save details", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My gravity lab", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Add to lesson", exact: true })
    .click();
  await expect
    .poll(async () => (await (await request.get(path)).json()).publishedVersion)
    .toBe(1);
  await page.getByRole("button", { name: "Changes", exact: true }).click();
  await page
    .getByLabel("Ask for a change", { exact: true })
    .fill("Add a reset control.");
  await page
    .getByRole("button", { name: "Make this change", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Use version 2 in lesson", exact: true }),
  ).toBeVisible();
  const publicPath = "/api/v1/published/lessons/" + lessonId + "/interactives";
  expect((await (await request.get(publicPath)).json()).items[0].version).toBe(
    1,
  );
  await page
    .getByRole("button", { name: "Go back to this", exact: true })
    .click();
  await expect
    .poll(async () => (await (await request.get(path)).json()).currentVersion)
    .toBe(1);
  await page
    .getByLabel("Ask for a change", { exact: true })
    .fill("Add instructions.");
  await page
    .getByRole("button", { name: "Make this change", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Use version 3 in lesson", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get(publicPath)).json()).items[0].version,
    )
    .toBe(3);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "My gravity lab", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/interactive-studio-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);

  const visitor = await browser.newContext({
    extraHTTPHeaders: {
      "X-Test-Owner": "user_00000000-0000-0000-0000-000000000002",
    },
  });
  const learner = await visitor.newPage();
  await learner.goto("/watch/lessons/" + lessonId);
  const video = learner.locator("video");
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState))
    .toBeGreaterThanOrEqual(2);
  await video.evaluate((v: HTMLVideoElement) => v.play());
  await learner
    .getByRole("navigation", { name: "Parts of this lesson" })
    .getByRole("button", { name: /My gravity lab/ })
    .click();
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.paused))
    .toBe(true);
  const liveFrame = learner.frameLocator('iframe[title="My gravity lab"]');
  await liveFrame.getByRole("button", { name: "Change gravity" }).click();
  await expect(liveFrame.locator("output")).toHaveText("1.6");
  await expect(
    learner.getByText("Things to try", { exact: true }),
  ).toBeVisible();
  await learner.reload();
  await expect(
    liveFrame.getByRole("button", { name: "Change gravity" }),
  ).toBeVisible();
  expect((await visitor.request.get(root)).status()).toBe(404);
  await visitor.close();
  expect(errors).toEqual([]);
});
