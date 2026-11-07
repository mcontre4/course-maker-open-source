const fs = require("fs");
const { chromium } = require(
  process.argv[2] + "/tools/animator/node_modules/playwright-core",
);
const options = JSON.parse(process.argv[3]);
(async () => {
  const browser = await chromium.launch({
    executablePath: options.browser,
    headless: true,
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1100 },
    });
    await context.addCookies(options.cookies);
    const page = await context.newPage();
    const javascriptErrors = [];
    page.on("pageerror", (error) => javascriptErrors.push(error.message));
    for (let n = 0; n < 100; n++) {
      try {
        await page.goto(options.url);
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 100));
      }
    }
    await page.locator("video").first().waitFor();
    await page.waitForFunction(() => {
      const v = document.querySelector("video");
      return v && v.readyState >= 2;
    });
    const initial = await page
      .locator("video")
      .first()
      .evaluate((v) => ({
        duration: v.duration,
        width: v.videoWidth,
        height: v.videoHeight,
      }));
    if (initial.width !== 1920 || initial.height !== 1080)
      throw Error("Invalid browser video dimensions");
    await page
      .locator("video")
      .first()
      .evaluate(async (v) => {
        v.muted = true;
        await v.play();
      });
    await page.waitForFunction(
      () => document.querySelector("video").currentTime > 0.3,
    );
    await page
      .locator("video")
      .first()
      .evaluate((v) => {
        v.pause();
        v.currentTime = 30;
      });
    await page.waitForFunction(() => {
      const v = document.querySelector("video");
      return !v.seeking && v.readyState >= 2;
    });
    const mediaUrl = await page.locator("video").first().evaluate((v) => v.currentSrc);
    const range = await context.request.get(mediaUrl, { headers: { Range: "bytes=0-1023" } });
    if (range.status() !== 206 || (await range.body()).length !== 1024)
      throw Error("Byte-range playback failed");
    await page
      .getByRole("button", { name: "Edit video", exact: true })
      .click();
    await page.locator(".quality-settings > summary").click();
    await page.getByRole("radio", { name: /Fast/ }).check();
    const expectedBackend = "direct";
    if (await page.getByRole("combobox", { name: "Animation and review engine" }).count()) {
      throw Error("Retired engine selector is still visible");
    }
    await page.screenshot({ path: options.output + "/engine-selector.png", fullPage: true });
    await page
      .getByRole("navigation", { name: "What would you like to change?" })
      .getByRole("button", { name: "Visuals", exact: true })
      .click();
    if (!(await page.getByLabel("AI review before delivery").isChecked())) {
      await page.getByLabel("AI review before delivery").check();
      const intermediate = page.waitForResponse(
        (r) => r.url().endsWith("/style") && r.request().method() === "POST",
      );
      await page.getByRole("button", { name: "Save visuals", exact: true }).click();
      const intermediateResponse = await intermediate;
      if (!intermediateResponse.ok()) throw Error("Intermediate review setting failed");
    }
    await page.getByLabel("AI review before delivery").uncheck();
    const saved = page.waitForResponse(
      (r) => r.url().endsWith("/style") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Save visuals", exact: true }).click();
    const saveResponse = await saved;
    if (!saveResponse.ok())
      throw Error("Style save failed: " + (await saveResponse.text()));
    const complete = page.waitForResponse(
      (r) => r.url().endsWith("/video") && r.request().method() === "POST",
      { timeout: 120000 },
    );
    await page
      .getByRole("button", {
        name: /^(Continue video generation|Generate updated video) →$/,
      })
      .click();
    const result = await complete;
    if (!result.ok())
      throw Error("Cached generation failed: " + (await result.text()));
    const sent = result.request().postDataJSON();
    if ((sent.animationBackend || "direct") !== expectedBackend) throw Error("UI sent the wrong engine");
    const body = await result.json();
    if (body.content.animation.reviewStatus !== "skipped")
      throw Error("Incorrect review provenance");
    if (body.content.animation.outputHash !== options.expectedHash)
      throw Error("Changing review replaced artwork");
    await page
      .getByText("Ready for your review · AI review was turned off.")
      .waitFor();
    await page.reload();
    await page.locator("video").first().waitFor();
    await page
      .getByText("Ready for your review · AI review was turned off.")
      .waitFor();
    await page.waitForFunction(
      () => document.querySelector("video").readyState >= 2,
    );
    await page.screenshot({
      path: options.output + "/browser.png",
      fullPage: true,
    });
    if (javascriptErrors.length) throw Error(javascriptErrors.join("\n"));
    fs.writeFileSync(
      options.output + "/verification.json",
      JSON.stringify(
        {
          engine: expectedBackend,
          engine_selection: true,
          browser_playback: initial,
          seek: true,
          range_playback: 206,
          review_toggle: true,
          same_artwork: true,
          reload: true,
          providers_disabled: true,
          javascript_errors: javascriptErrors,
        },
        null,
        2,
      ),
    );
    console.log(
      "Browser verified native playback, seeking, persisted review toggle and cached delivery with providers disabled",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
