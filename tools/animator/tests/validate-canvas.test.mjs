import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

const validator = new URL("../validate-canvas.mjs", import.meta.url).pathname;
const base =
  "window.explainer=(ctx,W,H,t)=>{ctx.fillText('React is a lesson topic',20,20);};window.scoreSound=k=>{};window.visualPlan=[];window.cueEvents=[];";
function validate(t, source, styleId) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "canvas-source-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  fs.writeFileSync(path.join(dir, "animation.js"), source);
  if (styleId) {
    fs.mkdirSync(path.join(dir, "style"));
    fs.copyFileSync(new URL(`../styles/${styleId}/drawing.js`, import.meta.url),
      path.join(dir, "style/drawing.js"));
  }
  return spawnSync(process.execPath, [validator, dir], { encoding: "utf8" });
}
test("accepts plain drawing and framework names as teaching text", (t) => {
  assert.equal(validate(t, base).status, 0);
});
for (const code of [
  "Math.random()",
  "Date.now()",
  'fetch("https://example.com")',
  "requestAnimationFrame(()=>{})",
  'React.createElement("div")',
]) {
  test("rejects runtime dependency: " + code, (t) => {
    assert.notEqual(validate(t, base + "\n" + code).status, 0);
  });
}
test("requires explicit cue events", (t) => {
  assert.notEqual(
    validate(t, base.replace("window.cueEvents=[];", "")).status,
    0,
  );
});
test("rejects module/framework scene authoring", (t) => {
  assert.notEqual(validate(t, "import React from 'react';\n" + base).status, 0);
});

test("rejects an undefined drawing helper with its source location", (t) => {
  const result = validate(t, base + "\nwindow.explainer = ctx => drawSun(ctx);");
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /animation\.js:2:\d+: Cannot find name 'drawSun'/);
});

test("checks helper names in later scenes too", (t) => {
  const result = validate(t, base + "\nfunction laterScene(ctx) { drawRain(ctx); }");
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Cannot find name 'drawRain'/);
});

test("accepts helpers exposed as classic browser globals", (t) => {
  const result = validate(t, base + `
    window.drawSun = ctx => ctx.fillRect(0, 0, 10, 10);
    globalThis.drawRain = ctx => ctx.fillRect(0, 0, 5, 5);
    window['drawCloud'] = ctx => ctx.fillRect(0, 0, 20, 20);
    window.explainer = ctx => { drawSun(ctx); drawRain(ctx); drawCloud(ctx); };
  `);
  assert.equal(result.status, 0, result.stderr);
});

test("rejects helper typos even when the compiler suggests a known helper", (t) => {
  const result = validate(t, base + `
    function drawSun(ctx) { ctx.fillRect(0, 0, 10, 10); }
    window.explainer = ctx => drawSunn(ctx);
  `);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Cannot find name 'drawSunn'/);
});

test("rejects undefined shorthand properties", (t) => {
  const result = validate(t, base + "\nwindow.data = { sunPosition };");
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /No value exists in scope for the shorthand property 'sunPosition'/);
});

test("accepts declared helpers, scoped arguments and bundled browser globals", (t) => {
  const result = validate(t, base + `
    function drawSun(ctx) { ctx.fillRect(0, 0, 10, 10); }
    window.explainer = (ctx, W, H_, t) => {
      const point = { x: Math.cos(t), y: H.clamp(t, 0, 1) };
      drawSun(ctx);
      FV.ball(ctx, point.x, point.y, W / H_);
      window.customData = new Float32Array(2);
      document.querySelector('canvas');
      return SOUND;
    };
  `);
  assert.equal(result.status, 0, result.stderr);
});

for (const [id, helper] of [
  ["flat-vector-science", "FV"], ["watercolor-wash", "WC"], ["tech-glow", "TG"],
  ["whiteboard", "WB"], ["halftone-pop", "HP"],
  ["risograph", "RISO"], ["gouache-poster", "GP"], ["soft-3d", "CLAY"], ["memphis", "MEMPHIS"], ["bauhaus", "BAUHAUS"], ["swiss-grid", "SWISS"],
]) {
  test(`accepts the ${id} helper and rejects another style's helper`, (t) => {
    const accepted = validate(t, base + `\nwindow.explainer=()=>${helper};`, id);
    assert.equal(accepted.status, 0, accepted.stderr);
    const missing = helper === "FV" ? "WC" : "FV";
    const rejected = validate(t, base + `\nwindow.explainer=()=>${missing};`, id);
    assert.notEqual(rejected.status, 0);
    assert.match(rejected.stderr, new RegExp("Cannot find name '" + missing + "'"));
  });
}
