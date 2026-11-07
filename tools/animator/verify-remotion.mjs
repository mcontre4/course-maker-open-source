// Developer-only QA. The backend never imports or invokes this renderer.
import fs from 'node:fs/promises';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {enableSkia} from '@remotion/skia/enable';
import {selectComposition, renderStill, renderMedia, openBrowser} from '@remotion/renderer';

const project = path.resolve(process.argv[2]);
const output = path.resolve(process.argv[3]);
if (!project || !process.argv[3]) throw new Error('Usage: node verify-remotion.mjs PROJECT REVIEW_DIRECTORY [--video]');
if (output.startsWith(project + path.sep)) throw new Error('Review output must be outside the source project');
await fs.mkdir(output, {recursive: true});
const timeline = JSON.parse(await fs.readFile(path.join(project, 'src/timeline.json')));
const manifest = JSON.parse(await fs.readFile(path.join(project, 'scene-manifest.json')));
const runtime = path.dirname(new URL(import.meta.url).pathname);
const serveUrl = await bundle({
  entryPoint: path.join(project, 'src/index.ts'),
  enableCaching: false,
  publicDir: path.join(project, 'public'),
  webpackOverride: config => enableSkia({...config, cache: false, resolve: {...config.resolve,
    modules: [path.join(runtime, 'node_modules'), ...(config.resolve?.modules ?? [])],
    alias: {...config.resolve?.alias, 'react-native$': 'react-native-web'}}}),
});
const browser = await openBrowser('chrome', {
  browserExecutable: process.env.REMOTION_BROWSER_EXECUTABLE || undefined,
});
try {
  const composition = await selectComposition({serveUrl, id: 'Course', puppeteerInstance: browser});
  if (composition.fps !== 30 || composition.width !== 1920 || composition.height !== 1080 ||
      composition.durationInFrames !== timeline.duration_frames) throw new Error('Composition metadata mismatch');
  const frames = new Set([0, timeline.duration_frames - 1]);
  for (const scene of timeline.scenes) {
    frames.add(scene.start_frame);
    frames.add(Math.min(timeline.duration_frames - 1, scene.start_frame + scene.duration_frames - 1));
    frames.add(Math.min(timeline.duration_frames - 1, scene.start_frame + (scene.visual_duration_frames ?? scene.duration_frames) - 1));
    for (const cue of scene.cues) {
      for (const offset of [-1, 0, 15, 45]) {
        frames.add(Math.min(timeline.duration_frames - 1, Math.max(0, cue.absolute_start_frame + offset)));
      }
    }
  }
  for (const scene of manifest.scenes) {
    for (const event of (scene.supplemental_word_events ?? [])) {
      for (const offset of [-1, 0, 15, 45]) {
        frames.add(Math.min(timeline.duration_frames - 1, Math.max(0, event.absolute_start_frame + offset)));
      }
    }
  }
  const sorted = [...frames].sort((a,b) => a-b);
  for (const frame of sorted) {
    await renderStill({composition, serveUrl, puppeteerInstance: browser,
      frame, output: path.join(output, `frame-${String(frame).padStart(6, '0')}.png`)});
    console.log(`frame ${frame}/${timeline.duration_frames}`);
  }
  // Render in reverse order to prove representative frames are independently seekable.
  const seekFrames = timeline.scenes.map(s => Math.min(timeline.duration_frames - 1,
    s.start_frame + Math.floor(s.duration_frames / 2))).reverse();
  for (const frame of seekFrames) {
    const first = path.join(output, `seek-${frame}-a.png`);
    const second = path.join(output, `seek-${frame}-b.png`);
    await renderStill({composition, serveUrl, puppeteerInstance: browser, frame, output: first});
    await renderStill({composition, serveUrl, puppeteerInstance: browser, frame: 0,
      output: path.join(output, 'seek-reset.png')});
    await renderStill({composition, serveUrl, puppeteerInstance: browser, frame, output: second});
    if (!(await fs.readFile(first)).equals(await fs.readFile(second))) throw new Error(`Non-deterministic seek at frame ${frame}`);
  }
  const gapHolds = [];
  for (const scene of timeline.scenes) {
    if (scene.visual_duration_frames > scene.duration_frames) {
      const last = scene.start_frame + scene.duration_frames - 1;
      const held = scene.start_frame + scene.visual_duration_frames - 1;
      const a = await fs.readFile(path.join(output, `frame-${String(last).padStart(6, '0')}.png`));
      const b = await fs.readFile(path.join(output, `frame-${String(held).padStart(6, '0')}.png`));
      if (!a.equals(b)) throw new Error(`Scene ${scene.scene_id} does not hold its final visual through silence`);
      gapHolds.push({scene_id: scene.scene_id, last, held});
    }
  }
  if (process.argv.includes('--video')) {
    let last = -1;
    await renderMedia({composition, serveUrl, puppeteerInstance: browser, codec: 'h264',
      outputLocation: path.join(output, 'lesson.mp4'), concurrency: 2,
      onProgress: ({progress}) => {
        const percent = Math.floor(progress * 100);
        if (percent >= last + 5) {console.log(`video ${percent}%`); last = percent;}
      }});
  }
  await fs.writeFile(path.join(output, 'verification.json'), JSON.stringify({
    composition: {id: composition.id, fps: composition.fps, width: composition.width,
      height: composition.height, durationInFrames: composition.durationInFrames},
    renderedFrames: sorted, seekFrames, gapHolds, scenes: manifest.scenes.length,
    cues: manifest.scenes.reduce((n,s) => n+s.cues.length, 0),
    videoRendered: process.argv.includes('--video'),
    visualReview: 'Pending human/agent inspection of rendered frames; rendering alone is not visual QA',
  }, null, 2));
} finally {await browser.close({silent: true});}
