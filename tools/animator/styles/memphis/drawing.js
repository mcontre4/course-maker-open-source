// Original Memphis outlines, hard shadows, patterns and grain from the supplied reference.
(function () {
  const K = '#151515';
  const PAL = { pink: '#f9c3d2', mint: '#a9e5d0', lilac: '#cbb8f4', butter: '#fff0a6', cream: '#fff8ec', magenta: '#ff4f9b', blue: '#2b62ff', yellow: '#ffd02e', teal: '#00b2a0', red: '#ff5a3c' };

  // filled + outlined + hard drop shadow
  const solid = (c, path, fill, sh = 10, lw = 5) => {
    c.save(); c.translate(sh, sh); c.fillStyle = K; c.fill(path); c.restore();
    c.fillStyle = fill; c.fill(path); c.lineWidth = lw; c.strokeStyle = K; c.lineJoin = 'round'; c.stroke(path);
  };
  const squigglePath = (x, y, len, amp, waves, ang, ph = 0, frac = 1) => {
    const p = new Path2D(), ca = Math.cos(ang), sa = Math.sin(ang);
    for (let i = 0; i <= Math.round(80 * frac); i++) {
      const u = i / 80, lx = u * len, ly = Math.sin(u * waves * Math.PI * 2 + ph) * amp;
      const X = x + lx * ca - ly * sa, Y = y + lx * sa + ly * ca;
      i ? p.lineTo(X, Y) : p.moveTo(X, Y);
    }
    return p;
  };
  const zigzagPath = (x, y, len, amp, n, ang, frac = 1) => {
    const p = new Path2D(), ca = Math.cos(ang), sa = Math.sin(ang), f = frac * n;
    for (let i = 0; i <= Math.ceil(f); i++) { const ii = Math.min(i, f), i0 = Math.floor(ii), fr = ii - i0, ya = i0 % 2 ? -amp : amp, yb = (i0 + 1) % 2 ? -amp : amp; const lx = (ii / n) * len, ly = ya + (yb - ya) * fr; const X = x + lx * ca - ly * sa, Y = y + lx * sa + ly * ca; i ? p.lineTo(X, Y) : p.moveTo(X, Y); }
    return p;
  };
  const strokeOutlined = (c, path, col, w, ow = 4, sh = 8) => {
    c.lineCap = 'round'; c.lineJoin = 'round';
    c.save(); c.translate(sh, sh); c.strokeStyle = K; c.lineWidth = w + ow * 2; c.stroke(path); c.restore();
    c.strokeStyle = K; c.lineWidth = w + ow * 2; c.stroke(path);
    c.strokeStyle = col; c.lineWidth = w; c.stroke(path);
  };
  const terrazzo = (c, path, seed, base = PAL.cream) => {
    c.save(); c.clip(path); c.fillStyle = base; c.fillRect(0, 0, 1280, 720);
    const r = H.rng(seed), cols = [PAL.magenta, PAL.blue, PAL.yellow, PAL.teal, K, PAL.pink, PAL.lilac, PAL.red];
    const bb = { x0: 0, y0: 0, x1: 1280, y1: 720 };
    for (let i = 0; i < 2400; i++) {
      const x = r.range(bb.x0, bb.x1), y = r.range(bb.y0, bb.y1);
      if (!c.isPointInPath(path, x, y)) continue;
      const s = r.range(3, 11) * (r() < 0.08 ? 2 : 1), n = r.int(3, 6), a0 = r.range(0, 7);
      c.fillStyle = r.pick(cols); c.beginPath();
      for (let k = 0; k < n; k++) { const a = a0 + (k / n) * Math.PI * 2 + r.range(-0.3, 0.3), rr = s * r.range(0.5, 1); k ? c.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr) : c.moveTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
      c.closePath(); c.fill();
    }
    c.restore();
  };

  // ===================== EXPLAINER: "How does AI learn?" =====================
  // Memphis cut-out animation on twos: scenes change with a striped band that swipes across, arrows are fat
  // outlined shapes, counters are stickers that pop, emphasis is a spiky starburst.
  const roundRect = (x, y, w, h, r) => { const p = new Path2D(); p.moveTo(x + r, y); p.arcTo(x + w, y, x + w, y + h, r); p.arcTo(x + w, y + h, x, y + h, r); p.arcTo(x, y + h, x, y, r); p.arcTo(x, y, x + w, y, r); p.closePath(); return p; };
  const bubble = (w, h, tail) => { // tail: [x, y] of the tip relative to centre
    const p = new Path2D(), r = 34, x = -w / 2, y = -h / 2;
    p.moveTo(x + r, y); p.arcTo(x + w, y, x + w, y + h, r); p.arcTo(x + w, y + h, x, y + h, r);
    if (tail) { p.lineTo(tail[0] + 40, y + h); p.lineTo(tail[0], tail[1]); p.lineTo(tail[0] - 10, y + h); }
    p.arcTo(x, y + h, x, y, r); p.arcTo(x, y, x + w, y, r); p.closePath(); return p;
  };
  const burst = (n, r0, r1) => { const p = new Path2D(); for (let i = 0; i < n * 2; i++) { const a = i / (n * 2) * Math.PI * 2, r = i % 2 ? r0 : r1; i ? p.lineTo(Math.cos(a) * r, Math.sin(a) * r) : p.moveTo(Math.cos(a) * r, Math.sin(a) * r); } p.closePath(); return p; };
  const fatArrow = (c, x0, y0, x1, y1, p, col, w = 22) => { // outlined chunky arrow with hard shadow
    if (p <= 0) return; const a = Math.atan2(y1 - y0, x1 - x0), l = Math.hypot(x1 - x0, y1 - y0) * p, hw = w * 1.3, hl = w * 1.6;
    const path = new Path2D(); path.moveTo(0, -w / 2); path.lineTo(Math.max(0, l - hl), -w / 2); path.lineTo(Math.max(0, l - hl), -hw); path.lineTo(l, 0); path.lineTo(Math.max(0, l - hl), hw); path.lineTo(Math.max(0, l - hl), w / 2); path.lineTo(0, w / 2); path.closePath();
    c.save(); c.translate(x0, y0); c.rotate(a); solid(c, path, col, 6, 4); c.restore();
  };
  const face = (c, kind, x, y, s) => { // chunky sticker card with a cat or dog face
    const card = roundRect(x - s / 2, y - s / 2, s, s, s * 0.14); solid(c, card, PAL.cream, 6, 4);
    c.lineWidth = 3.5; c.strokeStyle = K;
    if (kind === 'cat') {
      const p = new Path2D(); p.moveTo(x - s * 0.3, y + s * 0.02); p.lineTo(x - s * 0.28, y - s * 0.34); p.lineTo(x - s * 0.08, y - s * 0.18); p.lineTo(x + s * 0.08, y - s * 0.18); p.lineTo(x + s * 0.28, y - s * 0.34); p.lineTo(x + s * 0.3, y + s * 0.02); p.arc(x, y + s * 0.04, s * 0.3, 0, Math.PI); p.closePath();
      c.fillStyle = PAL.yellow; c.fill(p); c.stroke(p);
      c.fillStyle = K; c.beginPath(); c.arc(x - s * 0.1, y + s * 0.02, s * 0.04, 0, 7); c.arc(x + s * 0.1, y + s * 0.02, s * 0.04, 0, 7); c.fill();
      c.fillStyle = PAL.magenta; c.beginPath(); c.moveTo(x - s * 0.05, y + s * 0.1); c.lineTo(x + s * 0.05, y + s * 0.1); c.lineTo(x, y + s * 0.16); c.closePath(); c.fill();
    } else {
      c.fillStyle = PAL.blue; for (const sd of [-1, 1]) { c.beginPath(); c.ellipse(x + sd * s * 0.28, y + s * 0.02, s * 0.1, s * 0.2, sd * -0.3, 0, 7); c.fill(); c.stroke(); }
      c.fillStyle = PAL.pink; c.beginPath(); c.arc(x, y + s * 0.02, s * 0.25, 0, 7); c.fill(); c.stroke();
      c.fillStyle = K; c.beginPath(); c.arc(x - s * 0.09, y - s * 0.02, s * 0.035, 0, 7); c.arc(x + s * 0.09, y - s * 0.02, s * 0.035, 0, 7); c.fill();
      c.beginPath(); c.ellipse(x, y + s * 0.1, s * 0.06, s * 0.045, 0, 0, 7); c.fill();
    }
  };
  const tag = (c, txt, x, y, col, size = 22, rot = 0, halo = 0) => { c.save(); c.translate(x, y); c.rotate(rot); c.font = `700 ${size}px "Fredoka"`; const w = c.measureText(txt).width + size; if (halo) { const hp = roundRect(-w / 2 - halo, -size * 0.75 - halo, w + halo * 2, size * 1.5 + halo * 2, size * 0.75 + halo); solid(c, hp, PAL.cream, 6, 3); } const p = roundRect(-w / 2, -size * 0.75, w, size * 1.5, size * 0.75); solid(c, p, col, 4, 3); c.fillStyle = K; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(txt, 0, 1); c.restore(); };
  const chunky = (c, txt, x, y, size, col, ls = -4) => { c.save(); c.font = `400 ${size}px "Rubik Mono One"`; c.letterSpacing = ls + 'px'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.lineJoin = 'round'; c.fillStyle = K; c.fillText(txt, x + size * 0.07, y + size * 0.07); c.lineWidth = Math.max(4, size * 0.09); c.strokeStyle = K; c.strokeText(txt, x, y); c.fillStyle = col; c.fillText(txt, x, y); c.restore(); c.letterSpacing = '0px'; };
  const machine = (c, x, y, knobs, look, mood) => { // the model: a Memphis totem-computer with a funnel and three knobs
    // feet
    for (const sd of [-1, 1]) { const f = new Path2D(); f.arc(x + sd * 60, y + 140, 34, Math.PI, 0); f.closePath(); solid(c, f, PAL.blue, 6, 4); }
    const body = roundRect(x - 115, y - 120, 230, 260, 26); solid(c, body, PAL.lilac, 12, 5);
    c.save(); c.clip(body); c.fillStyle = 'rgba(21,21,21,0.5)'; for (let i = -10; i < 10; i++) { c.beginPath(); c.arc(x - 100 + (i % 5) * 50, y + 80 + Math.floor(i / 5) * 18, 3, 0, 7); c.fill(); } c.restore();
    const scr = roundRect(x - 85, y - 92, 170, 110, 18); solid(c, scr, PAL.cream, 0, 4);
    const dx = (look - 0.5) * 16;
    c.fillStyle = K; c.beginPath(); c.arc(x - 34 + dx, y - 42, 12, 0, 7); c.arc(x + 34 + dx, y - 42, 12, 0, 7); c.fill();
    c.lineWidth = 5; c.strokeStyle = K; c.lineCap = 'round'; c.beginPath(); if (mood > 0) c.arc(x + dx * 0.5, y - 20, 22, 0.2, Math.PI - 0.2); else if (mood < 0) c.arc(x + dx * 0.5, y + 2, 20, Math.PI + 0.3, -0.3); else { c.moveTo(x - 18, y - 6); c.lineTo(x + 18, y - 6); } c.stroke();
    // knobs on the belly
    knobs.forEach((a, i) => { const kx = x - 62 + i * 62, ky = y + 50; const kp = new Path2D(); kp.arc(kx, ky, 20, 0, Math.PI * 2); solid(c, kp, [PAL.magenta, PAL.teal, PAL.yellow][i], 4, 4); c.save(); c.translate(kx, ky); c.rotate(a); c.fillStyle = K; c.fillRect(-3, -18, 6, 16); c.restore(); });
    // funnel on top
    const fn = new Path2D(); fn.moveTo(x - 80, y - 210); fn.lineTo(x + 80, y - 210); fn.lineTo(x + 26, y - 122); fn.lineTo(x - 26, y - 122); fn.closePath();
    solid(c, fn, PAL.yellow, 8, 5); c.save(); c.clip(fn); c.fillStyle = K; for (let i = -6; i < 6; i++) c.fillRect(x + i * 24, y - 220, 9, 110); c.restore(); c.lineWidth = 5; c.strokeStyle = K; c.stroke(fn);
  };

  // static per-scene ground: pastel split, bacterio dashes at hero strength, and a decor layer (terrazzo quarter-disc,
  // dot-grid card, confetti, a squiggle) kept to corners and edges that no story element uses. Built once per scene.
  const GROUNDS = {};
  const confetti = (c, r, spots) => spots.forEach(([x, y], i) => {
    const s = r.range(10, 17), kind = i % 4, col = [PAL.magenta, PAL.blue, PAL.yellow, PAL.teal, PAL.red, K][(i * 5 + 1) % 6];
    c.save(); c.translate(x, y); c.rotate(r.range(0, 7)); const p = new Path2D();
    if (kind <= 1) { p.moveTo(0, -s); p.lineTo(s * 0.9, s * 0.6); p.lineTo(-s * 0.9, s * 0.6); p.closePath(); c.fillStyle = col; c.fill(p); c.lineWidth = 3; c.strokeStyle = K; c.stroke(p); }
    else if (kind === 2) { c.fillStyle = col; c.fillRect(-s * 0.9, -3.5, s * 1.8, 7); }
    else { c.beginPath(); c.arc(0, 0, s * 0.45, 0, 7); c.fillStyle = col; c.fill(); c.lineWidth = 3; c.strokeStyle = K; c.stroke(); }
    c.restore();
  });
  const dotCard = (c, x, y, w, h, col, rot = 0) => { c.save(); c.translate(x + w / 2, y + h / 2); c.rotate(rot); const p = new Path2D(); p.rect(-w / 2, -h / 2, w, h); solid(c, p, col, 8, 4); c.save(); c.clip(p); c.fillStyle = K; for (let yy = -h / 2 + 14; yy < h / 2 - 6; yy += 16) for (let xx = -w / 2 + 14; xx < w / 2 - 6; xx += 16) { c.beginPath(); c.arc(xx, yy, 3, 0, 7); c.fill(); } c.restore(); c.restore(); };
  const quarter = (c, cx, cy, R, a0, seed) => { const p = new Path2D(); p.moveTo(cx, cy); p.arc(cx, cy, R, a0, a0 + Math.PI / 2); p.closePath(); c.save(); c.translate(10, 10); c.fillStyle = K; c.fill(p); c.restore(); terrazzo(c, p, seed); c.lineWidth = 5; c.strokeStyle = K; c.stroke(p); };
  const gridCard = (c, x, y, w, h, col, rot) => { c.save(); c.translate(x + w / 2, y + h / 2); c.rotate(rot); const p = new Path2D(); p.rect(-w / 2, -h / 2, w, h); solid(c, p, col, 8, 4); c.save(); c.clip(p); c.strokeStyle = 'rgba(21,21,21,0.5)'; c.lineWidth = 2; for (let xx = -w / 2; xx < w / 2; xx += 24) { c.beginPath(); c.moveTo(xx, -h / 2); c.lineTo(xx, h / 2); c.stroke(); } for (let yy = -h / 2; yy < h / 2; yy += 24) { c.beginPath(); c.moveTo(-w / 2, yy); c.lineTo(w / 2, yy); c.stroke(); } c.restore(); c.lineWidth = 4; c.strokeStyle = K; c.stroke(p); c.restore(); };
  function sceneGround(scene, grounds, W, HH) {
    const key = JSON.stringify([scene, grounds, W, HH]);
    if (GROUNDS[key]) return GROUNDS[key];
    const L = H.layer(W, HH), c = L.getContext('2d');
    c.fillStyle = grounds[0]; c.fillRect(0, 0, W, HH);
    c.fillStyle = grounds[1]; c.beginPath(); c.moveTo(860, 0); c.lineTo(W, 0); c.lineTo(W, HH); c.lineTo(600, HH); c.closePath(); c.fill();
    const rb = H.rng(3 + scene); c.fillStyle = 'rgba(21,21,21,0.55)';
    for (let i = 0; i < 260; i++) { const x = rb.range(0, W), y = rb.range(0, HH), a = rb.range(0, Math.PI); c.save(); c.translate(x, y); c.rotate(a); c.beginPath(); c.ellipse(0, 0, rb.range(3, 7), 1.6, 0, 0, 7); c.fill(); c.restore(); }
    const r = H.rng(40 + scene);
    c.lineCap = 'round'; c.lineJoin = 'round';
    if (scene === 1) {
      quarter(c, 0, HH, 165, -Math.PI / 2, 21);
      dotCard(c, 1010, 638, 240, 62, PAL.butter, -0.02);
      strokeOutlined(c, squigglePath(430, 688, 230, 9, 3.5, -0.03), PAL.blue, 8, 3, 5);
      confetti(c, r, [[40, 170], [78, 300], [36, 430], [1240, 40], [1150, 70], [1250, 150], [470, 40], [600, 640], [1260, 400]]);
    } else if (scene === 2) {
      quarter(c, W, HH, 165, Math.PI, 22);
      dotCard(c, 1132, 22, 128, 84, PAL.pink, 0.04);
      strokeOutlined(c, squigglePath(620, 690, 240, 10, 3, -0.04), PAL.magenta, 8, 3, 5);
      c.strokeStyle = K; c.lineWidth = 6; c.stroke(zigzagPath(48, 200, 300, 10, 9, Math.PI / 2));
      confetti(c, r, [[40, 640], [110, 690], [380, 670], [900, 640], [880, 40], [1060, 40], [1250, 210], [1240, 300], [440, 40]]);
    } else if (scene === 3) {
      quarter(c, W, HH, 150, Math.PI, 23);
      gridCard(c, 430, 30, 230, 96, PAL.butter, -0.03);
      strokeOutlined(c, squigglePath(30, 680, 210, 9, 3, -0.03), PAL.teal, 8, 3, 5);
      confetti(c, r, [[720, 50], [780, 120], [1250, 60], [1180, 40], [40, 200], [60, 330], [850, 690], [700, 690]]);
    } else {
      quarter(c, W, 0, 160, Math.PI / 2, 24);
      dotCard(c, 560, 652, 240, 50, PAL.mint, 0.02);
      c.strokeStyle = K; c.lineWidth = 6; c.stroke(squigglePath(52, 190, 300, 12, 3, Math.PI / 2));
      confetti(c, r, [[860, 40], [960, 90], [1210, 260], [1240, 380], [1210, 520], [40, 60 + 560], [470, 690], [1240, 660], [760, 40]]);
    }
    GROUNDS[key] = L; return L;
  }


  const celTime = (t) => Math.floor(t * 12) / 12;
  function background(ctx, W, HH, scene = 1, grounds = null) {
    const colours = grounds || {
      1: [PAL.pink, PAL.mint], 2: [PAL.butter, PAL.lilac],
      3: [PAL.mint, PAL.pink], 4: [PAL.lilac, PAL.butter],
    }[scene] || [PAL.lilac, PAL.butter];
    ctx.drawImage(sceneGround(scene, colours, W, HH), 0, 0);
  }
  function bandSwipe(ctx, W, HH, progress) {
    const u = H.clamp(progress); if (u <= 0 || u >= 1) return;
    const x = H.lerp(-2300, W + 900, u);
    ctx.save(); ctx.translate(x, HH / 2); ctx.rotate(-0.35);
    const band = new Path2D(); band.rect(0, -1400, 1700, 2800);
    ctx.save(); ctx.translate(14, 14); ctx.fillStyle = K; ctx.fill(band); ctx.restore();
    ctx.save(); ctx.clip(band); const cols = [PAL.magenta, PAL.yellow, PAL.blue, PAL.mint, PAL.red];
    for (let i = 0; i < 20; i++) { ctx.fillStyle = cols[i % cols.length]; ctx.fillRect(i * 85, -1400, 86, 2800); ctx.fillStyle = K; for (let y = -1400; y < 1400; y += 40) { ctx.beginPath(); ctx.arc(i * 85 + 42, y + (i % 2) * 20, 5, 0, 7); ctx.fill(); } }
    ctx.restore(); ctx.lineWidth = 6; ctx.strokeStyle = K; ctx.stroke(band); ctx.restore();
  }
  function finish(ctx, W, HH, t) { H.grain(ctx, W, HH, 0.05, 6 + Math.floor(t * 12), true); }
  window.MEMPHIS = { K, PAL, solid, squigglePath, zigzagPath, strokeOutlined, terrazzo,
    roundRect, bubble, burst, fatArrow, face, tag, chunky, machine, confetti, dotCard,
    quarter, gridCard, sceneGround, celTime, background, bandSwipe, finish };
  window.STYLE = { fonts: ['400 92px "Rubik Mono One"', '700 28px "Fredoka"'], finish };
})();
