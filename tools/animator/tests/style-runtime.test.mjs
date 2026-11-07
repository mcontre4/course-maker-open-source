import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const root = new URL('../', import.meta.url);
const read = (name) => fs.readFileSync(new URL(name, root), 'utf8');
const loadStyle = (id) => {
  const context = vm.createContext({});
  context.window = context;
  vm.runInContext(read(`styles/${id}/harness.js`), context);
  vm.runInContext(read(`styles/${id}/drawing.js`), context);
  return context;
};

for (const id of ['risograph', 'gouache-poster', 'soft-3d', 'memphis', 'bauhaus', 'swiss-grid']) {
  test(`${id} preserves the uploaded helper library, sound kit and executable reference`, () => {
    const blocks = [...read(`styles/${id}/source-prompt.txt`).matchAll(/```js\n([\s\S]*?)\n```/g)];
    assert.equal(blocks.length, 3);
    for (const [i, name] of ['harness.js', 'sound.js', 'examples/reference-ai.js'].entries()) {
      assert.equal(read(`styles/${id}/${name}`), blocks[i][1] + '\n');
    }
  });
}

for (const id of ['flat-vector-science', 'watercolor-wash', 'tech-glow', 'whiteboard', 'halftone-pop', 'risograph', 'gouache-poster', 'soft-3d', 'memphis', 'bauhaus', 'swiss-grid']) {
  test(`${id} preloads its fonts and runs its finish on each seek`, async () => {
    const { STYLE } = loadStyle(id);
    const fonts = [], frames = [], order = [];
    const elements = Object.fromEntries(['canvas', '#scrub', '#clock', '#play', '#sound', '#loop']
      .map((key) => [key, {}]));
    const ctx = { resetTransform() {}, clearRect() {}, save() {}, restore() {} };
    elements.canvas.getContext = () => ctx;
    const context = vm.createContext({
      fetch: async () => ({ json: async () => ({ duration_sec: 10, scenes: [] }) }),
      document: { querySelector: (key) => elements[key], fonts: { load: async (spec) => fonts.push(spec) } },
      STYLE: { fonts: STYLE.fonts, beginFrame: () => order.push("begin"), finish: (...args) => { frames.push(args); order.push("finish"); } },
      H: { clamp: (t, lo, hi) => Math.max(lo, Math.min(hi, t)) },
      explainer() { order.push("draw"); }, requestAnimationFrame() {},
    });
    context.window = context;
    vm.runInContext(read('canvas-template/player.js'), context);
    await context.ready;
    context.seek(3);
    context.seek(20);
    assert.deepEqual(fonts, Array.from(STYLE.fonts));
    assert.deepEqual(frames.map((args) => args.slice(1)), [[1280, 720, 0], [1280, 720, 3], [1280, 720, 10]]);
    assert.deepEqual(order, ["begin", "draw", "finish", "begin", "draw", "finish", "begin", "draw", "finish"]);
    assert.equal(context.DURATION, 10);
  });
}

test('Swiss noise fields and dropout masks remain deterministic across cache changes', () => {
  const { SWISS } = loadStyle('swiss-grid');
  const first = SWISS.exField('ink', 16, 12, 3, 3, 2);
  assert.equal(SWISS.exField('ink', 16, 12, 3, 3, 2), first);
  assert.notDeepEqual(SWISS.exField('ink', 16, 12, 8, 3, 2), first);
  assert.notDeepEqual(SWISS.exField('ink', 16, 12, 3, 3, 2, 3, 0.6), first);
  assert.equal(SWISS.exField('ink', 20, 14, 3, 3, 2).length, 280);
  assert.equal(SWISS.exField('ink', 16, 12, 3, 3, 2), first);
  const mask = SWISS.speckMask(3,4);
  assert.equal(mask.length, 12);
  assert.ok(mask.every(v => Number.isFinite(v) && v >= 0 && v <= 0.85));
  assert.equal(SWISS.speckMask(3,4), mask);
  assert.equal(SWISS.speckMask(20,14).length, 280);
});

