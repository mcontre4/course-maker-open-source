// Original Bauhaus lithographic ink, paper, geometric drawing and fold-wear recipes.
// Reusable plates restore their colour routing with canvas state; caches include dimensions.
(function () {
  // ---------- print helpers (local) ----------
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
  // deterministic noise fields are cached across frames (pure: same inputs -> same arrays)
  const CACHE = {};
  const cachedField = (key, ...a) => {
    const cacheKey = JSON.stringify([key, ...a]);
    return CACHE[cacheKey] || (CACHE[cacheKey] = fieldNoise(...a));
  };

  // mottled ink coverage: modulates alpha of a layer
  const inkify = (layer, seed, mottle, speck) => {
    const c = layer.getContext('2d'), w = layer.width, h = layer.height, img = c.getImageData(0, 0, w, h), d = img.data;
    const n1 = cachedField('ink1' + seed, w, h, seed, 5, 3), n2 = cachedField('ink2' + seed, w, h, seed + 9, 40, 3), r = H.rng(seed + 3);
    for (let i = 0, p = 0; i < d.length; i += 4, p++) {
      if (!d[i + 3]) { r(); continue; }
      let a = 1 - mottle * Math.max(0, n1[p] * 1.6 + n2[p] * 0.9);
      if (r() < speck * (0.4 + Math.max(0, n2[p]) * 3)) a *= 0.25;
      d[i + 3] *= H.clamp(a, 0, 1);
    }
    c.putImageData(img, 0, 0);
  };

  const C = { cream: '#ece2c9', red: '#cf3a2a', yellow: '#efb526', blue: '#1f4f9b', black: '#1c1a18' };

  // ring helper
  const ring = (c, x, y, ro, ri) => { c.beginPath(); c.arc(x, y, ro, 0, Math.PI * 2); c.arc(x, y, ri, 0, Math.PI * 2, true); c.fill(); };

  // constructed geometric lettering (Bayer-like universal alphabet)
  const letter = (c, ch, x, base, xh, sw) => {
    const R = xh / 2;
    if (ch === 'o') { ring(c, x + R, base - R, R, R - sw); return xh; }
    if (ch === 'b') { c.fillRect(x, base - xh * 1.55, sw, xh * 1.55); ring(c, x + R, base - R, R, R - sw); return xh; }
    if (ch === 'r') {
      c.fillRect(x, base - xh, sw, xh);
      c.beginPath(); c.arc(x + R, base - R, R, Math.PI, Math.PI * 1.62); c.arc(x + R, base - R, R - sw, Math.PI * 1.62, Math.PI, true); c.fill();
      return xh * 0.66;
    }
    if (ch === 't') {
      c.fillRect(x + xh * 0.18, base - xh * 1.4, sw, xh * 1.4);
      c.fillRect(x, base - xh, xh * 0.62, sw * 0.9);
      return xh * 0.62;
    }
    return xh * 0.5;
  };

  // ===================== EXPLAINER: "How does AI learn?" =====================
  // One long printed sheet of four panels; the camera tracks along it (Bayer-style info-design spread),
  // then pulls back to show the whole sheet as one diagram for the takeaway.
  let EX_PAPER = null;
  const exPaper = (W, HH) => {
    if (EX_PAPER && EX_PAPER.width === W && EX_PAPER.height === HH) return EX_PAPER;
    const cv = H.layer(W, HH), x = cv.getContext('2d'), img = x.createImageData(W, HH), pd = img.data;
    const lo = cachedField('lo', W, HH, 11, 24, 4), fib = cachedField('fib', W, HH, 12, 2, 2, 3.5, 0.5), r0 = H.rng(5);
    const base = H.hex(C.cream), tan = H.hex('#c9ab78');
    for (let y = 0, p = 0; y < HH; y++) for (let xx = 0; xx < W; xx++, p++) {
      const ex = Math.min(xx, W - xx) / W, ey = Math.min(y, HH - y) / HH;
      const edge = Math.pow(1 - H.clamp(Math.min(ex * 3.2, ey * 2.2) + lo[p] * 0.15, 0, 1), 3);
      const k = 0.35 * edge + 0.12 * Math.max(0, lo[p]);
      const s = 1 + fib[p] * 0.035 + (r0() - 0.5) * 0.04, i = p * 4;
      pd[i] = (base[0] + (tan[0] - base[0]) * k) * s; pd[i + 1] = (base[1] + (tan[1] - base[1]) * k) * s; pd[i + 2] = (base[2] + (tan[2] - base[2]) * k) * s; pd[i + 3] = 255;
    }
    x.putImageData(img, 0, 0);
    const rf = H.rng(77);
    for (let i = 0; i < 26; i++) {
      const px = rf.range(0, W), py = rf.range(0, HH), rr = rf.range(2, 10), g = x.createRadialGradient(px, py, 0, px, py, rr);
      g.addColorStop(0, 'rgba(140,90,40,0.22)'); g.addColorStop(1, 'rgba(140,90,40,0)'); x.fillStyle = g; x.beginPath(); x.arc(px, py, rr, 0, 7); x.fill();
    }
    return (EX_PAPER = cv);
  };

  // geometric pictures: cat = yellow card, dog = blue card
  const exCard = (c, kind, x, y, s) => {
    c.save(); c.translate(x, y);
    c.fillStyle = kind === 'cat' ? C.yellow : C.blue; c.fillRect(-s / 2, -s / 2, s, s);
    if (kind === 'cat') {
      c.fillStyle = C.black;
      c.beginPath(); c.moveTo(-s * 0.3, -s * 0.06); c.lineTo(-s * 0.26, -s * 0.38); c.lineTo(-s * 0.06, -s * 0.2); c.closePath(); c.fill();
      c.beginPath(); c.moveTo(s * 0.3, -s * 0.06); c.lineTo(s * 0.26, -s * 0.38); c.lineTo(s * 0.06, -s * 0.2); c.closePath(); c.fill();
      c.beginPath(); c.arc(0, s * 0.06, s * 0.28, 0, 7); c.fill();
      c.fillStyle = C.yellow; c.beginPath(); c.arc(-s * 0.1, s * 0.02, s * 0.05, 0, 7); c.arc(s * 0.1, s * 0.02, s * 0.05, 0, 7); c.fill();
      c.fillStyle = C.red; c.beginPath(); c.moveTo(-s * 0.05, s * 0.12); c.lineTo(s * 0.05, s * 0.12); c.lineTo(0, s * 0.18); c.closePath(); c.fill();
    } else {
      c.fillStyle = C.cream; c.beginPath(); c.arc(0, s * 0.04, s * 0.27, 0, 7); c.fill();
      c.fillStyle = C.black;
      c.beginPath(); c.arc(-s * 0.27, s * 0.0, s * 0.13, -Math.PI / 2, Math.PI / 2, true); c.closePath(); c.fill();
      c.beginPath(); c.arc(s * 0.27, s * 0.0, s * 0.13, -Math.PI / 2, Math.PI / 2); c.closePath(); c.fill();
      c.beginPath(); c.arc(-s * 0.09, -s * 0.01, s * 0.04, 0, 7); c.arc(s * 0.09, -s * 0.01, s * 0.04, 0, 7); c.fill();
      c.beginPath(); c.arc(0, s * 0.12, s * 0.06, 0, 7); c.fill();
    }
    c.restore();
  };
  // label tag that lands on the thing it labels
  const exTag = (c, txt, x, y, p, size = 28, bg = C.black, fg = C.cream) => {
    if (p <= 0) return;
    c.save(); c.font = `700 ${size}px "Space Grotesk"`; c.textBaseline = 'middle';
    const w = c.measureText(txt).width + size * 0.9, h = size * 1.5, dy = -(1 - H.ease.back(p)) * 30;
    c.fillStyle = bg; c.fillRect(x - w / 2, y - h / 2 + dy, w, h);
    c.fillStyle = fg; c.textAlign = 'center'; c.fillText(txt, x, y + dy + 1);
    c.restore();
  };
  // thick Bauhaus arrow (bar + triangle), drawn on with progress p
  const exArrow = (c, x0, y0, x1, y1, p, w = 10, col = C.black) => {
    if (p <= 0) return;
    const L = Math.hypot(x1 - x0, y1 - y0), a = Math.atan2(y1 - y0, x1 - x0), l = L * p;
    c.save(); c.translate(x0, y0); c.rotate(a); c.fillStyle = col;
    c.fillRect(0, -w / 2, Math.max(0, l - w * 2), w);
    c.beginPath(); c.moveTo(l, 0); c.lineTo(l - w * 2.6, -w * 1.5); c.lineTo(l - w * 2.6, w * 1.5); c.closePath(); c.fill();
    c.restore();
  };
  // the model: the robot head from the poster, with three weight dials on a control bar
  const exRobot = (c, x, y, s, dials, look, mood = 0) => {
    const k = s / 300, hx = x - s / 2, hy = y - s / 2;
    c.fillStyle = C.black; c.fillRect(x - 100 * k, hy - 62 * k, 200 * k, 52 * k);
    dials.forEach((a, i) => {
      const dx = x + (i - 1) * 62 * k, dy = hy - 36 * k;
      c.fillStyle = C.cream; c.beginPath(); c.arc(dx, dy, 19 * k, 0, 7); c.fill();
      c.save(); c.translate(dx, dy); c.rotate(a); c.fillStyle = [C.red, C.blue, C.black][i]; c.fillRect(-3 * k, -17 * k, 6 * k, 17 * k); c.restore();
    });
    c.fillStyle = C.red; c.beginPath(); c.arc(hx, y, 50 * k, Math.PI / 2, Math.PI * 1.5); c.closePath(); c.fill();
    c.fillStyle = C.black; c.beginPath(); c.arc(hx + s, y, 50 * k, -Math.PI / 2, Math.PI / 2); c.closePath(); c.fill();
    c.fillStyle = C.blue; c.fillRect(hx, hy, s, s);
    c.fillStyle = C.yellow; c.beginPath(); c.arc(hx + 85 * k, hy + 105 * k, 50 * k, 0, 7); c.fill();
    c.fillStyle = mood > 0 ? C.yellow : C.red; c.fillRect(hx + s - 135 * k, hy + 55 * k, 100 * k, 100 * k);
    const dx = H.lerp(-8, 18, look) * k;
    c.fillStyle = C.black; c.beginPath(); c.arc(hx + 85 * k + dx, hy + 105 * k, 21 * k, 0, 7); c.arc(hx + s - 85 * k + dx, hy + 105 * k, 21 * k, 0, 7); c.fill();
    c.fillStyle = C.yellow; c.beginPath(); c.moveTo(x - 26 * k, hy + 150 * k); c.lineTo(x + 26 * k, hy + 150 * k); c.lineTo(x, hy + 196 * k); c.closePath(); c.fill();
    c.fillStyle = C.black; c.fillRect(x - 92 * k, hy + 220 * k, 184 * k, 46 * k);
    c.fillStyle = C.blue; for (let i = 0; i < 5; i++) c.fillRect(x - 76 * k + i * 33 * k, hy + 228 * k, 13 * k, 30 * k);
  };
  const fmt = (n) => Math.round(n).toLocaleString('en-US');

  // colour separations: every fill lands on its own plate (yellow / red / blue / black) and knocks the same shape out
  // of the other plates, exactly like a litho knockout. Cream fills knock out all plates (reversed type shows paper).
  // The plates are then printed with the per-colour misregistration offsets, overlapping slivers multiply.
  const PLATE_COLS = ['yellow', 'red', 'blue', 'black'];
  const PLATE_OF = { [C.yellow]: 0, [C.red]: 1, [C.blue]: 2, [C.black]: 3 };
  const plates = (W, HH) => {
    const PLATES = PLATE_COLS.map(() => H.layer(W, HH));
    const cs = PLATES.map((pl) => { const x = pl.getContext('2d'); x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; x.globalCompositeOperation = 'source-over'; x.clearRect(0, 0, W, HH); return x; });
    let fill = C.black, stroke = C.black;
    const stack = [];
    cs.forEach(x => { x.fillStyle = fill; x.strokeStyle = stroke; });
    const paint = (style, op) => { const k = style in PLATE_OF ? PLATE_OF[style] : style === C.cream ? -1 : 3;
      cs.forEach((x, i) => { if (i === k) op(x); else { x.globalCompositeOperation = 'destination-out'; op(x); x.globalCompositeOperation = 'source-over'; } }); };
    const DRAW = { fill: 1, fillRect: 1, fillText: 1, stroke: 2, strokeRect: 2, strokeText: 2 };
    const c = new Proxy({}, {
      get(_, prop) {
        if (prop === 'fillStyle') return fill; if (prop === 'strokeStyle') return stroke;
        if (prop === 'save') return () => { stack.push([fill, stroke]); cs.forEach(x => x.save()); };
        if (prop === 'restore') return () => {
          if (stack.length) [fill, stroke] = stack.pop();
          cs.forEach(x => x.restore());
        };
        const v = cs[0][prop];
        if (typeof v !== 'function') return v;
        if (DRAW[prop]) return (...a) => paint(DRAW[prop] === 1 ? fill : stroke, (x) => x[prop](...a));
        if (prop === 'measureText' || prop.startsWith('create') || prop.startsWith('get') || prop.startsWith('isPoint')) return (...a) => cs[0][prop](...a);
        return (...a) => { let r; cs.forEach((x) => { r = x[prop](...a); }); return r; };
      },
      set(_, prop, v) { if (prop === 'fillStyle') fill = v; else if (prop === 'strokeStyle') stroke = v; cs.forEach((x) => { x[prop] = v; }); return true; },
    });
    return { c, layers: PLATES };
  };

  const REG = { yellow: [2, -1], red: [-1.5, 1], blue: [1, 2], black: [0, 0] };
  function composite(ctx, frame, W, HH) {
    ctx.drawImage(exPaper(W, HH), 0, 0);
    const L = H.layer(W, HH), lc = L.getContext('2d'); lc.globalCompositeOperation = 'multiply';
    frame.layers.forEach((pl, i) => { const o = REG[PLATE_COLS[i]]; lc.drawImage(pl, o[0], o[1]); });
    inkify(L, 21, 0.22, 0.004);
    ctx.save(); ctx.globalCompositeOperation = 'multiply'; ctx.drawImage(L, 0, 0); ctx.restore();
  }
  function finish(ctx, W, HH, t) {
    const crease = (vert) => { const g = vert ? ctx.createLinearGradient(W / 2 - 4, 0, W / 2 + 10, 0) : ctx.createLinearGradient(0, HH / 2 - 8, 0, HH / 2 + 4);
      g.addColorStop(0, 'rgba(255,250,235,0)'); g.addColorStop(0.45, 'rgba(255,250,235,0.18)'); g.addColorStop(0.55, 'rgba(70,50,30,0.14)'); g.addColorStop(1, 'rgba(70,50,30,0)'); ctx.fillStyle = g; vert ? ctx.fillRect(W / 2 - 4, 0, 14, HH) : ctx.fillRect(0, HH / 2 - 8, W, 12); };
    crease(true); crease(false);
    { // scuffs along the folds (as in the still)
      const rs = H.rng(31); ctx.fillStyle = 'rgba(245,238,220,0.5)';
      for (let i = 0; i < 260; i++) { const along = rs.range(0, 1); if (rs() < 0.5) ctx.fillRect(W / 2 + 2 + rs.gauss() * 1.2, along * HH, 1.2, rs.range(1, 4)); else ctx.fillRect(along * W, HH / 2 - 2 + rs.gauss() * 1.2, rs.range(1, 4), 1.2); } }
    H.grain(ctx, W, HH, 0.06, 9 + Math.floor(t * 12), true);
    H.vignette(ctx, W, HH, 0.18, '60,40,20');

  }
  window.BAUHAUS = { C, fieldNoise, cachedField, inkify, ring, letter, exPaper,
    exCard, exTag, exArrow, exRobot, fmt, PLATE_COLS, REG, plates, composite, finish };
  window.STYLE = { fonts: ['700 64px "Space Grotesk"', '400 28px "Space Grotesk"', '800 44px "Syne"'], finish };
})();
