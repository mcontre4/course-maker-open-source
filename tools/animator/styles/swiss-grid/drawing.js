// Original Swiss-grid offset-ink, paper-fibre and grain recipes from the supplied reference.
// Cache keys include every noise parameter and dropout masks clip at canvas edges.
(function () {
  const fieldNoise = (w, h, seed, cell, oct, sx = 1, sy = 1) => {
    const nz = H.makeNoise(seed), gw = Math.ceil(w / cell) + 2, gh = Math.ceil(h / cell) + 2, g = new Float32Array(gw * gh);
    for (let j = 0; j < gh; j++) for (let i = 0; i < gw; i++) g[j * gw + i] = nz.fbm2(i * 0.35 * sx, j * 0.35 * sy, oct);
    const out = new Float32Array(w * h);
    for (let y = 0; y < h; y++) {
      const fy = y / cell, j = fy | 0, ty = fy - j;
      for (let x = 0; x < w; x++) {
        const fx = x / cell, i = fx | 0, tx = fx - i, k = j * gw + i;
        const a = g[k] + (g[k + 1] - g[k]) * tx, b = g[k + gw] + (g[k + gw + 1] - g[k + gw]) * tx;
        out[y * w + x] = a + (b - a) * ty;
      }
    }
    return out;
  };

  const RED = '#e2231a', BLACK = '#141414', PAPER = '#f1efe9';

  // ===================== EXPLAINER: "How does AI learn?" =====================
  // A Zürich-school information sequence: every page hangs on the same 12-column grid; pages change with a
  // column-by-column red wipe; arrows are hairline rules with solid heads; numbers are set in Inter 800.
  const EXF = {};
  const exField = (k, ...a) => { const kk = JSON.stringify([k, ...a]); return EXF[kk] || (EXF[kk] = fieldNoise(...a)); }; // cached per size
  // ink dropouts: fixed-seed single-pixel specks plus a few offset "hickeys" (tiny donuts of missing ink)
  const speckMask = (w, h) => {
    const key = 'speck' + w + 'x' + h; if (EXF[key]) return EXF[key];
    const m = new Float32Array(w * h), r = H.rng(12);
    for (let p = 0; p < m.length; p++) if (r() < 0.0015) m[p] = 0.5;
    const rh = H.rng(1212);
    for (let k = 0; k < 70; k++) {
      const cx = rh.range(4, w - 4), cy = rh.range(4, h - 4), ro = rh.range(1.6, 3.2);
      for (let y = Math.floor(cy - ro - 1); y <= cy + ro + 1; y++) for (let x = Math.floor(cx - ro - 1); x <= cx + ro + 1; x++) {
        if (x < 0 || x >= w || y < 0 || y >= h) continue;
        const dd = Math.hypot(x - cx, y - cy), ring = Math.max(0, 1 - Math.abs(dd - ro * 0.75) / (ro * 0.4)), core = dd < ro * 0.3 ? 0.35 : 0;
        const v = Math.min(0.85, ring * 0.8 + core); if (v > m[y * w + x]) m[y * w + x] = v;
      }
    }
    return (EXF[key] = m);
  };
  const pict = (c, kind, x, y, s, col = BLACK, eye = PAPER) => { // isotype-like pictograms
    c.fillStyle = col;
    if (kind === 'cat') {
      c.beginPath(); c.moveTo(x - s * 0.3, y - s * 0.02); c.lineTo(x - s * 0.27, y - s * 0.4); c.lineTo(x - s * 0.05, y - s * 0.2); c.closePath(); c.fill();
      c.beginPath(); c.moveTo(x + s * 0.3, y - s * 0.02); c.lineTo(x + s * 0.27, y - s * 0.4); c.lineTo(x + s * 0.05, y - s * 0.2); c.closePath(); c.fill();
      c.beginPath(); c.arc(x, y + s * 0.06, s * 0.3, 0, 7); c.fill();
    } else {
      c.beginPath(); c.arc(x, y + s * 0.02, s * 0.28, 0, 7); c.fill();
      c.beginPath(); c.ellipse(x - s * 0.3, y + s * 0.04, s * 0.1, s * 0.22, 0.35, 0, 7); c.fill();
      c.beginPath(); c.ellipse(x + s * 0.3, y + s * 0.04, s * 0.1, s * 0.22, -0.35, 0, 7); c.fill();
      c.beginPath(); c.ellipse(x, y + s * 0.22, s * 0.13, s * 0.1, 0, 0, 7); c.fill();
    }
    if (s > 30) { c.fillStyle = eye; c.beginPath(); c.arc(x - s * 0.1, y + s * 0.02, s * 0.045, 0, 7); c.arc(x + s * 0.1, y + s * 0.02, s * 0.045, 0, 7); c.fill(); }
  };
  const rule = (c, x0, y0, x1, y1, p, w = 2, col = BLACK, head = true) => { // hairline arrow
    if (p <= 0) return;
    const x = H.lerp(x0, x1, p), y = H.lerp(y0, y1, p), a = Math.atan2(y1 - y0, x1 - x0);
    c.strokeStyle = col; c.fillStyle = col; c.lineWidth = w; c.lineCap = 'butt';
    const hl = 14 + w * 2.6;
    c.beginPath(); c.moveTo(x0, y0); c.lineTo(x - Math.cos(a) * hl * 0.6, y - Math.sin(a) * hl * 0.6); c.stroke();
    if (head) { c.beginPath(); c.moveTo(x, y); c.lineTo(x - Math.cos(a - 0.42) * hl, y - Math.sin(a - 0.42) * hl); c.lineTo(x - Math.cos(a + 0.42) * hl, y - Math.sin(a + 0.42) * hl); c.closePath(); c.fill(); }
  };


  function arcField(c, ox, oy, t) {
    const P = (d, dur = 0.6) => H.ease.out(H.clamp((t - d) / dur, 0, 1));
      // red disc
      c.fillStyle = RED;
      c.beginPath(); c.arc(ox, oy, 205 * P(0.2, 0.8), 0, Math.PI * 2); c.fill();

      // concentric arc segments (the "score")
      const rr = H.rng(404);
      c.strokeStyle = BLACK; c.lineCap = 'butt';
      for (let k = 0; k < 17; k++) {
        const rad = 46 + k * 19;
        const lw = H.lerp(12, 5, k / 16);
        const Q = Math.PI / 8; // angles snap to a 22.5° module at the hero frame
        const len = rr.int(2, 9) * Q;
        const spd = rr.range(-0.4, 0.4);
        // the rings spin in and decelerate onto the module (locked at t=3.2), then drift very slowly
        const settle = t < 3.2 ? -Math.pow(3.2 - t, 2) * 0.9 : (t - 3.2) * 0.05;
        const a0 = rr.int(0, 15) * Q + settle * spd * 2.2;
        const grow = P(0.4 + k * 0.06, 0.9);
        c.lineWidth = lw;
        c.beginPath(); c.arc(ox, oy, rad, a0, a0 + len * grow); c.stroke();
        if (rr() < 0.45) { // a second, shorter segment on the same ring
          const b0 = a0 + len + rr.int(1, 3) * Q;
          c.beginPath(); c.arc(ox, oy, rad, b0, b0 + rr.int(1, 3) * Q * grow); c.stroke();
        }
      }
      // one red ring segment outside the disc, bleeding off the top edge
      c.strokeStyle = RED; c.lineWidth = 6;
      { const g = P(1.3, 0.8); if (g > 0) { c.beginPath(); c.arc(ox, oy, 46 + 17 * 19, -Math.PI * 0.95 + t * 0.12, -Math.PI * 0.95 + t * 0.12 + Math.PI * 0.6 * g); c.stroke(); } }
      // centre point
      const cp = H.ease.back(H.clamp((t - 0.9) / 0.35, 0, 1));
      c.fillStyle = PAPER; c.beginPath(); c.arc(ox, oy, 14 * cp, 0, 7); c.fill();
      c.fillStyle = BLACK; c.beginPath(); c.arc(ox, oy, 6 * cp, 0, 7); c.fill();

  }

  const grid = () => ({ margin: 48, pitch: 100, columnWidth: 84, columns: 12, colX: i => 48 + i * 100 });
  function frame(W, HH) {
    const layer = H.layer(W, HH), c = layer.getContext('2d'); c.textBaseline = 'alphabetic';
    return { layer, c };
  }
  function composite(ctx, frame, W, HH) {
    ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, HH);
    const L = H.layer(W, HH), c = L.getContext('2d'); c.drawImage(frame.layer, 0, 0);
    const img = c.getImageData(0, 0, W, HH), d = img.data, n1 = exField('n1', W, HH, 3, 3, 2), n2 = exField('n2', W, HH, 8, 60, 3), sm = speckMask(W, HH);
    for (let i = 0, p = 0; i < d.length; i += 4, p++) { if (!d[i + 3]) continue; d[i + 3] *= Math.max(0, 1 - 0.07 * Math.max(0, n1[p] * 1.5 + n2[p]) - sm[p]); }
    c.putImageData(img, 0, 0);
    ctx.save(); ctx.globalAlpha = 0.12; ctx.filter = 'blur(1.2px)'; ctx.drawImage(L, 0, 0); ctx.restore();
    ctx.save(); ctx.globalCompositeOperation = 'multiply'; ctx.drawImage(L, 0, 0); ctx.restore();

  }
  function finish(ctx, W, HH, t) {
    const pi = ctx.getImageData(0, 0, W, HH), pd = pi.data, fib = exField('fib', W, HH, 21, 2, 2, 3, 0.6), lo = exField('lo', W, HH, 22, 30, 3), rg = H.rng(99 + Math.floor(t * 12));
    for (let i = 0, p = 0; i < pd.length; i += 4, p++) { const s = 1 + fib[p] * 0.022 + lo[p] * 0.02 + (rg() - 0.5) * 0.03; pd[i] *= s; pd[i + 1] *= s; pd[i + 2] *= s; }
    ctx.putImageData(pi, 0, 0);
    H.vignette(ctx, W, HH, 0.07, '40,30,20');

  }
  function columnWipe(c, W, HH, elapsed, colour = RED) {
    const S = (a, b) => H.clamp((elapsed - a) / (b - a));
    if (elapsed < 0 || elapsed > 1.2) return;
    c.save(); c.fillStyle = colour;
    for (let i = 0; i < 12; i++) {
      const a = H.ease.inOut(S(i * 0.025, i * 0.025 + 0.28));
      const b = H.ease.inOut(S(0.6 + i * 0.025, 0.88 + i * 0.025));
      const x = i * W / 12; if (a > b) c.fillRect(x, b * HH, W / 12 + 1, (a - b) * HH);
    }
    c.restore();
  }
  window.SWISS = { RED, BLACK, PAPER, fieldNoise, exField, speckMask, pict, rule,
    arcField, grid, frame, composite, columnWipe, finish };
  window.STYLE = { fonts: ['800 112px "Inter"', '600 28px "Inter"', '400 28px "Inter"'], finish };
})();
