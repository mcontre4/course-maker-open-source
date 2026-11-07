import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const runtime = path.resolve(import.meta.dirname, '..');
const base = 'import React from "react"; export default () => <div data-cue-id="c1">{ "F = ma" }</div>;';
async function fixture() {
  const job = await fs.mkdtemp(path.join(os.tmpdir(), 'remotion-static-'));
  const project = path.join(job, 'remotion');
  await fs.mkdir(path.join(project, 'src/scenes'), {recursive: true});
  await fs.mkdir(path.join(job, 'inputs'));
  await fs.copyFile(path.join(runtime, 'template/tsconfig.json'), path.join(project, 'tsconfig.json'));
  await fs.copyFile(path.join(runtime, 'template/src/remotion-env.d.ts'), path.join(project, 'src/remotion-env.d.ts'));
  await fs.writeFile(path.join(job, 'inputs/storyboard.json'), JSON.stringify({scenes:[{scene_id:'s01',equations:['F = ma']}]}));
  await fs.writeFile(path.join(project, 'src/timeline.json'), JSON.stringify({scenes:[{scene_id:'s01',cues:[{cue_id:'c1'}]}]}));
  return {job, project, source: path.join(project, 'src/scenes/s01.tsx')};
}
function check(project) {return spawnSync(process.execPath, [path.join(runtime, 'validate-project.mjs'), project], {encoding:'utf8'});}
test('real TypeScript boundary validates JSX equations, cue anchors, types and deterministic motion', async () => {
  const {job, project, source} = await fixture();
  try {
    await fs.writeFile(source, base);
    const baseline = check(project);
    assert.equal(baseline.status, 0, baseline.stderr);
    const cases = [
      [base.replace('F = ma', 'wrong') + '\nconst ApprovedEquation = ({verbatim}: {verbatim: string}) => null; const Fake = () => <ApprovedEquation verbatim="F = ma"/>;', /Missing visible equation/],
      [base + '\nimport {timer as clock} from "d3";', /Library clock/],
      [base + '\nconst load = () => import("react");', /nondeterministic/],
      [base + '\nconst style = {transition: "opacity 1s"};', /CSS animation/],
      [base + '\nconst x = Math.random();', /nondeterministic/],
      [base + '\nconst x = Date.now();', /nondeterministic/],
      [base + '\nfetch("\/data");', /network/],
      [base + '\nconst x: number = "wrong";', /not assignable/],
      [base.replace('F = ma', 'wrong') + '\nconst hidden = "F = ma";', /equation/],
      [base.replace('data-cue-id="c1"','data-cue-id="wrong"'), /Missing visible cue/],
      [base + '\nimport fs from "node:fs";', /Unsupported external/],
      [base + '\nconst style = {animation: "spin 2s"};', /CSS animation/],
      ['// @ts-nocheck\n' + base + '\nconst x: number = "wrong";', /suppression/],
      [base + '\n// @ts-expect-error\nconst x: number = "wrong";', /suppression/],
      [base + '\nconst Style = () => <style>{"@keyframes spin {to {opacity: 0}}"}</style>;', /Inline CSS/],
      [base + '\nconst Image = () => <img src={"https://example.com/image.png"}/>;', /Nonlocal asset/],
      [base + '\nwindow.setTimeout(() => {}, 100);', /nondeterministic/],
      [base + '\nimport {useState} from "react"; const State = () => useState(0);', /Mutable animation state/],
    ];
    for (const [content, error] of cases) {
      await fs.writeFile(source, content);
      const result = check(project);
      assert.equal(result.status, 1);
      assert.match(result.stderr, error);
    }
    await fs.writeFile(source, base + '\nconst Teaching = () => <pre>{"// @ts-nocheck https://example.com"}</pre>;');
    const teaching = check(project);
    assert.equal(teaching.status, 0, teaching.stderr);
  } finally {await fs.rm(job, {recursive:true, force:true});}
});

test('preinstalled Remotion and optional Three stack typecheck without skipped library checks', async () => {
  const {job, project, source} = await fixture();
  try {
    await fs.writeFile(source, `import React from 'react';
import {useCurrentFrame, spring} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {Vector3} from 'three';
const position = new Vector3(0, 0, 0);
export default () => {const frame = useCurrentFrame();
return <div data-cue-id="c1">{'F = ma'}{frame}{position.x}
<ThreeCanvas width={1920} height={1080}><ambientLight intensity={1}/></ThreeCanvas></div>;};`);
    const result = check(project);
    assert.equal(result.status, 0, result.stderr);
  } finally {await fs.rm(job, {recursive:true, force:true});}
});

test('the full visual toolkit and offline Skia bootstrap typecheck together', async () => {
  const {job, project, source} = await fixture();
  try {
    await fs.cp(path.join(runtime, 'template/src'), path.join(project, 'src'), {recursive: true});
    await fs.cp(path.join(runtime, 'template/types'), path.join(project, 'types'), {recursive: true});
    await fs.writeFile(path.join(project, 'src/Root.tsx'), 'export const Root = () => null;');
    await fs.copyFile(path.join(runtime, 'tests/fixtures/toolkit.tsx'), source);
    const result = check(project);
    assert.equal(result.status, 0, result.stderr);
  } finally {await fs.rm(job, {recursive:true, force:true});}
});

test('worker and editable project share the exact visual dependency graph', async () => {
  const worker = JSON.parse(await fs.readFile(path.join(runtime, 'package-lock.json'), 'utf8'));
  const template = JSON.parse(await fs.readFile(path.join(runtime, 'template/package-lock.json'), 'utf8'));
  const expected = Object.keys(worker.packages).filter(name => name);
  assert.deepEqual(Object.keys(template.packages).filter(Boolean).sort(), expected.sort());
  for (const name of expected) assert.deepEqual(template.packages[name], worker.packages[name], name);
  assert.equal(template.packages[''].dependencies['@openai/codex'], undefined);
});
