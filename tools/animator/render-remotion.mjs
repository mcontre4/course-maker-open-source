// Runs only inside the offline server renderer container. No provider credentials.
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {enableSkia} from '@remotion/skia/enable';
import {openBrowser, selectComposition, renderMedia} from '@remotion/renderer';

const [projectArg, outputArg, concurrencyArg = '2'] = process.argv.slice(2);
if (!projectArg || !outputArg) throw new Error('Usage: render-video.mjs PROJECT OUTPUT [CONCURRENCY]');
const project = path.resolve(projectArg);
const output = path.resolve(outputArg);
const concurrency = Number(concurrencyArg);
if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 8) throw new Error('Invalid concurrency');
const timeline = JSON.parse(await fs.readFile(path.join(project, 'src/timeline.json')));
const runtime = path.dirname(new URL(import.meta.url).pathname);
const serveUrl = await bundle({
  entryPoint: path.join(project, 'src/index.ts'),
  outDir: '/tmp/remotion-bundle', enableCaching: false,
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
  if (composition.width !== 1920 || composition.height !== 1080 || composition.fps !== 30 ||
      composition.durationInFrames !== timeline.duration_frames) throw new Error('Composition metadata mismatch');
  await renderMedia({serveUrl, composition, puppeteerInstance: browser,
    codec: 'h264', audioCodec: 'aac', pixelFormat: 'yuv420p',
    imageFormat: 'png', crf: 18, colorSpace: 'bt709',
    outputLocation: output, concurrency, overwrite: true,
    onProgress: ({progress}) => console.log(`render ${Math.floor(progress * 100)}%`),
  });
  const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_streams', '-show_format',
    '-of', 'json', output], {encoding: 'utf8'}));
  const video = probe.streams.find(s => s.codec_type === 'video');
  const audio = probe.streams.find(s => s.codec_type === 'audio');
  const duration = Number(probe.format.duration);
  if (!video || video.codec_name !== 'h264' || video.width !== 1920 || video.height !== 1080 ||
      !['yuv420p', 'yuvj420p'].includes(video.pix_fmt) || !audio || audio.codec_name !== 'aac' ||
      Math.abs(duration - composition.durationInFrames / 30) > 0.1) {
    console.error(JSON.stringify({duration, streams: probe.streams.map(s => ({
      type: s.codec_type, codec: s.codec_name, width: s.width, height: s.height, pixelFormat: s.pix_fmt,
    }))}));
    throw new Error('Invalid rendered media');
  }
  // Decode the complete file, including audio, before accepting it as a durable lesson video.
  execFileSync('ffmpeg', ['-v', 'error', '-xerror', '-i', output, '-f', 'null', '-']);
  await fs.writeFile(path.join(path.dirname(output), 'probe.json'), JSON.stringify({
    duration_sec: composition.durationInFrames / 30,
    duration_frames: composition.durationInFrames, width: video.width, height: video.height,
    fps: 30, video_codec: video.codec_name, audio_codec: audio.codec_name,
  }));
} finally {
  await browser.close({silent: true});
}
