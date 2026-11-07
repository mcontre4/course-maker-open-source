// Real offline WASM/Remotion integration check; takes a locally compiled probe .riv.
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
const require = createRequire('/opt/animator/package.json');
const {bundle} = require('@remotion/bundler');
const {openBrowser, selectComposition, renderStill} = require('@remotion/renderer');
const [binary, output, helper] = process.argv.slice(2);
if (!helper) throw new Error('Usage: verify-rive.mjs PROBE.riv OUTPUT_DIRECTORY RiveIllustration.tsx');
const project = await fs.mkdtemp(path.join(os.tmpdir(), 'rive-motion-'));
await fs.mkdir(path.join(project, 'public/illustrations'), {recursive: true});
await fs.mkdir(path.join(project, 'public/rive'), {recursive: true});
await fs.mkdir(output, {recursive: true});
await fs.copyFile(binary, path.join(project, 'public/illustrations/probe.riv'));
await fs.copyFile(require.resolve('@rive-app/canvas-advanced/rive.wasm'), path.join(project, 'public/rive/rive.wasm'));
await fs.copyFile(helper, path.join(project, 'RiveIllustration.tsx'));
await fs.writeFile(path.join(project, 'index.tsx'), `
import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {RiveIllustration} from './RiveIllustration';
const Scene = () => <RiveIllustration asset="probe" animation="Explain" width={600} height={400}/>;
registerRoot(() => <Composition id="Probe" component={Scene} width={600} height={400} fps={30} durationInFrames={61}/>);
`);
const serveUrl = await bundle({entryPoint: path.join(project, 'index.tsx'), publicDir: path.join(project, 'public'),
  enableCaching: false, webpackOverride: c => ({...c, resolve: {...c.resolve, modules: ['/opt/animator/node_modules']}})});
const browser = await openBrowser('chrome', {browserExecutable: process.env.REMOTION_BROWSER_EXECUTABLE});
try {
  const composition = await selectComposition({serveUrl, id: 'Probe', puppeteerInstance: browser});
  for (const [index, frame] of [0, 30, 15, 0].entries()) {
    await renderStill({serveUrl, composition, puppeteerInstance: browser, frame,
      output: path.join(output, `probe-${index}.png`)});
  }
  const images = await Promise.all([0,1,2,3].map(i => fs.readFile(path.join(output, `probe-${i}.png`))));
  if (!images[0].equals(images[3])) throw new Error('Out-of-order Rive seeking changed the same frame');
  if (images[0].equals(images[1]) || images[1].equals(images[2])) throw new Error('Rive motion did not advance');
  console.log('Offline Rive motion and repeated out-of-order frames verified');
} finally {await browser.close({silent: true}); await fs.rm(project, {recursive: true, force: true});}
