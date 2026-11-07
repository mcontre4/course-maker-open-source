// Rendering helpers and paper-age recipe extracted unchanged from the supplied reference.
(function () {
  // ---------- Lichtenstein pop-art comic panel ----------
  const C = { red: '#e2231a', blue: '#1f5fbf', yellow: '#ffd51f', black: '#141210', white: '#fbf6ea' };

  // Ben-Day dot field inside the current clip (staggered grid)
  const benday = (x, color, s, r, x0, y0, x1, y1, seed, rgain) => {
    const rr = H.rng(seed);
    x.fillStyle = color; x.beginPath();
    for (let j = 0, y = y0; y < y1 + s; j++, y += s * 0.5) {
      const off = (j & 1) ? s * 0.5 : 0;
      for (let xx = x0 + off; xx < x1 + s; xx += s) {
        const g = rgain ? rgain(xx, y) : 1;
        const rad = r * g * (1 + (rr() - 0.5) * 0.08);
        if (rad < 0.4) continue;
        const px = xx + (rr() - 0.5) * 0.6, py = y + (rr() - 0.5) * 0.6;
        x.moveTo(px + rad, py); x.arc(px, py, rad, 0, Math.PI * 2);
      }
    }
    x.fill();
  };

  // ---------- robot head geometry (local coords) ----------
  const headPath = (x) => {
    x.beginPath(); x.moveTo(-238, -70);
    x.bezierCurveTo(-240, -255, -125, -325, 0, -325);
    x.bezierCurveTo(125, -325, 240, -255, 238, -70);
    x.lineTo(228, 170); x.quadraticCurveTo(218, 262, 120, 292);
    x.lineTo(-120, 292); x.quadraticCurveTo(-218, 262, -228, 170); x.closePath();
  };
  const facePath = (x) => {
    x.beginPath(); x.moveTo(-180, -150);
    x.quadraticCurveTo(-182, -205, -120, -208); x.lineTo(120, -208); x.quadraticCurveTo(182, -205, 180, -150);
    x.lineTo(172, 150); x.quadraticCurveTo(165, 240, 80, 252); x.lineTo(-80, 252); x.quadraticCurveTo(-165, 240, -172, 150); x.closePath();
  };
  const eye = (x, cx, cy, sgn) => { x.beginPath(); x.ellipse(cx, cy, 64, 50, sgn * 0.08, 0, Math.PI * 2); };
  const tearPath = (x, cx, cy, s) => {
    x.beginPath(); x.moveTo(cx, cy - 46 * s);
    x.bezierCurveTo(cx + 8 * s, cy - 20 * s, cx + 26 * s, cy, cx + 26 * s, cy + 16 * s);
    x.arc(cx, cy + 16 * s, 26 * s, 0, Math.PI);
    x.bezierCurveTo(cx - 26 * s, cy, cx - 8 * s, cy - 20 * s, cx, cy - 46 * s); x.closePath();
  };
  const mouthPath = (x) => {
    x.beginPath(); x.moveTo(-78, 186); x.quadraticCurveTo(0, 150, 78, 186);
    x.lineTo(70, 216); x.quadraticCurveTo(0, 186, -70, 216); x.closePath();
  };

  const bubblePath = (x) => {
    x.beginPath();
    x.ellipse(330, 318, 262, 150, -0.04, 0.78, Math.PI * 2 + 0.5);
    x.lineTo(588, 600); x.closePath();
  };

  // ================= EXPLAINER: a comic page read panel by panel =================
  const PE = H.ease, pcl = H.clamp, pseg = (t, a, b) => pcl((t - a) / (b - a));
  const PPW = 1200, PPH = 660, PG = 44;
  const pX = (i) => i * (PPW + PG);

  // robot head drawn on colour (c) + key (k) plates; mood: think | eat | sad | happy
  const robot = (c, k, cx, cy, s, rot, mood, t, opt = {}) => {
    for (const [x, isKey] of [[c, false], [k, true]]) {
      x.save(); x.translate(cx, cy); x.rotate(rot); x.scale(s, s);
      x.lineJoin = 'round'; x.lineCap = 'round';
      if (!isKey) {
        x.fillStyle = C.yellow; headPath(x); x.fill();
        // orange Ben-Day shade band down the shell's right side (as in the hero still)
        x.save(); headPath(x); x.clip();
        x.beginPath(); x.moveTo(160, -320); x.bezierCurveTo(150, -150, 150, 60, 170, 320); x.lineTo(320, 320); x.lineTo(320, -320); x.closePath(); x.clip();
        benday(x, C.red, 12, 3.3, 100, -340, 320, 340, 12);
        x.restore();
        x.save(); facePath(x); x.clip(); x.fillStyle = C.white; x.fillRect(-300, -300, 600, 600); benday(x, C.red, 16, 3.7, -260, -260, 260, 300, 8); x.restore();
        x.fillStyle = C.white; x.beginPath(); x.moveTo(-226, -60); x.bezierCurveTo(-226, -200, -160, -270, -90, -300); x.bezierCurveTo(-150, -250, -196, -170, -200, -60); x.closePath(); x.fill();
        for (const [ex, sg] of [[-88, -1], [92, 1]]) { x.fillStyle = C.white; eye(x, ex, -30, sg); x.fill(); x.save(); eye(x, ex, -30, sg); x.clip(); x.fillStyle = C.blue; x.beginPath(); x.arc(ex + (opt.look || [8, -8])[0], -30 + (opt.look || [8, -8])[1], 34, 0, 7); x.fill(); x.restore(); }
        // blue-dot eye-shadow lids (Lichtenstein make-up, matches the hero)
        for (const [ex, sg] of [[-88, -1], [92, 1]]) {
          x.save(); x.beginPath(); x.ellipse(ex, -48, 74, 40, sg * 0.1, Math.PI, Math.PI * 2); x.closePath(); x.clip();
          x.fillStyle = C.white; x.fillRect(ex - 90, -120, 180, 70);
          benday(x, C.blue, 10, 3.4, ex - 100, -130, ex + 100, -40, 21 + ex);
          x.restore();
        }
        x.fillStyle = C.red; x.beginPath(); x.arc(0, -392, 30, 0, 7); x.fill();
        for (const sx of [-1, 1]) { x.beginPath(); x.arc(sx * 262, -10, 46, 0, 7); x.fill(); }
      } else {
        x.strokeStyle = C.black; x.fillStyle = C.black;
        x.lineWidth = 12; x.beginPath(); x.moveTo(0, -325); x.lineTo(0, -362); x.stroke();
        x.lineWidth = 9; x.beginPath(); x.arc(0, -392, 30, 0, 7); x.stroke();
        x.fillStyle = C.white; x.beginPath(); x.ellipse(-10, -402, 9, 6, -0.6, 0, 7); x.fill(); x.fillStyle = C.black;
        for (const sx of [-1, 1]) {
          x.lineWidth = 9; x.beginPath(); x.arc(sx * 262, -10, 46, 0, 7); x.stroke();
          x.lineWidth = 5; x.beginPath(); x.arc(sx * 262, -10, 22, 0, 7); x.stroke();
          const sp = opt.spin || 0; x.lineWidth = 8; x.beginPath(); x.moveTo(sx * 262 + Math.cos(sp) * 30, -10 + Math.sin(sp) * 30); x.lineTo(sx * 262 - Math.cos(sp) * 30, -10 - Math.sin(sp) * 30); x.stroke();
        }
        x.save(); headPath(x); x.clip();
        x.beginPath(); x.moveTo(252, -300); x.bezierCurveTo(222, -170, 214, 40, 226, 300); x.lineTo(320, 300); x.lineTo(320, -300); x.closePath(); x.fill();
        x.beginPath(); x.moveTo(-150, -296); x.bezierCurveTo(-60, -318, 70, -318, 150, -290); x.bezierCurveTo(70, -300, -50, -298, -150, -282); x.closePath(); x.fill();
        x.restore();
        // fat brush outlines, doubled with a slight offset like the hero's inking
        x.lineWidth = 13; headPath(x); x.stroke();
        x.save(); x.translate(5, 4); x.lineWidth = 10; headPath(x); x.stroke(); x.restore();
        x.lineWidth = 9; facePath(x); x.stroke();
        x.save(); x.translate(-4, 3); x.lineWidth = 6; facePath(x); x.stroke(); x.restore();
        for (const [rx, ry] of [[-208, -150], [-206, 100], [204, -150], [200, 100], [-60, -270], [60, -270]]) { x.beginPath(); x.arc(rx, ry, 7, 0, 7); x.fill(); }
        for (const [ex, sg] of [[-88, -1], [92, 1]]) {
          const lk = opt.look || [8, -8];
          x.lineWidth = 8; eye(x, ex, -30, sg); x.stroke();
          x.save(); eye(x, ex, -30, sg); x.clip(); x.beginPath(); x.arc(ex + lk[0], -30 + lk[1], 15, 0, 7); x.fill();
          x.fillStyle = C.white; x.beginPath(); x.ellipse(ex + lk[0] - 14, -30 + lk[1] - 16, 10, 7, -0.5, 0, 7); x.fill(); x.fillStyle = C.black; x.restore();
        }
        // brows by mood
        const browY = mood === 'happy' ? -128 : -118;
        for (const sg of [-1, 1]) {
          x.lineWidth = 14; x.beginPath();
          if (mood === 'sad') { x.moveTo(sg * 165, -100); x.quadraticCurveTo(sg * 100, -150, sg * 36, -150); }
          else if (mood === 'think' && sg > 0) { x.moveTo(36, -150); x.quadraticCurveTo(100, -175, 165, -140); }
          else { x.moveTo(sg * 160, browY + 10); x.quadraticCurveTo(sg * 100, browY - 18, sg * 40, browY); }
          x.stroke();
        }
        // mouth
        x.lineWidth = 12;
        if (mood === 'happy') { x.beginPath(); x.moveTo(-80, 160); x.quadraticCurveTo(0, 235, 80, 160); x.quadraticCurveTo(0, 200, -80, 160); x.fill(); x.stroke(); }
        else if (mood === 'eat') { const o = 30 + 16 * Math.abs(Math.sin(t * 9)); x.beginPath(); x.ellipse(0, 180, 60, o, 0, 0, 7); x.fill(); }
        else if (mood === 'sad') { mouthPath(x); x.fill(); }
        else { x.beginPath(); x.moveTo(-60, 185); x.lineTo(50, 175); x.stroke(); }
      }
      x.restore();
    }
  };

  // comic devices
  const box = (c, k, x0, y0, w, h, fill, txt, size, t0, t) => {
    if (t < t0) return;
    const u = PE.back(pseg(t, t0, t0 + 0.25)), dx = (1 - u) * -w;
    c.fillStyle = fill; c.fillRect(x0 + dx, y0, w, h);
    k.lineWidth = 6; k.strokeStyle = C.black; k.strokeRect(x0 + dx, y0, w, h);
    k.fillStyle = C.black; k.font = `400 ${size}px "Bangers"`; k.letterSpacing = '1.5px'; k.textAlign = 'left'; k.textBaseline = 'middle';
    k.fillText(txt, x0 + dx + 16, y0 + h / 2 + 2); k.letterSpacing = '0px';
  };
  const balloon = (c, k, cx, cy, rx, ry, tx, ty, sc) => {
    if (sc <= 0) return;
    const path = (x) => { x.beginPath(); x.ellipse(cx, cy, rx, ry, 0, 0, 7); };
    const tail = (x) => { const a = Math.atan2(ty - cy, tx - cx); x.beginPath(); x.moveTo(cx + Math.cos(a - 0.22) * rx * 0.9, cy + Math.sin(a - 0.22) * ry * 0.9); x.lineTo(tx, ty); x.lineTo(cx + Math.cos(a + 0.22) * rx * 0.9, cy + Math.sin(a + 0.22) * ry * 0.9); x.closePath(); };
    for (const x of [c, k]) { x.save(); x.translate(cx, cy); x.scale(sc, sc); x.translate(-cx, -cy); }
    k.lineWidth = 8; k.strokeStyle = C.black; tail(k); k.stroke(); path(k); k.stroke();
    c.fillStyle = C.white; path(c); c.fill(); tail(c); c.fill();
    k.fillStyle = '#fff'; k.save(); k.globalCompositeOperation = 'destination-out'; path(k); k.fill(); k.restore();
    k.fillStyle = C.black; k.lineWidth = 8;
    // re-stroke ellipse (tail join hidden by fill)
    path(k); k.stroke();
    k.save(); k.globalCompositeOperation = 'destination-out'; k.beginPath(); k.ellipse(cx, cy, rx - 4, ry - 4, 0, 0, 7); k.fill(); k.restore();
    for (const x of [c, k]) x.restore();
  };
  const burstPath = (x, cx, cy, r, n, seed) => { const rr = H.rng(seed); x.beginPath(); for (let i = 0; i < n * 2; i++) { const a = (i / (n * 2)) * Math.PI * 2, R = i % 2 ? r * rr.range(0.6, 0.72) : r * rr.range(0.92, 1.12); x.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R); } x.closePath(); };
  const burst = (c, k, cx, cy, r, sc, fill, seed) => {
    if (sc <= 0) return;
    c.fillStyle = fill; burstPath(c, cx, cy, r * sc, 14, seed); c.fill();
    k.lineWidth = 8; k.strokeStyle = C.black; k.lineJoin = 'miter'; burstPath(k, cx, cy, r * sc, 14, seed); k.stroke(); k.lineJoin = 'round';
  };
  const say = (k, txt, size, x, y, sc = 1, align = 'center', rot = 0) => {
    if (sc <= 0) return;
    k.save(); k.translate(x, y); k.rotate(rot); k.scale(sc, sc); k.fillStyle = C.black; k.font = `400 ${size}px "Bangers"`; k.letterSpacing = '2px'; k.textAlign = align; k.textBaseline = 'middle'; k.fillText(txt, 0, 0); k.letterSpacing = '0px'; k.restore();
  };
  // lettering knocked out of whatever is behind it: a white halo on both plates (breaks dots, arrow fills and key lines)
  const sayK = (c, k, txt, size, x, y, sc = 1, align = 'center', rot = 0, halo = 12) => {
    if (sc <= 0) return;
    for (const x_ of [c, k]) {
      x_.save(); x_.translate(x, y); x_.rotate(rot); x_.scale(sc, sc); x_.font = `400 ${size}px "Bangers"`; x_.letterSpacing = '2px'; x_.textAlign = align; x_.textBaseline = 'middle';
      x_.lineJoin = 'round'; x_.lineWidth = halo; x_.strokeStyle = C.white; x_.strokeText(txt, 0, 0); x_.letterSpacing = '0px'; x_.restore();
    }
    say(k, txt, size, x, y, sc, align, rot);
  };
  const popIn = (t, t0) => (t < t0 ? 0 : 1 + 0.3 * (1 - PE.out(pseg(t, t0, t0 + 0.16))) * (t - t0 < 0.16 ? 1 : 0));
  // fat comic arrow along a quadratic, drawn on with progress u (yellow fill, black outline)
  const fatArrow = (c, k, p0, cp, p1, u, w, fill) => {
    if (u <= 0) return;
    const q = (s) => [(1 - s) * (1 - s) * p0[0] + 2 * (1 - s) * s * cp[0] + s * s * p1[0], (1 - s) * (1 - s) * p0[1] + 2 * (1 - s) * s * cp[1] + s * s * p1[1]];
    const N = 24, L = [], R = [], end = u * 0.86;
    for (let i = 0; i <= N; i++) { const s = (i / N) * end, a = q(s), b = q(Math.min(1, s + 0.01)); let dx = b[0] - a[0], dy = b[1] - a[1]; const l = Math.hypot(dx, dy) || 1; dx /= l; dy /= l; const ww = w * (0.6 + 0.4 * (i / N)) / 2; L.push([a[0] - dy * ww, a[1] + dx * ww]); R.push([a[0] + dy * ww, a[1] - dx * ww]); }
    const e = q(end), tip = q(Math.min(1, end + 0.14)); let dx = tip[0] - e[0], dy = tip[1] - e[1]; const l = Math.hypot(dx, dy) || 1; dx /= l; dy /= l;
    const hw = w * 1.1;
    const path = (x) => { x.beginPath(); x.moveTo(L[0][0], L[0][1]); L.forEach((p) => x.lineTo(p[0], p[1])); x.lineTo(e[0] - dy * hw, e[1] + dx * hw); x.lineTo(tip[0], tip[1]); x.lineTo(e[0] + dy * hw, e[1] - dx * hw); for (let i = R.length - 1; i >= 0; i--) x.lineTo(R[i][0], R[i][1]); x.closePath(); };
    c.fillStyle = fill; path(c); c.fill(); k.lineWidth = 6; k.strokeStyle = C.black; k.lineJoin = 'round'; path(k); k.stroke();
    return q(0.5);
  };
  // labelled training photo (comic style)
  const photo = (c, k, cx, cy, s, kind, label, rot) => {
    for (const x of [c, k]) { x.save(); x.translate(cx, cy); x.rotate(rot); x.scale(s / 100, s / 100); }
    c.fillStyle = C.white; c.fillRect(-50, -60, 100, 120); c.fillStyle = C.yellow; c.fillRect(-50, 30, 100, 30);
    benday(c, C.blue, 9, 2.4, -46, -56, 46, 24, 4);
    c.fillStyle = C.white; c.beginPath(); c.arc(0, -16, 30, 0, 7); c.fill();
    k.lineWidth = 4; k.strokeStyle = C.black; k.fillStyle = C.black; k.strokeRect(-50, -60, 100, 120); k.beginPath(); k.moveTo(-50, 30); k.lineTo(50, 30); k.stroke();
    k.lineWidth = 3.5; k.beginPath(); k.arc(0, -16, 28, 0, 7); k.stroke();
    if (kind === 'cat') { k.beginPath(); k.moveTo(-24, -28); k.lineTo(-22, -54); k.lineTo(-6, -42); k.moveTo(24, -28); k.lineTo(22, -54); k.lineTo(6, -42); k.stroke(); k.beginPath(); for (const sg of [-1, 1]) { k.moveTo(sg * 8, -8); k.lineTo(sg * 38, -10); k.moveTo(sg * 8, -4); k.lineTo(sg * 36, 0); } k.stroke(); }
    else { for (const sg of [-1, 1]) { k.beginPath(); k.ellipse(sg * 28, -14, 8, 18, sg * 0.4, 0, 7); k.fill(); } k.beginPath(); k.ellipse(0, -6, 6, 4, 0, 0, 7); k.fill(); }
    k.beginPath(); k.arc(-9, -20, 3.2, 0, 7); k.arc(9, -20, 3.2, 0, 7); k.fill();
    k.font = '400 26px "Bangers"'; k.textAlign = 'center'; k.textBaseline = 'middle'; k.fillText(label, 0, 46);
    for (const x of [c, k]) x.restore();
  };
  const speedLines = (k, x0, y0, len, n, seed) => { const r = H.rng(seed); k.lineWidth = 3; k.strokeStyle = C.black; k.lineCap = 'round'; for (let i = 0; i < n; i++) { const yy = y0 + r.range(-50, 50), l = len * r.range(0.5, 1); k.beginPath(); k.moveTo(x0 - 70, yy); k.lineTo(x0 - 70 - l, yy); k.stroke(); } };

  const panel = (c, k, i, t, bg) => {
    const x0 = pX(i);
    c.save(); c.translate(x0, 0); c.beginPath(); c.rect(0, 0, PPW, PPH); c.clip();
    k.save(); k.translate(x0, 0); k.beginPath(); k.rect(0, 0, PPW, PPH); k.clip();
    bg(c, k);
    return () => { c.restore(); k.restore(); k.save(); k.translate(x0, 0); k.lineWidth = 9; k.strokeStyle = C.black; k.strokeRect(0, 0, PPW, PPH); k.restore(); };
  };
  const fmtN = (n) => Math.round(n).toLocaleString('en-US');

  let ageCache = null;
  const paperAge = (W, H_) => {
    if (ageCache && ageCache.W === W && ageCache.H === H_) return ageCache;
    const nz = H.makeNoise(41), LW = 160, LH = 90;
    const lo = H.layer(LW, LH), lx = lo.getContext('2d'), li = lx.createImageData(LW, LH);
    for (let y = 0; y < LH; y++) for (let x = 0; x < LW; x++) { const i = (y * LW + x) * 4; li.data[i] = 128 + 127 * nz.fbm2(x * 0.06, y * 0.06, 3); li.data[i + 3] = 255; }
    lx.putImageData(li, 0, 0);
    const big = H.layer(W, H_), bx = big.getContext('2d'); bx.drawImage(lo, 0, 0, W, H_);
    const lf = bx.getImageData(0, 0, W, H_).data, r = H.rng(5), N = W * H_;
    const R = new Float32Array(N), G = new Float32Array(N), B = new Float32Array(N);
    for (let y = 0, p = 0; y < H_; y++) for (let x = 0; x < W; x++, p++) {
      const n = (lf[p * 4] - 128) / 128, g = r() - 0.5, ex = Math.min(x, W - x, y, H_ - y);
      const age = 1 - 0.06 * (1 - H.smooth(0, 160, ex)) - 0.025 * n;
      R[p] = age * (1 + g * 0.05); G[p] = (age - 0.01) * (1 + g * 0.05); B[p] = (age - 0.045) * (1 + g * 0.06);
    }
    return (ageCache = { W, H: H_, r: R, g: G, b: B });
  };

  function plates(W, H_) {
    const col = H.layer(W, H_), key = H.layer(W, H_);
    const c = col.getContext('2d'), k = key.getContext('2d');
    c.fillStyle = C.white; c.fillRect(0, 0, W, H_);
    return { col, key, c, k };
  }
  function composite(ctx, col, key, W, H_) {
    ctx.fillStyle = C.white; ctx.fillRect(0, 0, W, H_);
    ctx.drawImage(col, 2.5, -1.5);
    ctx.globalCompositeOperation = 'multiply'; ctx.drawImage(key, 0, 0); ctx.globalCompositeOperation = 'source-over';
  }
  function finish(ctx, W, H_, t) {
    const A = paperAge(W, H_), img = ctx.getImageData(0, 0, W, H_), d = img.data;
    for (let i = 0, p = 0; i < d.length; i += 4, p++) { d[i] *= A.r[p]; d[i + 1] *= A.g[p]; d[i + 2] *= A.b[p]; }
    ctx.putImageData(img, 0, 0);
  }
  window.HP = { C, benday, PE, pcl, pseg, PPW, PPH, PG, pX, robot, box, balloon,
    burstPath, burst, say, sayK, popIn, fatArrow, photo, speedLines, panel, fmtN,
    paperAge, plates, composite, finish };
  window.STYLE = { fonts: ['400 66px "Bangers"', '400 30px "Bangers"'], finish };
})();
