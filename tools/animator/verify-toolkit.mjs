// Developer-only offline browser smoke test, separate from the production worker.
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {bundle} from '@remotion/bundler';
import {enableSkia} from '@remotion/skia/enable';
import {openBrowser, selectComposition, renderStill} from '@remotion/renderer';
const runtime = path.dirname(new URL(import.meta.url).pathname);
const output = process.argv[2];
if (!output) throw new Error('Usage: node verify-toolkit.mjs OUTPUT');
await fs.mkdir(output, {recursive: true});
const project = await fs.mkdtemp(path.join(os.tmpdir(), 'toolkit-browser-'));
let browser;
try {
  await fs.cp(path.join(runtime, 'template'), project, {recursive: true, filter: source => !source.split(path.sep).includes('node_modules')});
  await fs.mkdir(path.join(project, 'src/scenes'), {recursive: true});
  await fs.copyFile(path.join(runtime, 'tests/fixtures/toolkit.tsx'), path.join(project, 'src/scenes/s01.tsx'));
  await fs.writeFile(path.join(project, 'src/Root.tsx'), `import React from 'react';
import {Composition} from 'remotion';
import Toolkit from './scenes/s01';
export const Root = () => <Composition id="Toolkit" component={Toolkit} width={1920} height={1080} fps={30} durationInFrames={90}/>;`);
  await fs.mkdir(path.join(project, 'public/skia'), {recursive: true});
  await fs.copyFile(path.join(runtime, 'node_modules/canvaskit-wasm/bin/full/canvaskit.wasm'), path.join(project, 'public/skia/canvaskit.wasm'));
  const serveUrl = await bundle({entryPoint: path.join(project, 'src/index.ts'), publicDir: path.join(project, 'public'), enableCaching: false,
    webpackOverride: config => enableSkia({...config, cache: false, resolve: {...config.resolve, modules: [path.join(runtime, 'node_modules'), ...(config.resolve?.modules ?? [])],
    alias: {...config.resolve?.alias, 'react-native$': 'react-native-web'}}})});
  browser = await openBrowser('chrome', {browserExecutable: process.env.REMOTION_BROWSER_EXECUTABLE, chromiumOptions: {gl: 'swangle'}});
  const composition = await selectComposition({serveUrl, id: 'Toolkit', puppeteerInstance: browser});
  for (const [index, frame] of [10, 60, 10].entries()) {
    await renderStill({serveUrl, composition, frame, output: path.join(output, `${index}-${frame}.png`), puppeteerInstance: browser,
      chromiumOptions: {gl: 'swangle'}, onBrowserLog: log => {if (log.type === 'error') throw new Error(log.text);}});
  }
  assert.deepEqual(await fs.readFile(path.join(output, '0-10.png')), await fs.readFile(path.join(output, '2-10.png')), 'Repeated out-of-order frame must match');
  assert.notDeepEqual(await fs.readFile(path.join(output, '0-10.png')), await fs.readFile(path.join(output, '1-60.png')), 'Frame-driven geometry must change');
  await fs.writeFile(path.join(output, 'verification.json'), JSON.stringify({offline: true, frames: [10, 60, 10], deterministic: true}, null, 2));
  console.log('Offline toolkit rendering and deterministic seeking passed');
} finally {
  await browser?.close({silent: true});
  await fs.rm(project, {recursive: true, force: true});
}
