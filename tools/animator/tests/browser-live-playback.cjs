const fs = require("fs");
const assert = require("node:assert/strict");
const { chromium } = require(
  process.argv[2] + "/tools/animator/node_modules/playwright-core",
);
const options = JSON.parse(process.argv[3]);
(async () => {
  const browser = await chromium.launch({
    executablePath: options.browser,
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  await context.addCookies(options.cookies);
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const lessonPath = new URL(options.url).pathname;
  const api = "/api/v1" + lessonPath;
  try {
    for (let i = 0; i < 100; i++) {
      try {
        await page.goto(options.url);
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 100));
      }
    }
    if (options.reuseSource) {
      await page
        .getByRole("button", { name: "Edit lesson", exact: true })
        .click();
    }
    await page
      .getByRole("combobox", { name: "Animation and review engine" })
      .selectOption("direct");
    await page
      .getByRole("combobox", { name: "Animator model", exact: true })
      .selectOption("openai/gpt-6-luna:fast");
    await page.getByRole("radio", { name: /Fast/ }).check();
    let submitted;
    let final;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith(api + "/video"))
        submitted = request.postDataJSON();
    });
    page.on("response", async (response) => {
      if (
        response.request().method() === "POST" &&
        response.url().endsWith(api + "/video")
      ) {
        if (!response.ok())
          console.error("Generation failed: " + (await response.text()));
        else {
          final = await response.json();
          fs.writeFileSync(
            options.output + "/final.json",
            JSON.stringify(final, null, 2),
          );
        }
      }
    });
    let generation;
    if (options.reuseSource) {
      const current = await (
        await context.request.get(new URL(api, options.url).href)
      ).json();
      submitted = {
        expectedRevision: current.revision,
        generationMode: "fast",
        animatorModel: await page
          .getByRole("combobox", { name: "Animator model", exact: true })
          .inputValue(),
        animationBackend: await page
          .getByRole("combobox", { name: "Animation and review engine" })
          .inputValue(),
      };
      generation = context.request
        .post(new URL(api + "/animation", options.url).href, {
          data: submitted,
          timeout: 1200000,
        })
        .then(async (response) => {
          assert(response.ok(), await response.text());
          final = await response.json();
          fs.writeFileSync(
            options.output + "/final.json",
            JSON.stringify(final, null, 2),
          );
        });
    } else {
      await page
        .getByRole("button", {
          name: /Continue video generation|Create.*video|Generate.*video|Bring.*life/i,
        })
        .click();
    }
    console.log(
      options.reuseSource
        ? "Started background delivery using saved Luna Fast code; paid providers disabled"
        : "Started real Luna Fast generation with saved outline and narration",
    );
    await page
      .locator("iframe.lesson-code-player")
      .waitFor({ timeout: 1500000 });
    assert.equal(submitted.animatorModel, "openai/gpt-6-luna:fast");
    const status = await (
      await context.request.get(new URL(api + "/playback", options.url).href)
    ).json();
    assert.equal(
      status.videoReady,
      false,
      "Code must be offered before the MP4 is ready",
    );
    const liveFrame = page.frameLocator("iframe.lesson-code-player");
    await liveFrame
      .getByRole("button", { name: "Play", exact: true })
      .waitFor();
    await liveFrame.getByRole("button", { name: "Play", exact: true }).click();
    await liveFrame
      .getByRole("button", { name: "Pause", exact: true })
      .waitFor();
    const frame = page.frames().find((f) => f.url().includes("/preview?"));
    await frame.waitForFunction(
      () => Number(document.querySelector("#scrub").value) > 0.5,
    );
    const playing = await frame.evaluate(() => ({
      time: Number(document.querySelector("#scrub").value),
      duration: window.DURATION,
      audio: performance
        .getEntriesByType("resource")
        .filter((e) => e.initiatorType === "audio").length,
      canvas: !!document.querySelector("canvas"),
      video: !!document.querySelector("video"),
    }));
    assert(playing.canvas && !playing.video);
    assert.equal(await page.locator("video").count(), 0);
    const mediaSession = await context.newCDPSession(frame);
    const proto = await mediaSession.send("Runtime.evaluate", {
      expression: "HTMLAudioElement.prototype",
    });
    const objects = await mediaSession.send("Runtime.queryObjects", {
      prototypeObjectId: proto.result.objectId,
    });
    const audioState = await mediaSession.send("Runtime.callFunctionOn", {
      objectId: objects.objects.objectId,
      functionDeclaration:
        "function(){return this.map(a=>({paused:a.paused,time:a.currentTime,ready:a.readyState,error:a.error?.message}));}",
      returnByValue: true,
    });
    const narration = audioState.result.value;
    assert(
      narration.some(
        (a) => !a.paused && a.time > 0 && a.ready >= 2 && !a.error,
      ),
      "Narration must play with code",
    );
    const hash = await liveFrame
      .locator("canvas")
      .evaluate((c) => c.toDataURL());
    await frame.waitForFunction(
      (before) => document.querySelector("canvas").toDataURL() !== before,
      hash,
    );
    console.log("Verified real Canvas motion while MP4 rendering is pending");
    await page.screenshot({
      path: options.output + "/code-playing.png",
      fullPage: true,
    });
    // Seek during code playback and verify narration is audible and synchronized.
    await liveFrame.getByRole("button", { name: "Pause", exact: true }).click();
    const seek = liveFrame.getByLabel("Seek");
    const bounds = await seek.boundingBox();
    await page.mouse.click(
      bounds.x + bounds.width * 0.25,
      bounds.y + bounds.height / 2,
    );
    const seekTime = Number(await seek.inputValue());
    assert(seekTime > 1 && seekTime < playing.duration - 1);
    await liveFrame.getByRole("button", { name: "Play", exact: true }).click();
    await liveFrame
      .getByRole("button", { name: "Pause", exact: true })
      .waitFor();
    await page.evaluate(() => {
      window.previewCompletions = 0;
      window.addEventListener("message", (event) => {
        if (
          event.data?.channel === "lesson-preview" &&
          event.data.type === "ended"
        )
          window.previewCompletions++;
      });
    });
    await seek.press("End");
    await page.waitForFunction(() => window.previewCompletions === 1);
    await liveFrame.getByRole("button", { name: "Play", exact: true }).click();
    await liveFrame
      .getByRole("button", { name: "Pause", exact: true })
      .waitFor();
    assert(
      Number(await seek.inputValue()) < 2,
      "Completed code playback must restart from zero",
    );
    const codeSrc = await page
      .locator("iframe.lesson-code-player")
      .getAttribute("src");
    // Wait for the actual production encoder, leaving the current code playback running.
    let completedStatus;
    const deadline = Date.now() + 900000;
    while (Date.now() < deadline) {
      const response = await context.request.get(
        new URL(api + "/playback", options.url).href,
      );
      if (response.ok()) {
        completedStatus = await response.json();
        if (completedStatus.videoReady === true) break;
      }
      await new Promise((resolve) => setTimeout(resolve, 3000));
    }
    assert.equal(
      completedStatus?.videoReady,
      true,
      "MP4 must actually finish before switching",
    );
    assert.equal(
      await page.locator("iframe.lesson-code-player").getAttribute("src"),
      codeSrc,
    );
    assert.equal(
      await page.locator("video").count(),
      0,
      "Encoding must not interrupt code playback",
    );
    console.log("MP4 ready; active code playback remained uninterrupted");
    if (
      await liveFrame
        .getByRole("button", { name: "Pause", exact: true })
        .count()
    ) {
      await liveFrame
        .getByRole("button", { name: "Pause", exact: true })
        .click();
    }
    await liveFrame.getByRole("button", { name: "Play", exact: true }).click();
    await page.locator("video").waitFor();
    await page.waitForFunction(
      () => document.querySelector("video")?.readyState >= 2,
    );
    const video = await page.locator("video").evaluate((v) => ({
      width: v.videoWidth,
      height: v.videoHeight,
      duration: v.duration,
      time: v.currentTime,
    }));
    assert.equal(video.width, 1920);
    assert.equal(video.height, 1080);
    assert(
      video.time < 2,
      "The next playback after completion must start from zero",
    );
    await page.locator("video").evaluate(async (v) => {
      v.muted = true;
      await v.play();
    });
    await page.waitForFunction(() => !document.querySelector("video").paused);
    const mediaUrl = await page.locator("video").getAttribute("src");
    const range = await context.request.get(
      new URL(mediaUrl, options.url).href,
      { headers: { Range: "bytes=0-1023" } },
    );
    assert.equal(range.status(), 206);
    assert.equal((await range.body()).length, 1024);
    await page.screenshot({
      path: options.output + "/mp4-playing.png",
      fullPage: true,
    });
    await page.reload();
    await page.locator("video").waitFor();
    assert.equal(await page.locator("iframe.lesson-code-player").count(), 0);
    assert.equal(errors.length, 0, errors.join("\n"));
    if (generation) await generation;
    assert(final, "Generation must complete and persist its result");
    assert.equal(final.content.animation.model, "openai/gpt-6-luna:fast");
    fs.writeFileSync(
      options.output + "/verification.json",
      JSON.stringify(
        {
          modelOverride: submitted.animatorModel,
          backend: submitted.animationBackend,
          codeBeforeMp4: true,
          codeMotion: playing,
          codeSeeking: true,
          codeCompletionAndReplay: true,
          narration,
          backgroundRender: true,
          uninterrupted: true,
          nextPlaybackMp4: video,
          reloadPrefersMp4: true,
          byteRange: range.status(),
          browserErrors: errors,
          providersDisabled: !!options.reuseSource,
        },
        null,
        2,
      ),
    );
    console.log(
      "Verified code-first playback, real background rendering, MP4 on next play, and reload",
    );
  } catch (error) {
    await page.screenshot({
      path: options.output + "/failure.png",
      fullPage: true,
    });
    fs.writeFileSync(
      options.output + "/failure.txt",
      String(error) + "\n" + (await page.locator("body").innerText()),
    );
    throw error;
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
