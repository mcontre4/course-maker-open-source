import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

const tools = new URL("../", import.meta.url);
const source = `
window.explainer = ctx => ctx.fillRect(0, 0, 100, 100);
window.scoreSound = k => {};
window.cueEvents = [];
window.visualPlan = [{scene_id: 'scene-1', at_sec: 0,
  composition: 'Sun', continuity: 'hold', camera: 'fixed', objects: ['sun']}];
`;

async function fixture(t, style = "flat-vector-science", animation = source) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "canvas-render-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const project = path.join(root, "javascript");
  const output = path.join(root, "render");
  await fs.mkdir(project);
  await fs.cp(new URL("canvas-template/", tools), project, { recursive: true });
  await fs.cp(new URL(`styles/${style}/`, tools), path.join(project, "style"), {
    recursive: true,
  });
  await fs.mkdir(path.join(project, "fonts"));
  for (const [family, weight] of [["nunito", 900], ["nunito", 700], ["fredoka", 600],
    ["fredoka", 700], ["archivo-black", 400], ["space-mono", 400], ["space-mono", 700],
    ["bebas-neue", 400], ["oswald", 400], ["oswald", 700], ["rubik-mono-one", 400],
    ["space-grotesk", 400], ["space-grotesk", 700], ["syne", 800],
    ["inter", 400], ["inter", 600], ["inter", 800]]) {
    const name = `${family}-latin-${weight}-normal.woff2`;
    await fs.copyFile(
      new URL(`node_modules/@fontsource/${family}/files/${name}`, tools),
      path.join(project, "fonts", name),
    );
  }
  await fs.writeFile(path.join(project, "timeline.json"), JSON.stringify({
    duration_sec: 1, duration_frames: 30,
    scenes: [{scene_id: "scene-1", start_sec: 0, duration_sec: 1,
      start_frame: 0, duration_frames: 30, cues: [], audio: "voice.wav"}],
  }));
  await fs.writeFile(path.join(root, "inputs.json"), JSON.stringify({
    storyboard: {scenes: [{equations: []}]},
  }));
  await fs.writeFile(path.join(project, "animation.js"), animation);
  return { project, output };
}

async function render({ project, output }) {
  const child = spawn(process.execPath, [
    new URL("render-canvas.mjs", tools).pathname, project, output, "preview",
  ], { stdio: ["ignore", "pipe", "pipe"] });
  let stdout = "", stderr = "";
  child.stdout.on("data", data => { stdout += data; });
  child.stderr.on("data", data => { stderr += data; });
  const deadline = setTimeout(() => child.kill("SIGKILL"), 45000);
  try {
    const code = await new Promise((resolve, reject) => {
      child.once("error", reject);
      child.once("close", resolve);
    });
    return { code, stdout, stderr };
  } finally {
    clearTimeout(deadline);
  }
}

test("initializes the real player and captures deterministic frames", async t => {
  const files = await fixture(t);
  const result = await render(files);
  assert.equal(result.code, 0, result.stderr);
  const report = JSON.parse(await fs.readFile(path.join(files.output, "verification.json")));
  assert.equal(report.deterministic, true);
  assert.deepEqual(report.frames, [0, 29]);
});

