// Helpers and cold-press finishing pass extracted unchanged from the supplied reference.
(function () {

  // ---------------------------------------------------------------
  // Watercolor — layered deformed-polygon washes on cold-press paper
  // ---------------------------------------------------------------
  const PAPER = [251, 248, 240];

  // recursive midpoint displacement; each vertex carries its own "wobble" weight v
  function deform(pts, r, depth, amt) {
    let p = pts;
    for (let d = 0; d < depth; d++) {
      const out = [];
      for (let i = 0; i < p.length; i++) {
        const a = p[i], b = p[(i + 1) % p.length];
        out.push(a);
        const len = Math.hypot(b.x - a.x, b.y - a.y);
        const v = (a.v + b.v) * 0.5;
        const s = len * amt * v;
        out.push({ x: (a.x + b.x) / 2 + r.gauss() * s, y: (a.y + b.y) / 2 + r.gauss() * s, v: v * (0.7 + r() * 0.6) });
      }
      p = out;
    }
    return p;
  }
  function poly(c, pts) {
    c.beginPath(); c.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) c.lineTo(pts[i].x, pts[i].y);
    c.closePath();
  }
  const P = (x, y, v = 1) => ({ x, y, v });
  function circlePts(cx, cy, rx, ry, n, r, vv = 1, a0 = 0, a1 = Math.PI * 2) {
    const out = [];
    for (let i = 0; i < n; i++) { const a = a0 + (a1 - a0) * i / n; out.push(P(cx + Math.cos(a) * rx, cy + Math.sin(a) * ry, vv * (0.6 + r() * 0.8))); }
    return out;
  }

  // value-noise field (fast) in 0..1, sampled bilinearly from a random grid
  function grid(W, H_, cell, r) {
    const gw = Math.ceil(W / cell) + 2, gh = Math.ceil(H_ / cell) + 2, g = new Float32Array(gw * gh);
    for (let i = 0; i < g.length; i++) g[i] = r();
    return (x, y) => {
      const fx = x / cell, fy = y / cell, ix = fx | 0, iy = fy | 0, tx = fx - ix, ty = fy - iy;
      const sx = tx * tx * (3 - 2 * tx), sy = ty * ty * (3 - 2 * ty);
      const a = g[iy * gw + ix], b = g[iy * gw + ix + 1], c = g[(iy + 1) * gw + ix], d = g[(iy + 1) * gw + ix + 1];
      return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
    };
  }

  function makeMottle(W, H_, seed) {
    const c = H.layer(W, H_), x = c.getContext('2d'), r = H.rng(seed);
    const small = H.layer(48, 27), sx = small.getContext('2d');
    for (let j = 0; j < 27; j++) for (let i = 0; i < 48; i++) { sx.fillStyle = `rgba(0,0,0,${0.55 + r() * 0.45})`; sx.fillRect(i, j, 1, 1); }
    const mid = H.layer(160, 90), mx = mid.getContext('2d');
    for (let j = 0; j < 90; j++) for (let i = 0; i < 160; i++) { mx.fillStyle = `rgba(0,0,0,${0.75 + r() * 0.25})`; mx.fillRect(i, j, 1, 1); }
    x.imageSmoothingEnabled = true; x.imageSmoothingQuality = 'high';
    x.drawImage(small, 0, 0, W, H_);
    x.globalCompositeOperation = 'destination-in'; x.drawImage(mid, 0, 0, W, H_);
    return c;
  }


  // =================================================================
  // EXPLAINER — "How does AI learn?" painted along one long sketchbook sheet; the camera pans across it.
  // =================================================================
  const EXW = 3400;
  let EXC = null;
  const lerp = (a, b, u) => a + (b - a) * u;
  const cl = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
  const ez = (u) => H.ease.inOut(cl(u));
  const win = (t, a, b) => cl((t - a) / (b - a));

  // pigment pools at the drying edge: alpha += (alpha - blurred alpha) * pool
  function rimPool(cv, pool = 2.2, blur = 4) {
    const w = cv.width, h = cv.height, c = cv.getContext('2d');
    const B = H.layer(w, h), b = B.getContext('2d');
    b.filter = `blur(${blur}px)`; b.drawImage(cv, 0, 0); b.filter = 'none';
    const A = c.getImageData(0, 0, w, h), d = A.data, e = b.getImageData(0, 0, w, h).data;
    for (let i = 3; i < d.length; i += 4) { const rim = d[i] - e[i]; if (rim > 0) d[i] = Math.min(255, d[i] + rim * pool); }
    c.putImageData(A, 0, 0);
    return cv;
  }
  // layered deformed-polygon wash into a canvas context
  function exWash(c, base, col, { layers = 26, alpha = 0.06, amt = 0.14, depth = 3, seed = 1, comp = 'source-over' } = {}) {
    const r = H.rng(seed);
    c.save(); c.globalCompositeOperation = comp; c.fillStyle = Array.isArray(col) ? H.rgba(col, 1) : col;
    for (let i = 0; i < layers; i++) { c.globalAlpha = alpha * (0.6 + r() * 0.8); poly(c, deform(base, r, depth, amt)); c.fill(); }
    c.restore();
  }
  const blob = (x, y, rx, ry, seed, n = 10, v = 1) => deform(circlePts(x, y, rx, ry, n, H.rng(seed), v), H.rng(seed + 1), 2, 0.25);
  function exBloom(c, x, y, r0, seed, a = 0.5) { exWash(c, blob(x, y, r0, r0 * 0.85, seed, 9, 1.4), '#000', { layers: 10, alpha: a / 5, amt: 0.35, depth: 2, seed: seed + 3, comp: 'destination-out' }); }


  function finish(ctx, W, H_, t) {
      const gr = H.rng(99), fine = grid(W, H_, 2.2, gr), mid = grid(W, H_, 7, gr), big = grid(W, H_, 36, gr), speck = grid(W, H_, 1.3, gr);
      const img = ctx.getImageData(0, 0, W, H_), d = img.data;
      const hgt = new Float32Array(W * H_);
      for (let y = 0; y < H_; y++) for (let x = 0; x < W; x++) hgt[y * W + x] = fine(x, y) * 0.3 + mid(x, y) * 0.5 + big(x, y) * 0.2;
      for (let y = 1; y < H_ - 1; y++) for (let x = 1; x < W - 1; x++) {
        const i = y * W + x, p = i * 4, h = hgt[i];
        const shade = 1 + (hgt[i - W - 1] - hgt[i + W + 1]) * 0.1;
        const valley = (0.5 - h) * 2;                        // >0 in pits of the paper
        const sp = speck(x, y);
        let dens = 0;
        for (let c = 0; c < 3; c++) dens += 1 - d[p + c] / PAPER[c];
        dens /= 3;
        const blue = Math.max(0, (d[p + 2] - d[p]) / 120);           // ultramarine / violet granulate, yellows don't
        const g = 1 + (valley * (0.22 + blue * 0.7) + (sp > 0.82 ? (sp - 0.82) * 5 * blue : 0)) * Math.min(1, dens * 3);
        for (let c = 0; c < 3; c++) {
          const dc = Math.max(0, 1 - d[p + c] / PAPER[c]) * g;
          d[p + c] = Math.max(0, Math.min(255, PAPER[c] * (1 - dc) * shade));
        }
      }
      ctx.putImageData(img, 0, 0);
  }
  window.WC = { PAPER, P, deform, poly, circlePts, grid, makeMottle, rimPool, exWash, blob, exBloom, finish };
  window.STYLE = { fonts: ['700 132px "Caveat"', '400 30px "Caveat"', '700 40px "Caveat"'], finish };
})();
