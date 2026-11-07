// Marker and surface recipes extracted unchanged from the supplied Whiteboard reference.
(function () {
  const seg = (pts, step = 2.5) => {
    const out = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i], [x1, y1] = pts[i + 1];
      const n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / step));
      for (let j = 0; j < n; j++) out.push([x0 + (x1 - x0) * j / n, y0 + (y1 - y0) * j / n]);
    }
    out.push(pts[pts.length - 1]);
    return out;
  };
  const normals = (P) => P.map((p, i) => {
    const a = P[Math.max(0, i - 1)], b = P[Math.min(P.length - 1, i + 1)];
    const dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 1;
    return [-dy / d, dx / d];
  });
  const wobble = (pts, nz, seed, amp = 1.6, freq = 0.011) => {
    const N = normals(pts); let L = 0;
    return pts.map((p, i) => {
      if (i) L += Math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]);
      const o = nz.n2(L * freq + seed * 1.37, seed * 0.71) * amp + nz.n2(L * freq * 6 + seed, seed + 3.3) * amp * 0.25;
      return [p[0] + N[i][0] * o, p[1] + N[i][1] * o];
    });
  };
  const ell = (cx, cy, rx, ry, a0 = 0, a1 = Math.PI * 2, grow = 0) => {
    const n = Math.max(10, Math.ceil(Math.abs(a1 - a0) * Math.max(rx, ry) / 2.5)), out = [];
    for (let i = 0; i <= n; i++) {
      const u = i / n, a = a0 + (a1 - a0) * u, g = 1 + grow * u;
      out.push([cx + Math.cos(a) * rx * g, cy + Math.sin(a) * ry * g]);
    }
    return out;
  };
  const bez = (p0, p1, p2, p3) => {
    const out = [];
    for (let i = 0; i <= 60; i++) {
      const t = i / 60, m = 1 - t;
      out.push([m * m * m * p0[0] + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t * t * t * p3[0],
        m * m * m * p0[1] + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t * t * t * p3[1]]);
    }
    return out;
  };
  const tracePath = (ctx, P) => { ctx.beginPath(); P.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]))); };

  // A dry-erase marker stroke: lighter wet center, darker pooled edges, streaky dry lines.
  const BOARD = [236, 240, 239];
  const MN = H.makeNoise(4242);
  let TIP = null; // where the marker tip currently is (during the build)
  const marker = (ctx, pts, col, w, seed, prog = 1) => {
    if (prog <= 0) return;
    if (prog < 1) { const q = pts[Math.max(1, Math.ceil(pts.length * prog)) - 1]; TIP = [q[0], q[1], col]; }
    const P = prog < 1 ? pts.slice(0, Math.max(2, Math.ceil(pts.length * prog))) : pts;
    const r = H.rng(seed), rgb = H.hex(col), N = normals(P);
    ctx.save(); ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.strokeStyle = H.rgba(rgb, 0.3); ctx.lineWidth = w; tracePath(ctx, P); ctx.stroke();
    ctx.lineCap = 'butt';
    // body ink density drifts along the stroke (wetter / drier patches)
    const CH = 10;
    for (let i = 0; i < P.length - 1; i += CH) {
      const a = 0.16 + 0.22 * (0.5 + 0.5 * MN.n2(i * 0.03 + seed * 3.1, seed * 0.37));
      ctx.strokeStyle = H.rgba(rgb, a); ctx.lineWidth = w * 0.96;
      ctx.beginPath(); ctx.moveTo(P[i][0], P[i][1]);
      for (let j = i + 1; j <= Math.min(P.length - 1, i + CH); j++) ctx.lineTo(P[j][0], P[j][1]);
      ctx.stroke();
    }
    const n = 7;
    for (let k = 0; k < n; k++) {
      const u = k / (n - 1) - 0.5, edge = Math.abs(u) * 2;
      const a = (0.08 + 0.5 * Math.pow(edge, 2.2)) * (0.65 + r() * 0.7);
      ctx.strokeStyle = H.rgba(rgb, a); ctx.lineWidth = (w / n) * 1.5;
      const off = u * w * 0.84;
      ctx.beginPath();
      P.forEach((p, i) => { const x = p[0] + N[i][0] * off, y = p[1] + N[i][1] * off; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.stroke();
    }
    // dry streaks where the felt tip skipped
    for (let k = 0; k < 4; k++) {
      const off = (r() - 0.5) * w * 0.6;
      ctx.strokeStyle = H.rgba(BOARD, 0.14 + r() * 0.2); ctx.lineWidth = 0.6 + r() * 0.6;
      const s = Math.floor(r() * P.length * 0.4), e = Math.min(P.length, s + Math.floor(P.length * (0.3 + r() * 0.6)));
      ctx.beginPath();
      for (let i = s; i < e; i++) { const x = P[i][0] + N[i][0] * off, y = P[i][1] + N[i][1] * off; i > s ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
      ctx.stroke();
    }
    // ink pools where the tip lands and lifts
    [P[0], prog >= 1 ? P[P.length - 1] : null].forEach((p, j) => {
      if (!p) return;
      const g = ctx.createRadialGradient(p[0], p[1], 0, p[0], p[1], w * 0.62);
      g.addColorStop(0, H.rgba(rgb, j ? 0.25 : 0.42)); g.addColorStop(1, H.rgba(rgb, 0));
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p[0], p[1], w * 0.62, 0, 7); ctx.fill();
    });
    ctx.restore();
  };

  // Marker lettering: per-glyph jitter, pale centers with darker rims.
  const mText = (ctx, str, x, y, font, col, seed, prog = 1, rot = 0) => {
    if (prog <= 0) return;
    const r = H.rng(seed), rgb = H.hex(col);
    ctx.save(); ctx.font = font; ctx.textBaseline = 'alphabetic';
    ctx.translate(x, y); ctx.rotate(rot);
    const nChars = Math.ceil(str.length * prog);
    if (prog < 1) {
      const wsofar = ctx.measureText(str.slice(0, nChars)).width;
      TIP = [x + Math.cos(rot) * wsofar, y + Math.sin(rot) * wsofar - 10, col];
    }
    let cx = 0;
    for (let i = 0; i < nChars; i++) {
      const ch = str[i], wch = ctx.measureText(ch).width;
      ctx.save(); ctx.translate(cx + wch / 2, (r() - 0.5) * 3); ctx.rotate((r() - 0.5) * 0.07);
      ctx.fillStyle = H.rgba(rgb, 0.8 + r() * 0.1); ctx.fillText(ch, -wch / 2, 0);
      ctx.strokeStyle = H.rgba(rgb, 0.7); ctx.lineWidth = 1.3; ctx.strokeText(ch, -wch / 2, 0);
      ctx.restore();
      cx += wch + (r() - 0.5) * 1.5;
    }
    ctx.restore();
  };

  const XC = {};
  // Ghost residue of earlier lessons on the explainer's big board: baked once (world space, half resolution)
  // with the hero's streaky eraser-wipe mask and haze, then simply drawn under the live diagram.
  const ghostBoard = () => {
    if (XC.ghost) return XC.ghost;
    const x0 = -200, y0 = -100, w = 3600, h = 1400, s = 0.5;
    const nz = H.makeNoise(23);
    const g = H.layer(w * s, h * s), gc = g.getContext('2d');
    gc.scale(s, s); gc.translate(-x0, -y0);
    gc.strokeStyle = '#30343c'; gc.fillStyle = '#30343c'; gc.lineCap = 'round'; gc.lineJoin = 'round'; gc.lineWidth = 7;
    const wl = (pts, sd, amp = 1.8) => { tracePath(gc, wobble(seg(pts), nz, sd, amp)); gc.stroke(); };
    // A: an old quiz list (top right of the opening view)
    gc.font = '400 52px "Permanent Marker"'; gc.fillText('WEEK 6 QUIZ', 850, 118);
    gc.font = '700 34px "Kalam"';
    ['- read ch. 4', '- lab due Fri', '- bring calc!'].forEach((t, i) => gc.fillText(t, 872, 182 + i * 44));
    wl([[840, 138], [1020, 135], [1210, 132]], 1);
    // B: a pie and a wobbly line chart (bottom left of the opening view)
    gc.beginPath(); gc.arc(190, 588, 72, 0, 7); gc.stroke();
    gc.beginPath(); gc.moveTo(190, 588); gc.lineTo(190, 516); gc.moveTo(190, 588); gc.lineTo(252, 626); gc.stroke();
    wl([[300, 660], [360, 600], [420, 630], [520, 540]], 2);
    gc.font = '700 30px "Kalam"'; gc.fillText('sales / mo', 330, 694);
    // C: a formula above the example cards
    gc.font = '400 40px "Permanent Marker"'; gc.fillText('f(x) = w·x + b', 1740, 830);
    wl([[1730, 850], [1890, 846], [2030, 852]], 3, 1.4);
    // D: a little box diagram, top right of the loop view
    gc.beginPath(); gc.rect(3070, 300, 150, 80); gc.stroke();
    wl([[3010, 340], [3062, 340]], 4, 0.8);
    gc.font = '700 30px "Kalam"'; gc.fillText('step 2', 3100, 350);
    // E: homework note under the takeaway
    gc.font = '400 44px "Permanent Marker"'; gc.fillText('HW: p. 112', 2180, 1086);
    gc.beginPath(); gc.rect(2560, 1030, 200, 84); gc.stroke();
    wl([[2470, 1070], [2550, 1072]], 5, 0.8);
    gc.font = '700 30px "Kalam"'; gc.fillText('#3, #7', 2800, 1084);
    // eraser-wipe mask: the residue survives only in streaky swipe bands
    const m = H.layer(w * s, h * s), mc = m.getContext('2d'), rm = H.rng(77);
    mc.scale(s, s); mc.translate(-x0, -y0); mc.lineCap = 'round';
    for (let i = 0; i < 230; i++) {
      const y = rm.range(0, 1250), x = rm.range(-150, 3300), len = rm.range(150, 420);
      mc.strokeStyle = `rgba(0,0,0,${rm.range(0.15, 0.8)})`; mc.lineWidth = rm.range(4, 26);
      mc.beginPath(); mc.moveTo(x, y); mc.quadraticCurveTo(x + len / 2, y + rm.range(-30, 30), x + len, y + rm.range(-18, 18)); mc.stroke();
    }
    gc.setTransform(1, 0, 0, 1, 0, 0); gc.globalCompositeOperation = 'destination-in'; gc.drawImage(m, 0, 0);
    const cv = H.layer(w * s, h * s), c = cv.getContext('2d');
    c.filter = 'blur(0.5px)'; c.globalAlpha = 0.12; c.drawImage(g, 0, 0); c.globalAlpha = 1;
    // grey eraser haze smeared over each old lesson
    const rh = H.rng(78);
    c.scale(s, s); c.translate(-x0, -y0); c.lineCap = 'round'; c.filter = 'blur(3px)';
    [[1040, 180, 200, 70], [330, 600, 200, 80], [1880, 820, 160, 30], [3140, 340, 90, 40], [2470, 1070, 330, 40]].forEach(([cx, cy, rx, ry]) => {
      for (let i = 0; i < 4; i++) {
        const x = cx + rh.range(-rx, rx) * 0.6, y = cy + rh.range(-ry, ry);
        c.strokeStyle = `rgba(120,128,135,${rh.range(0.014, 0.03)})`; c.lineWidth = rh.range(30, 60);
        c.beginPath(); c.moveTo(x - 120, y); c.quadraticCurveTo(x, y + rh.range(-25, 25), x + 120, y + rh.range(-10, 10)); c.stroke();
      }
    });
    const out = { cv, x0, y0, w, h };
    let ready = true;
    try { ready = document.fonts.check('400 52px "Permanent Marker"') && document.fonts.check('700 34px "Kalam"'); } catch (e) { /* assume ready */ }
    if (ready) XC.ghost = out;
    return out;
  };
  // Streaky felt-eraser brush: a soft base wipe plus felt-fibre bands, so the residue left behind varies
  // across the swipe (clean bands next to faint ghost bands) like a real dry-erase felt.
  const FIBRES = (() => {
    const r = H.rng(313), out = [];
    for (let i = 0; i < 16; i++) out.push({ dy: (r() - 0.5) * 118, w: 5 + r() * 14, a: 0.45 + r() * 0.5 });
    return out;
  })();
  function beginFrame() { TIP = null; }
  function tip() { return TIP; }
  function background(ctx, W, H_, t) {
    const BX0 = 26, BY0 = 26, BX1 = W - 26, BY1 = 650;
      const bg = ctx.createLinearGradient(0, 0, W, H_);
      bg.addColorStop(0, '#f6f8f7'); bg.addColorStop(0.55, '#ecefee'); bg.addColorStop(1, '#dfe4e3');
      ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H_);
      // faint large mottling (old cleaner residue)
      const rb = H.rng(5);
      for (let i = 0; i < 14; i++) {
        const x = rb.range(BX0, BX1), y = rb.range(BY0, BY1), rr = rb.range(80, 260);
        const g = ctx.createRadialGradient(x, y, 0, x, y, rr);
        g.addColorStop(0, `rgba(150,160,165,${rb.range(0.015, 0.04)})`); g.addColorStop(1, 'rgba(150,160,165,0)');
        ctx.fillStyle = g; ctx.fillRect(x - rr, y - rr, rr * 2, rr * 2);
      }

  }
  function gloss(ctx, W, H_, t) {
    const BY1 = 650;
      ctx.save();
      const sh = ctx.createLinearGradient(220 + t * 6, -60, 760 + t * 6, 760);
      sh.addColorStop(0.0, 'rgba(255,255,255,0)');
      sh.addColorStop(0.36, 'rgba(255,255,255,0)');
      sh.addColorStop(0.43, 'rgba(255,255,255,0.26)');
      sh.addColorStop(0.47, 'rgba(255,255,255,0.12)');
      sh.addColorStop(0.5, 'rgba(255,255,255,0.3)');
      sh.addColorStop(0.58, 'rgba(255,255,255,0)');
      sh.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = sh; ctx.fillRect(0, 0, W, H_);
      // ceiling light reflections
      [[380, 70, 260, 26], [930, 66, 230, 22]].forEach(([x, y, rx, ry]) => {
        ctx.save(); ctx.translate(x, y); ctx.scale(1, ry / rx);
        const g = ctx.createRadialGradient(0, 0, 0, 0, 0, rx);
        g.addColorStop(0, 'rgba(255,255,255,0.55)'); g.addColorStop(0.5, 'rgba(255,255,255,0.18)'); g.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, rx, 0, 7); ctx.fill(); ctx.restore();
      });
      // darker falloff at bottom of board
      const fo = ctx.createLinearGradient(0, BY1 - 200, 0, BY1);
      fo.addColorStop(0, 'rgba(60,70,80,0)'); fo.addColorStop(1, 'rgba(60,70,80,0.07)');
      ctx.fillStyle = fo; ctx.fillRect(0, BY1 - 200, W, 200);
      ctx.restore();

  }
  function finish(ctx, W, H_, t) {
    gloss(ctx, W, H_, t);
    H.grain(ctx, W, H_, 0.018, 9 + (Math.floor(t * 12) % 5));
  }
  window.WB = { BOARD, MN, seg, normals, wobble, ell, bez, tracePath, marker, mText,
    ghostBoard, FIBRES, background, gloss, beginFrame, tip, finish };
  window.STYLE = { fonts: ['400 66px "Permanent Marker"', '700 38px "Kalam"',
    '400 40px "Permanent Marker"'], beginFrame, finish };
})();