for (const [style, drawing] of [
  ["swiss-grid", `
    const f = SWISS.frame(W,H_), c = f.c, grid = SWISS.grid();
    c.fillStyle = SWISS.BLACK; c.fillRect(0,0,64,64);
    SWISS.arcField(c,958,262,t+4);
    c.fillStyle = SWISS.BLACK; c.font = '800 100px "Inter"'; c.letterSpacing = '-4px';
    c.fillText('Typographic',grid.colX(0),570+t*30);
    c.font = '600 28px "Inter"'; c.letterSpacing = '0px'; c.fillText('CAUSE → FLOW',grid.colX(0),120);
    SWISS.rule(c,grid.colX(0),650,grid.colX(7),650,1,3,SWISS.RED);
    SWISS.columnWipe(c,W,H_,t);
    const before = c.getImageData(0,0,64,64).data;
    SWISS.composite(ctx,f,W,H_);
    const after = c.getImageData(0,0,64,64).data;
    if (!before.every((v,i)=>v===after[i])) throw new Error('Printing must preserve reusable source artwork');
  `],
  ["bauhaus", `
    if (BAUHAUS.exPaper(16,12).width !== 16 || BAUHAUS.exPaper(32,24).height !== 24) {
      throw new Error('Paper cache must respect dimensions');
    }
    const frame = BAUHAUS.plates(W,H_), c = frame.c, C = BAUHAUS.C;
    const other = BAUHAUS.plates(W,H_);
    if (frame.layers[0] === other.layers[0]) throw new Error('Frames must own independent plates');
    c.fillStyle = C.red; c.strokeStyle = C.red;
    c.save(); c.fillStyle = C.blue; c.strokeStyle = C.blue; c.fillRect(100,10,20,20); c.restore();
    c.fillRect(10,10,20,20); c.lineWidth = 4; c.strokeRect(50,10,20,20);
    const alpha = (i,x,y) => frame.layers[i].getContext('2d').getImageData(x,y,1,1).data[3];
    if (alpha(1,20,20) !== 255 || alpha(2,20,20) !== 0 || alpha(1,50,20) !== 255) {
      throw new Error('save/restore must restore fill and stroke plate routing');
    }
    c.fillStyle = C.cream; c.fillRect(14,14,4,4);
    if (frame.layers.some((_,i) => alpha(i,15,15) !== 0)) throw new Error('Cream must knock out all plates');
    c.fillStyle = C.yellow; c.beginPath(); c.arc(730+t*60,330,180,0,Math.PI*2); c.fill();
    c.fillStyle = C.blue; c.fillRect(320,220,250,250);
    BAUHAUS.exArrow(c,200,550,1000,550,1,14,C.black);
    BAUHAUS.exTag(c,'BAUHAUS',640,160,1,64);
    c.strokeStyle = C.red; c.lineWidth = 8; c.beginPath(); c.ellipse(760,330,210,205,0,0,Math.PI*2); c.stroke();
    BAUHAUS.composite(ctx,frame,W,H_);
  `],
  ["memphis", `
    const a = MEMPHIS.sceneGround(1,[MEMPHIS.PAL.pink,MEMPHIS.PAL.mint],W,H_);
    const b = MEMPHIS.sceneGround(1,[MEMPHIS.PAL.butter,MEMPHIS.PAL.lilac],W,H_);
    if (a === b) throw new Error('Different ground colours must not reuse a cached canvas');
    if (a !== MEMPHIS.sceneGround(1,[MEMPHIS.PAL.pink,MEMPHIS.PAL.mint],W,H_)) {
      throw new Error('Identical ground palettes should reuse their cached canvas');
    }
    const tq = MEMPHIS.celTime(t);
    MEMPHIS.background(ctx,W,H_,1);
    ctx.save(); ctx.translate(640+tq*40,330); ctx.rotate(-0.04);
    MEMPHIS.solid(ctx,MEMPHIS.bubble(760,280,[-150,210]),MEMPHIS.PAL.yellow,16,6);
    MEMPHIS.chunky(ctx,'MEMPHIS',0,0,80,MEMPHIS.PAL.blue); ctx.restore();
    MEMPHIS.tag(ctx,'PATTERN + MOTION',640,540,MEMPHIS.PAL.cream,32);
    MEMPHIS.fatArrow(ctx,220,570,450,570,1,MEMPHIS.PAL.teal);
    MEMPHIS.strokeOutlined(ctx,MEMPHIS.zigzagPath(880,580,230,14,8,0),MEMPHIS.PAL.magenta,10);
    MEMPHIS.bandSwipe(ctx,W,H_,tq);
  `],
  ["risograph", `
    const plates = RISO.plates(W,H_,t);
    for (const p of plates) {
      p.ctx.fillStyle = p.k === 'yellow' ? '#000' : 'rgba(0,0,0,0.5)';
      p.ctx.fillRect(100+t*100,160,600,340);
      RISO.T(p.ctx,'PRINT','400 64px "Archivo Black"',120,260);
      RISO.arrowQ(p.ctx,[120,400],[440,300],[900,400],1,8,[8,12]);
    }
    RISO.composite(ctx,plates,W,H_,t);
  `],
  ["gouache-poster", `
    const f = GP.frame(W,H_);
    f.paint(GP.PAL.teal,[60,80,900,600],c=>c.fillRect(100+t*100,160,600,340));
    f.paint(GP.PAL.orange,[100,160,850,500],c=>{
      c.font='400 96px "Bebas Neue"'; c.fillText('PAINT',200,360);
    },{dir:'v',p:0.8});
    f.commit(ctx);
  `],
  ["soft-3d", `
    CLAY.background(ctx,W,H_,t);
    CLAY.contactShadow(ctx,600,540,160,24,0.3,16);
    CLAY.clay(ctx,CLAY.rrect(300,220,50),[-150,-110,150,110],600+t*100,340,CLAY.PAL.lav);
    CLAY.clayLabel(ctx,600,320,'CLAY',CLAY.PAL.butter,{font:'700 64px "Fredoka"'});
    CLAY.clayTube(ctx,[100,400],[260,200],[420,400],1,CLAY.PAL.mint,20);
  `],
]) {
  test(`${style} renders its real helpers, local fonts and surface finish with deterministic seeks`, async t => {
    const files = await fixture(t, style, source + `
      window.explainer = (ctx,W,H_,t) => { ${drawing} };
    `);
    const result = await render(files);
    assert.equal(result.code, 0, result.stderr);
    const report = JSON.parse(await fs.readFile(path.join(files.output, "verification.json")));
    assert.equal(report.deterministic, true);
    assert.deepEqual(report.frames, [0,29]);
  });
}

