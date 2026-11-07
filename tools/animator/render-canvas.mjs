import fs from "node:fs/promises";
import path from "node:path";
import http from "node:http";
import { spawn, execFileSync } from "node:child_process";
import { once } from "node:events";
import { chromium } from "playwright-core";

const [projectArg, outputArg, mode = "full"] = process.argv.slice(2);
if (!projectArg || !outputArg)
  throw new Error("Usage: render-canvas.mjs PROJECT OUTPUT [preview|full]");
const project = path.resolve(projectArg),
  output = path.resolve(outputArg);
await fs.mkdir(output, { recursive: true });
// A corrected storyboard must never retain frames from the previous implementation.
for (const name of await fs.readdir(output)) {
  if (/^(?:frame-\d+|contact-\d+|motion-\d+)\.png$/.test(name)) {
    await fs.unlink(path.join(output, name));
  }
}
const timeline = JSON.parse(
  await fs.readFile(path.join(project, "timeline.json")),
);
const types = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".json": "application/json",
  ".woff2": "font/woff2",
  ".wav": "audio/wav",
};
const server = http.createServer(async (req, res) => {
  try {
    const filename = path.resolve(
      project,
      "." + decodeURIComponent(new URL(req.url, "http://local").pathname),
    );
    if (!filename.startsWith(project + path.sep)) throw Error();
    res.setHeader(
      "Content-Type",
      types[path.extname(filename)] || "application/octet-stream",
    );
    res.end(await fs.readFile(filename));
  } catch {
    res.writeHead(404);
    res.end();
  }
});
server.listen(0, "127.0.0.1");
await once(server, "listening");
const origin = "http://127.0.0.1:" + server.address().port;
let browser;
try {
  browser = await chromium.launch({
    executablePath:
      process.env.REMOTION_BROWSER_EXECUTABLE ||
      "/usr/bin/chromium-headless-shell",
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage({
      viewport: { width: 1280, height: 800 },
    }),
    faults = [];
  const garbageCollector = await page.context().newCDPSession(page);
  const startupFailure = new Promise((_, reject) => {
    page.on("pageerror", (e) => {
      faults.push(e.stack || e.message);
      reject(e);
    });
  });
  const failedResources = [];
  page.on("requestfailed", (request) =>
    failedResources.push(`${request.url()}: ${request.failure()?.errorText}`),
  );
  page.on("response", (response) => {
    if (response.status() >= 400)
      failedResources.push(`${response.url()}: HTTP ${response.status()}`);
  });
  await page.route("**/*", (route) =>
    route
      .request()
      .url()
      .startsWith(origin + "/")
      ? route.continue()
      : route.abort(),
  );
  try {
    await Promise.race([
      startupFailure,
      (async () => {
        await page.goto(origin + "/player.html");
        await Promise.all([
          // Propagate rejected initialization (fonts, timeline, first draw).
          page.evaluate(() => window.ready),
          page.waitForFunction(() => window.done, null, { timeout: 30000 }),
        ]);
      })(),
    ]);
  } catch (error) {
    throw new Error(
      "Canvas player initialization failed: " + error.message +
        (faults.length ? "\nBrowser errors:\n" + faults.join("\n") : "") +
        (failedResources.length
          ? "\nFailed resources:\n" + failedResources.slice(-10).join("\n")
          : ""),
      { cause: error },
    );
  }
  const plan = await page.evaluate(() => window.visualPlan);
  const events = await page.evaluate(() => window.cueEvents);
  if (!Array.isArray(events)) throw Error("Cue event manifest is required");
  const expected = timeline.scenes.flatMap((s) =>
    s.cues.map((c) => ({
      scene: s.scene_id,
      id: c.cue_id,
      time: s.start_sec + c.start_sec,
    })),
  );
  if (events.length !== expected.length)
    throw Error("Cue coverage does not match narration");
  for (const cue of expected) {
    const matches = events.filter(
      (e) => e.scene_id === cue.scene && e.cue_id === cue.id,
    );
    if (
      matches.length !== 1 ||
      !Number.isFinite(matches[0].at_sec) ||
      Math.abs(matches[0].at_sec - cue.time) > 1 / 30 ||
      !matches[0].action
    )
      throw Error("Invalid cue event: " + cue.scene + "/" + cue.id);
  }
  const board = JSON.parse(
    await fs.readFile(path.join(project, "../inputs.json")),
  );
  const source = await fs.readFile(path.join(project, "animation.js"), "utf8");
  for (const scene of board.storyboard.scenes)
    for (const eq of scene.equations)
      if (!source.includes(eq)) throw Error("Missing required equation: " + eq);
  if (!Array.isArray(plan) || !plan.length || plan.length > 100)
    throw Error("Visual storyboard needs 1–100 shots");
  const ids = new Set(timeline.scenes.map((s) => s.scene_id));
  for (const shot of plan) {
    if (
      !ids.has(shot.scene_id) ||
      !Number.isFinite(shot.at_sec) ||
      shot.at_sec < 0 ||
      shot.at_sec >= timeline.duration_sec ||
      !shot.composition ||
      !shot.continuity ||
      !shot.camera ||
      !Array.isArray(shot.objects)
    )
      throw Error("Invalid visual shot plan");
  }
  if ([...ids].some((id) => !plan.some((s) => s.scene_id === id)))
    throw Error("Every narration segment needs a visual shot");
  await fs.writeFile(
    path.join(output, "visual-plan.json"),
    JSON.stringify(plan, null, 2),
  );
  const frames = new Set(plan.map((s) => Math.floor(s.at_sec * 30)));
  // A bounded temporal strip per scene exposes changes between sparse samples.
  const motion = mode === "preview" ? [] : timeline.scenes.map((scene) => {
    const cue = scene.cues[Math.floor(scene.cues.length / 2)];
    const start = cue ? cue.absolute_start_frame : scene.start_frame;
    return Array.from({ length: 8 }, (_, i) => Math.max(scene.start_frame,
      Math.min(scene.start_frame + scene.duration_frames - 1, start - 1 + i * 6)));
  });
  for (const strip of motion) for (const frame of strip) frames.add(frame);
  frames.add(0);
  frames.add(timeline.duration_frames - 1);
  if (mode !== "preview") {
    for (let f = 0; f < timeline.duration_frames; f += 60) frames.add(f);
    for (const s of timeline.scenes) {
      frames.add(s.start_frame);
      frames.add(
        Math.min(
          timeline.duration_frames - 1,
          s.start_frame + s.duration_frames - 1,
        ),
      );
      for (const c of s.cues)
        for (const d of [-1, 0, 15, 45])
          frames.add(
            Math.max(
              0,
              Math.min(
                timeline.duration_frames - 1,
                c.absolute_start_frame + d,
              ),
            ),
          );
    }
  }
  const grab = async (f) =>
    Buffer.from(
      await page.evaluate((t) => {
        window.seek(t);
        return document
          .querySelector("canvas")
          .toDataURL("image/png")
          .split(",")[1];
      }, f / 30),
      "base64",
    );
  for (const f of [...frames].sort((a, b) => a - b))
    await fs.writeFile(
      path.join(output, "frame-" + String(f).padStart(6, "0") + ".png"),
      await grab(f),
    );
  for (const shot of plan.slice().reverse()) {
    const f = Math.floor(shot.at_sec * 30),
      a = await grab(f);
    await grab(0);
    if (!a.equals(await grab(f)))
      throw Error("History-dependent rendering at frame " + f);
  }
  if (faults.length) throw Error(faults.join("\n"));
  const sheetScript = `from PIL import Image,ImageDraw\nfrom pathlib import Path\nimport sys\np=Path(sys.argv[1]); fs=sorted(p.glob('frame-*.png'))\nfor start in range(0,len(fs),9):\n im=Image.new('RGB',(1920,1152),'#10122d');d=ImageDraw.Draw(im)\n for i,f in enumerate(fs[start:start+9]):\n  x=(i%3)*640;y=(i//3)*384\n  with Image.open(f) as src: im.paste(src.convert('RGB').resize((640,360)),(x,y))\n  d.text((x+8,y+363),f.name,fill='white')\n im.save(p/('contact-%02d.png'%(start//9)))`;
  execFileSync("python3", ["-c", sheetScript, output]);
  await fs.writeFile(path.join(output, "motion-frames.json"), JSON.stringify(motion));
  const motionScript = `from PIL import Image,ImageDraw\nfrom pathlib import Path\nimport json,sys\np=Path(sys.argv[1])\nfor i,frames in enumerate(json.loads((p/'motion-frames.json').read_text())):\n im=Image.new('RGB',(1920,768),'#10122d');d=ImageDraw.Draw(im)\n for j,f in enumerate(frames):\n  x=(j%4)*480;y=(j//4)*384\n  with Image.open(p/('frame-%06d.png'%f)) as src: im.paste(src.convert('RGB').resize((480,270)),(x,y))\n  d.text((x+8,y+285),'%.3fs'%(f/30),fill='white')\n im.save(p/('motion-%02d.png'%i))`;
  execFileSync("python3", ["-c", motionScript, output]);
  if (mode === "preview" || mode === "review") {
    console.log("Storyboard and deterministic key frames rendered");
  } else {
    const audio = await page.evaluate(() => window.renderSound());
    if (!Number.isFinite(audio.peak) || audio.peak > 1.01)
      throw Error("Invalid effects mix");
    const sound = path.join(output, "effects.f32");
    await fs.writeFile(sound, Buffer.from(audio.data, "base64"));
    const args = [
      "-y",
      "-f",
      "image2pipe",
      "-vcodec",
      "mjpeg",
      "-r",
      "30",
      "-i",
      "pipe:0",
      "-f",
      "f32le",
      "-ar",
      "48000",
      "-ac",
      "2",
      "-i",
      sound,
    ];
    for (const scene of timeline.scenes)
      args.push("-i", path.join(project, scene.audio));
    const filters = [
      `[1:a]afade=t=out:st=${Math.max(0, timeline.duration_sec - 1)}:d=1[sfx]`,
    ];
    timeline.scenes.forEach((s, i) =>
      filters.push(
        `[${i + 2}:a]aresample=48000,adelay=${Math.round(s.start_sec * 48000)}S:all=1[a${i}]`,
      ),
    );
    filters.push(
      "[sfx]" +
        timeline.scenes.map((_, i) => `[a${i}]`).join("") +
        `amix=inputs=${timeline.scenes.length + 1}:normalize=0:duration=longest,alimiter=limit=0.95:latency=1[mix]`,
    );
    args.push(
      "-filter_complex",
      filters.join(";"),
      "-map",
      "0:v",
      "-map",
      "[mix]",
      "-vf",
      "scale=1920:1080",
      "-c:v",
      "libx264",
      "-preset",
      "fast",
      "-crf",
      "19",
      "-pix_fmt",
      "yuv420p",
      "-c:a",
      "aac",
      "-b:a",
      "192k",
      "-t",
      String(timeline.duration_frames / 30),
      "-movflags",
      "+faststart",
      path.join(output, "lesson.mp4"),
    );
    const proc = spawn("ffmpeg", args, { stdio: ["pipe", "ignore", "pipe"] });
    let error = "";
    proc.stderr.on("data", (d) => (error = (error + d).slice(-5000)));
    const exit = new Promise((resolve, reject) => {
      proc.on("error", reject);
      proc.on("close", (code) => (code ? reject(Error(error)) : resolve()));
    });
    for (let f = 0; f < timeline.duration_frames; f++) {
      // Canvas backing stores and encoded image buffers can outlive JS heap
      // pressure. Release them regularly during long offline render sessions.
      if (f % 60 === 0)
        await garbageCollector.send("HeapProfiler.collectGarbage");
      const data = await page.evaluate((t) => {
        window.seek(t);
        return document
          .querySelector("canvas")
          .toDataURL("image/jpeg", 0.94)
          .split(",")[1];
      }, f / 30);
      if (!proc.stdin.write(Buffer.from(data, "base64")))
        await once(proc.stdin, "drain");
      if (f % 150 === 0)
        console.log("render " + f + "/" + timeline.duration_frames);
    }
    proc.stdin.end();
    await exit;
    if (faults.length) throw Error(faults.join("\n"));
    const probe = JSON.parse(
      execFileSync(
        "ffprobe",
        [
          "-v",
          "error",
          "-show_streams",
          "-show_format",
          "-of",
          "json",
          path.join(output, "lesson.mp4"),
        ],
        { encoding: "utf8" },
      ),
    );
    const v = probe.streams.find((s) => s.codec_type === "video"),
      a = probe.streams.find((s) => s.codec_type === "audio");
    if (
      !v ||
      v.width !== 1920 ||
      v.height !== 1080 ||
      v.r_frame_rate !== "30/1" ||
      v.codec_name !== "h264" ||
      !a ||
      a.codec_name !== "aac" ||
      Math.abs(Number(probe.format.duration) - timeline.duration_frames / 30) >
        0.1
    )
      throw Error("Media contract failed");
    execFileSync("ffmpeg", [
      "-v",
      "error",
      "-xerror",
      "-i",
      path.join(output, "lesson.mp4"),
      "-f",
      "null",
      "-",
    ]);
    await fs.unlink(sound);
    await fs.writeFile(
      path.join(output, "probe.json"),
      JSON.stringify(probe, null, 2),
    );
  }
  await fs.writeFile(
    path.join(output, "verification.json"),
    JSON.stringify(
      {
        renderer: "plain-javascript-canvas-v1",
        duration_sec: timeline.duration_sec,
        frames: [...frames].sort((a, b) => a - b),
        deterministic: true,
        effects_peak: mode === "full" ? "validated" : null,
        mode,
      },
      null,
      2,
    ),
  );
} finally {
  if (browser) await browser.close();
  server.close();
}