test('Bauhaus noise caches respect dimensions and every field parameter', () => {
  const { BAUHAUS } = loadStyle('bauhaus');
  const first = BAUHAUS.cachedField('ink', 16, 12, 21, 5, 3);
  assert.equal(BAUHAUS.cachedField('ink', 16, 12, 21, 5, 3), first);
  const resized = BAUHAUS.cachedField('ink', 20, 14, 21, 5, 3);
  assert.equal(resized.length, 280);
  assert.notEqual(resized, first);
  const reseeded = BAUHAUS.cachedField('ink', 16, 12, 22, 5, 3);
  assert.notDeepEqual(reseeded, first);
  assert.equal(BAUHAUS.cachedField('ink', 16, 12, 21, 5, 3), first);
});

test('Memphis quantizes cel motion and preserves the full animated monochrome grain', () => {
  const { MEMPHIS, STYLE } = loadStyle('memphis');
  assert.equal(MEMPHIS.celTime(1.01), 1);
  assert.equal(MEMPHIS.celTime(1.09), 13 / 12);
  const finish = t => {
    const data = new Uint8ClampedArray(16 * 12 * 4).fill(180);
    STYLE.finish({ canvas: { width: 16, height: 12 },
      getImageData: () => ({ data }), putImageData() {} },16,12,t);
    return data;
  };
  assert.deepEqual(finish(1),finish(1.01));
  assert.notDeepEqual(finish(1),finish(1.09));
  const pixels = finish(1);
  assert.ok(pixels.some(v=>v!==180));
  for (let i=0;i<pixels.length;i+=4) {
    assert.equal(pixels[i],pixels[i+1]);
    assert.equal(pixels[i],pixels[i+2]);
    assert.equal(pixels[i+3],180);
  }
});

test('watercolor helpers and the full paper pass are deterministic', () => {
  const { WC, H } = loadStyle('watercolor-wash');
  const points = () => WC.deform(WC.circlePts(8, 6, 4, 3, 8, H.rng(4)), H.rng(5), 3, 0.14);
  assert.deepEqual(points(), points());
  const render = () => {
    const data = new Uint8ClampedArray(16 * 12 * 4).fill(180);
    WC.finish({ getImageData: () => ({ data }), putImageData() {} }, 16, 12, 3);
    return data;
  };
  assert.deepEqual(render(), render());
  assert.ok(render().some((value) => value !== 180));
});

test('tech glow preserves connector geometry and both bloom layers on every frame', () => {
  const draws = [], stops = [];
  const makeCanvas = () => {
    const canvas = { width: 1280, height: 720 };
    const ctx = { canvas, save() {}, restore() {}, setTransform() {},
      drawImage(...args) { draws.push({ alpha: this.globalAlpha, mode: this.globalCompositeOperation, args }); },
      createRadialGradient() { return { addColorStop: (...args) => stops.push(args) }; }, fillRect() {} };
    canvas.getContext = () => ctx;
    return canvas;
  };
  const context = vm.createContext({ document: { createElement: makeCanvas } });
  context.window = context;
  vm.runInContext(read('styles/tech-glow/harness.js'), context);
  vm.runInContext(read('styles/tech-glow/drawing.js'), context);
  const { TG, STYLE } = context;
  const curve = TG.bez(0, 0, 20, 0, 80, 100, 100, 100);
  assert.equal(TG.ptAt(curve, 0).x, 0);
  assert.equal(TG.ptAt(curve, 1).x, 100);
  assert.equal(TG.ptAt(curve, 1).y, 100);
  const canvas = makeCanvas();
  STYLE.finish(canvas.getContext(), 1280, 720, 2);
  STYLE.finish(canvas.getContext(), 1280, 720, 2);
  assert.deepEqual(draws.filter((d) => d.mode === 'lighter').map((d) => d.alpha), [.45, .5, .45, .5]);
  assert.deepEqual(stops.filter(([offset]) => offset === 1), [[1, 'rgba(2,3,16,0.45)'], [1, 'rgba(2,3,16,0.45)']]);
});