test("reports undefined first-frame helpers instead of a startup timeout", async t => {
  const files = await fixture(t);
  await fs.writeFile(path.join(files.project, "animation.js"),
    source + "\nwindow.explainer = ctx => drawSun(ctx);");
  const result = await render(files);
  assert.equal(result.code, 1);
  assert.match(result.stderr, /Canvas player initialization failed/);
  assert.match(result.stderr, /drawSun is not defined/);
  assert.match(result.stderr, /animation\.js:\d+:\d+/);
  assert.doesNotMatch(result.stderr, /Timeout 30000ms exceeded/);
});

test("reports top-level animation errors", async t => {
  const files = await fixture(t);
  await fs.writeFile(path.join(files.project, "animation.js"),
    "throw new Error('broken animation initialization');\n" + source);
  const result = await render(files);
  assert.equal(result.code, 1);
  assert.match(result.stderr, /Canvas player initialization failed.*broken animation initialization/);
});

test("reports rejected local font loading with the failed resource", async t => {
  const files = await fixture(t);
  await fs.unlink(path.join(files.project, "fonts/nunito-latin-900-normal.woff2"));
  const result = await render(files);
  assert.equal(result.code, 1);
  assert.match(result.stderr, /Canvas player initialization failed/);
  assert.match(result.stderr, /nunito-latin-900-normal\.woff2: HTTP 404/);
  assert.doesNotMatch(result.stderr, /Timeout 30000ms exceeded/);
});

test("bounds missing-player startup and includes HTTP diagnostics", async t => {
  const files = await fixture(t);
  await fs.unlink(path.join(files.project, "player.js"));
  const result = await render(files);
  assert.equal(result.code, 1);
  assert.match(result.stderr, /Canvas player initialization failed/);
  assert.match(result.stderr, /Timeout 30000ms exceeded/);
  assert.match(result.stderr, /player\.js: HTTP 404/);
});