test('whiteboard resets marker-tip tracking and retains deterministic marker strokes and grain', () => {
  const { WB, STYLE } = loadStyle('whiteboard');
  const strokes = [];
  const gradient = () => ({ addColorStop() {} });
  const ctx = { save() {}, restore() {}, beginPath() {}, moveTo() {}, lineTo() {}, arc() {}, fill() {},
    stroke() { strokes.push([this.strokeStyle, this.lineWidth]); }, createRadialGradient: gradient };
  const points = WB.seg([[0, 0], [30, 20]]);
  const draw = () => {
    STYLE.beginFrame();
    assert.equal(WB.tip(), null);
    strokes.length = 0;
    WB.marker(ctx, points, '#1f4fc2', 7, 101, .5);
    return JSON.stringify(strokes);
  };
  const first = draw();
  assert.ok(WB.tip());
  assert.equal(draw(), first);
  STYLE.beginFrame();
  assert.equal(WB.tip(), null);
  const finish = (t) => {
    const data = new Uint8ClampedArray(16 * 12 * 4).fill(180);
    STYLE.finish({ canvas: { width: 16, height: 12 }, save() {}, restore() {}, translate() {}, scale() {},
      createLinearGradient: gradient, createRadialGradient: gradient, fillRect() {}, beginPath() {}, arc() {}, fill() {},
      getImageData: () => ({ data }), putImageData() {} }, 16, 12, t);
    return data;
  };
  assert.deepEqual(finish(2), finish(2));
  assert.notDeepEqual(finish(2), finish(2.1));
});

test('halftone preserves staggered dots, plate misregistration and deterministic paper ageing', () => {
  const makeCanvas = () => {
    const canvas = { width: 16, height: 12 };
    const ctx = { canvas, fillRect() {}, drawImage() {},
      createImageData: (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) }), putImageData() {},
      getImageData: (x, y, w, h) => ({ data: new Uint8ClampedArray(w * h * 4).fill(128) }) };
    canvas.getContext = () => ctx;
    return canvas;
  };
  const context = vm.createContext({ document: { createElement: makeCanvas } });
  context.window = context;
  vm.runInContext(read('styles/halftone-pop/harness.js'), context);
  vm.runInContext(read('styles/halftone-pop/drawing.js'), context);
  const { HP, STYLE } = context;
  const dots = [];
  const drawDots = () => {
    dots.length = 0;
    HP.benday({ beginPath() {}, moveTo() {}, arc: (...args) => dots.push(args), fill() {} },
      HP.C.red, 16, 3.7, 0, 0, 32, 32, 8);
    return JSON.stringify(dots);
  };
  assert.equal(drawDots(), drawDots());
  assert.ok(dots.length > 0);
  const plates = HP.plates(16, 12), draws = [];
  const ctx = { fillRect() {}, drawImage(...args) { draws.push([this.globalCompositeOperation, ...args]); } };
  HP.composite(ctx, plates.col, plates.key, 16, 12);
  assert.equal(draws[0][1], plates.col);
  assert.deepEqual(draws[0].slice(2), [2.5, -1.5]);
  assert.equal(draws[1][0], 'multiply');
  assert.equal(draws[1][1], plates.key);
  assert.equal(ctx.globalCompositeOperation, 'source-over');
  const finish = () => {
    const data = new Uint8ClampedArray(16 * 12 * 4).fill(180);
    STYLE.finish({ getImageData: () => ({ data }), putImageData() {} }, 16, 12, 3);
    return data;
  };
  assert.deepEqual(finish(), finish());
  assert.ok(finish().some((value) => value !== 180));
  assert.ok(finish()[2] < finish()[0]);
});
