// Rendering helpers extracted unchanged from the supplied Tech Glow reference.
(function () {
  const E = H.ease, cl = H.clamp, lerp = H.lerp;
  const seg = (a, b, t) => cl((t - a) / (b - a));
  const eo = (a, b, t) => E.out(seg(a, b, t));
  const eio = (a, b, t) => E.inOut(seg(a, b, t));
  const ebk = (a, b, t) => (t <= a ? 0 : t >= b ? 1 : E.back(seg(a, b, t)));
  const fract = (x) => x - Math.floor(x);
  const rgb = (c, a) => H.rgba(c, a);
  const HEAD = '"Space Grotesk"', UI = '"Inter"';
  const F = (w, s, fam) => `${w} ${s}px ${fam || HEAD}`;
  const C = {
    cyan: '#3fe3ff', blue: '#3d7bff', violet: '#8f5bff', magenta: '#e04dff', indigo: '#4b3bff',
    red: '#ff4f7a', green: '#3cf0b4', white: '#eef2ff', muted: '#9aa3d8',
  };
  const GRAD_HEAD = ['#ffffff', '#c8f4ff', '#7fdcff', '#9a78ff'];
  const GRAD_NUM = ['#7ff0ff', '#5d9bff', '#a77bff'];
  const rr = (c, x, y, w, h, r) => { c.beginPath(); c.roundRect(x, y, w, h, r); };
  const bump = (t, t0, k = 6) => (t < t0 ? 0 : Math.exp(-(t - t0) * k)); // decaying flash after t0

  // ---------------------------------------------------------------- icons (line art in a -1..1 box scaled by u)
  const dot = (c, x, y, r) => { c.moveTo(x + r, y); c.arc(x, y, r, 0, Math.PI * 2); };
  const ICONS = {
    brain(c, u) {
      for (const sx of [-1, 1]) {
        const X = (v) => v * u * sx, Y = (v) => v * u;
        c.moveTo(X(0.04), Y(-0.78));
        c.bezierCurveTo(X(0.3), Y(-0.98), X(0.64), Y(-0.84), X(0.64), Y(-0.52));
        c.bezierCurveTo(X(0.95), Y(-0.42), X(0.98), Y(-0.02), X(0.74), Y(0.08));
        c.bezierCurveTo(X(0.95), Y(0.32), X(0.82), Y(0.7), X(0.5), Y(0.68));
        c.bezierCurveTo(X(0.4), Y(0.92), X(0.12), Y(0.92), X(0.04), Y(0.74));
        c.lineTo(X(0.04), Y(-0.78));
        c.moveTo(X(0.64), Y(-0.52)); c.quadraticCurveTo(X(0.46), Y(-0.5), X(0.36), Y(-0.34));
        c.moveTo(X(0.74), Y(0.08)); c.quadraticCurveTo(X(0.52), Y(0.1), X(0.42), Y(-0.08));
        c.moveTo(X(0.5), Y(0.68)); c.quadraticCurveTo(X(0.5), Y(0.42), X(0.3), Y(0.34));
        c.moveTo(X(0.04), Y(-0.16)); c.quadraticCurveTo(X(0.22), Y(-0.18), X(0.26), Y(0.02));
      }
    },
    chip(c, u) {
      c.roundRect(-0.58 * u, -0.58 * u, 1.16 * u, 1.16 * u, 0.16 * u);
      c.roundRect(-0.26 * u, -0.26 * u, 0.52 * u, 0.52 * u, 0.06 * u);
      for (const k of [-0.3, 0, 0.3]) {
        c.moveTo(k * u, -0.58 * u); c.lineTo(k * u, -0.86 * u); c.moveTo(k * u, 0.58 * u); c.lineTo(k * u, 0.86 * u);
        c.moveTo(-0.58 * u, k * u); c.lineTo(-0.86 * u, k * u); c.moveTo(0.58 * u, k * u); c.lineTo(0.86 * u, k * u);
      }
    },
    database(c, u) {
      c.moveTo(0.64 * u, -0.56 * u); c.ellipse(0, -0.56 * u, 0.64 * u, 0.2 * u, 0, 0, Math.PI * 2);
      c.moveTo(-0.64 * u, -0.56 * u); c.lineTo(-0.64 * u, 0.56 * u); c.moveTo(0.64 * u, -0.56 * u); c.lineTo(0.64 * u, 0.56 * u);
      c.moveTo(0.64 * u, 0.56 * u); c.ellipse(0, 0.56 * u, 0.64 * u, 0.2 * u, 0, 0, Math.PI);
      c.moveTo(0.64 * u, 0); c.ellipse(0, 0, 0.64 * u, 0.2 * u, 0, 0, Math.PI);
    },
    chat(c, u) {
      c.moveTo(-0.5 * u, -0.66 * u); c.lineTo(0.5 * u, -0.66 * u); c.quadraticCurveTo(0.82 * u, -0.66 * u, 0.82 * u, -0.34 * u);
      c.lineTo(0.82 * u, 0.12 * u); c.quadraticCurveTo(0.82 * u, 0.44 * u, 0.5 * u, 0.44 * u); c.lineTo(-0.1 * u, 0.44 * u);
      c.lineTo(-0.48 * u, 0.8 * u); c.lineTo(-0.44 * u, 0.44 * u); c.quadraticCurveTo(-0.82 * u, 0.44 * u, -0.82 * u, 0.12 * u);
      c.lineTo(-0.82 * u, -0.34 * u); c.quadraticCurveTo(-0.82 * u, -0.66 * u, -0.5 * u, -0.66 * u);
      for (const x of [-0.36, 0, 0.36]) dot(c, x * u, -0.11 * u, 0.05 * u);
    },
    sparkle(c, u) {
      const star = (x, y, r) => { c.moveTo(x, y - r); c.quadraticCurveTo(x, y, x + r, y); c.quadraticCurveTo(x, y, x, y + r); c.quadraticCurveTo(x, y, x - r, y); c.quadraticCurveTo(x, y, x, y - r); };
      star(-0.14 * u, 0.12 * u, 0.72 * u); star(0.56 * u, -0.56 * u, 0.26 * u);
    },
    eye(c, u) {
      c.moveTo(-0.88 * u, 0); c.quadraticCurveTo(0, -0.84 * u, 0.88 * u, 0); c.quadraticCurveTo(0, 0.84 * u, -0.88 * u, 0);
      dot(c, 0, 0, 0.3 * u); dot(c, 0, 0, 0.07 * u);
    },
    check(c, u) { c.moveTo(-0.58 * u, 0.02 * u); c.lineTo(-0.16 * u, 0.44 * u); c.lineTo(0.62 * u, -0.42 * u); },
    cross(c, u) { c.moveTo(-0.45 * u, -0.45 * u); c.lineTo(0.45 * u, 0.45 * u); c.moveTo(0.45 * u, -0.45 * u); c.lineTo(-0.45 * u, 0.45 * u); },
    cat(c, u) {
      c.moveTo(-0.6 * u, -0.08 * u); c.lineTo(-0.62 * u, -0.78 * u); c.lineTo(-0.24 * u, -0.48 * u);
      c.quadraticCurveTo(0, -0.56 * u, 0.24 * u, -0.48 * u); c.lineTo(0.62 * u, -0.78 * u); c.lineTo(0.6 * u, -0.08 * u);
      c.bezierCurveTo(0.62 * u, 0.52 * u, 0.3 * u, 0.72 * u, 0, 0.72 * u); c.bezierCurveTo(-0.3 * u, 0.72 * u, -0.62 * u, 0.52 * u, -0.6 * u, -0.08 * u);
      dot(c, -0.25 * u, 0.02 * u, 0.06 * u); dot(c, 0.25 * u, 0.02 * u, 0.06 * u);
      c.moveTo(-0.08 * u, 0.22 * u); c.lineTo(0.08 * u, 0.22 * u); c.lineTo(0, 0.32 * u); c.closePath();
      for (const s of [-1, 1]) { c.moveTo(s * 0.36 * u, 0.28 * u); c.lineTo(s * 0.86 * u, 0.2 * u); c.moveTo(s * 0.36 * u, 0.38 * u); c.lineTo(s * 0.84 * u, 0.46 * u); }
    },
    dog(c, u) {
      c.moveTo(0, -0.6 * u); c.bezierCurveTo(0.46 * u, -0.6 * u, 0.54 * u, -0.2 * u, 0.5 * u, 0.2 * u);
      c.bezierCurveTo(0.46 * u, 0.6 * u, 0.2 * u, 0.76 * u, 0, 0.76 * u); c.bezierCurveTo(-0.2 * u, 0.76 * u, -0.46 * u, 0.6 * u, -0.5 * u, 0.2 * u);
      c.bezierCurveTo(-0.54 * u, -0.2 * u, -0.46 * u, -0.6 * u, 0, -0.6 * u);
      for (const s of [-1, 1]) { c.moveTo(s * 0.38 * u, -0.5 * u); c.bezierCurveTo(s * 0.86 * u, -0.56 * u, s * 0.98 * u, 0, s * 0.76 * u, 0.32 * u); c.bezierCurveTo(s * 0.6 * u, 0.36 * u, s * 0.52 * u, 0.1 * u, s * 0.5 * u, -0.1 * u); }
      dot(c, -0.2 * u, -0.06 * u, 0.06 * u); dot(c, 0.2 * u, -0.06 * u, 0.06 * u);
      c.moveTo(0.12 * u, 0.3 * u); c.ellipse(0, 0.3 * u, 0.12 * u, 0.08 * u, 0, 0, Math.PI * 2);
      c.moveTo(0, 0.38 * u); c.quadraticCurveTo(-0.04 * u, 0.52 * u, -0.16 * u, 0.5 * u); c.moveTo(0, 0.38 * u); c.quadraticCurveTo(0.04 * u, 0.52 * u, 0.16 * u, 0.5 * u);
    },
    chart(c, u) {
      c.moveTo(-0.76 * u, -0.72 * u); c.lineTo(-0.76 * u, 0.7 * u); c.lineTo(0.8 * u, 0.7 * u);
      c.moveTo(-0.52 * u, 0.36 * u); c.lineTo(-0.18 * u, 0.02 * u); c.lineTo(0.1 * u, 0.2 * u); c.lineTo(0.58 * u, -0.42 * u);
      c.moveTo(0.3 * u, -0.44 * u); c.lineTo(0.6 * u, -0.44 * u); c.lineTo(0.6 * u, -0.14 * u);
    },
    loop(c, u) {
      c.moveTo(0.62 * u, -0.1 * u); c.arc(0, 0, 0.62 * u, -0.16, -2.6, true);
      c.moveTo(-0.62 * u, 0.1 * u); c.arc(0, 0, 0.62 * u, Math.PI - 0.16, Math.PI - 2.6, true);
      c.moveTo(0.36 * u, -0.22 * u); c.lineTo(0.62 * u, -0.08 * u); c.lineTo(0.76 * u, -0.36 * u);
      c.moveTo(-0.36 * u, 0.22 * u); c.lineTo(-0.62 * u, 0.08 * u); c.lineTo(-0.76 * u, 0.36 * u);
    },
  };

  // ---------------------------------------------------------------- background: gradient space, drifting glows, perspective grid, particles
  const GLOWS = [
    { c: C.blue, x: 0.16, y: 0.24, r: 520, a: 0.24 },
    { c: C.violet, x: 0.82, y: 0.18, r: 560, a: 0.3 },
    { c: C.cyan, x: 0.6, y: 0.95, r: 440, a: 0.17 },
    { c: C.magenta, x: 1.0, y: 0.72, r: 380, a: 0.17 },
    { c: C.indigo, x: 0.42, y: 0.62, r: 560, a: 0.12 },
  ];
  const PARTS = (() => { const r = H.rng(77); return Array.from({ length: 90 }, () => ({ x: r(), y: r(), s: r.range(0.6, 2.1), sp: r.range(0.004, 0.018), ph: r() * 6.28, c: r.pick([C.cyan, C.violet, '#ffffff', C.blue]), z: r.range(0.3, 1) })); })();

  function background(ctx, W, Hh, t, camX = 0, lvl = 1) {
    const g = ctx.createLinearGradient(0, 0, W * 0.5, Hh);
    g.addColorStop(0, '#03041a'); g.addColorStop(0.55, '#080a2d'); g.addColorStop(1, '#120b3c');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, Hh);
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    GLOWS.forEach((b, i) => {
      const x = (b.x + 0.05 * Math.sin(t * 0.21 + i * 1.9)) * W - camX * 0.1, y = (b.y + 0.06 * Math.cos(t * 0.17 + i * 2.7)) * Hh;
      const r = b.r * (1 + 0.07 * Math.sin(t * 0.3 + i)), rg = ctx.createRadialGradient(x, y, 0, x, y, r);
      rg.addColorStop(0, rgb(b.c, b.a * lvl)); rg.addColorStop(0.4, rgb(b.c, b.a * 0.38 * lvl)); rg.addColorStop(1, rgb(b.c, 0));
      ctx.fillStyle = rg; ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
    });
    ctx.restore();
    // faint dot field up top (fades upward)
    ctx.save();
    const ox = ((-camX * 0.3) % 40 + 40) % 40;
    for (let y = 20; y < Hh * 0.56; y += 40) {
      const a = 0.09 * lvl * (y / (Hh * 0.56));
      ctx.fillStyle = `rgba(150,170,255,${a})`;
      for (let x = ox; x < W; x += 40) ctx.fillRect(x - 1, y - 1, 2, 2);
    }
    ctx.restore();
    // perspective floor grid, lines rolling toward the camera
    const hy = Hh * 0.6, vx = W / 2 - camX * 0.25;
    ctx.save(); ctx.lineWidth = 1;
    const sg = ctx.createLinearGradient(0, hy, 0, Hh);
    sg.addColorStop(0, 'rgba(110,140,255,0)'); sg.addColorStop(0.3, `rgba(110,140,255,${0.07 * lvl})`); sg.addColorStop(1, `rgba(140,170,255,${0.22 * lvl})`);
    ctx.strokeStyle = sg; ctx.beginPath();
    const sh = fract(camX / 900) * 1;
    for (let i = -34; i <= 34; i++) { const k = i - sh; ctx.moveTo(vx + k * 12, hy); ctx.lineTo(vx + k * 190, Hh + 260); }
    const roll = fract(t * 0.35);
    for (let k = 0; k < 26; k++) { const d = k + 1 - roll, y = hy + 230 / d; if (y > Hh + 2) continue; ctx.moveTo(0, y); ctx.lineTo(W, y); }
    ctx.stroke();
    // horizon haze line
    const hz = ctx.createLinearGradient(0, 0, W, 0);
    hz.addColorStop(0, 'rgba(90,140,255,0)'); hz.addColorStop(0.5, `rgba(120,180,255,${0.18 * lvl})`); hz.addColorStop(1, 'rgba(90,140,255,0)');
    ctx.fillStyle = hz; ctx.fillRect(0, hy - 1, W, 2);
    ctx.restore();
    // particles
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (const p of PARTS) {
      const x = fract(p.x + 0.006 * Math.sin(t * 0.5 + p.ph) - camX * 0.0003 * p.z) * W, y = fract(p.y - t * p.sp) * Hh;
      const a = (0.2 + 0.55 * (0.5 + 0.5 * Math.sin(t * 1.7 + p.ph * 3))) * lvl * p.z;
      if (p.s > 1.7) { const rg = ctx.createRadialGradient(x, y, 0, x, y, p.s * 6); rg.addColorStop(0, rgb(p.c, a * 0.35)); rg.addColorStop(1, rgb(p.c, 0)); ctx.fillStyle = rg; ctx.fillRect(x - p.s * 6, y - p.s * 6, p.s * 12, p.s * 12); }
      ctx.fillStyle = rgb(p.c, a); ctx.beginPath(); ctx.arc(x, y, p.s * 0.7, 0, 6.283); ctx.fill();
    }
    ctx.restore();
  }

  // ---------------------------------------------------------------- bloom: threshold-ish downsample, two blur radii, added back
  let BL = null;
  function bloom(ctx, amt = 1) {
    const cv = ctx.canvas;
    if (!BL) BL = { a: H.layer(320, 180), b: H.layer(320, 180), c: H.layer(160, 90) };
    const a = BL.a.getContext('2d'), b = BL.b.getContext('2d'), c = BL.c.getContext('2d');
    a.globalCompositeOperation = 'copy'; a.filter = 'brightness(0.9) contrast(2.6) saturate(1.4)'; a.drawImage(cv, 0, 0, 320, 180); a.filter = 'none';
    b.globalCompositeOperation = 'copy'; b.filter = 'blur(2.5px)'; b.drawImage(BL.a, 0, 0); b.filter = 'none';
    c.globalCompositeOperation = 'copy'; c.filter = 'blur(4px)'; c.drawImage(BL.a, 0, 0, 160, 90); c.filter = 'none';
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = 0.45 * amt; ctx.drawImage(BL.b, 0, 0, cv.width, cv.height);
    ctx.globalAlpha = 0.5 * amt; ctx.drawImage(BL.c, 0, 0, cv.width, cv.height);
    ctx.restore();
  }

  // ---------------------------------------------------------------- building blocks
  function glowDot(ctx, x, y, col, r, a = 1) {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, rgb('#ffffff', a)); g.addColorStop(0.16, rgb(col, 0.9 * a)); g.addColorStop(0.45, rgb(col, 0.22 * a)); g.addColorStop(1, rgb(col, 0));
    ctx.fillStyle = g; ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
  }
  function ring(ctx, x, y, r, col, a, lw = 2) {
    if (a <= 0.001) return;
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = rgb(col, a); ctx.lineWidth = lw;
    ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.stroke(); ctx.restore();
  }
  // dark translucent card, inner glow, thin gradient border
  function card(ctx, x, y, w, h, o = {}) {
    const r = o.r ?? 22, acc = o.acc || [C.cyan, C.violet];
    ctx.save(); ctx.globalAlpha *= o.a ?? 1;
    ctx.shadowColor = 'rgba(0,0,12,0.6)'; ctx.shadowBlur = 44; ctx.shadowOffsetY = 18;
    const fg = ctx.createLinearGradient(x, y, x, y + h);
    fg.addColorStop(0, 'rgba(22,26,72,0.8)'); fg.addColorStop(1, 'rgba(8,9,32,0.86)');
    ctx.fillStyle = fg; rr(ctx, x, y, w, h, r); ctx.fill();
    ctx.shadowColor = 'transparent';
    ctx.save(); rr(ctx, x, y, w, h, r); ctx.clip();
    const ig = ctx.createRadialGradient(x + w * 0.25, y, 0, x + w * 0.25, y, Math.max(w, h) * 0.8);
    ig.addColorStop(0, rgb(acc[0], 0.17)); ig.addColorStop(1, rgb(acc[0], 0)); ctx.fillStyle = ig; ctx.fillRect(x, y, w, h);
    const ig2 = ctx.createRadialGradient(x + w, y + h, 0, x + w, y + h, Math.max(w, h) * 0.7);
    ig2.addColorStop(0, rgb(acc[1], 0.14)); ig2.addColorStop(1, rgb(acc[1], 0)); ctx.fillStyle = ig2; ctx.fillRect(x, y, w, h);
    ctx.restore();
    const bg = ctx.createLinearGradient(x, y, x + w, y + h);
    bg.addColorStop(0, rgb(acc[0], 0.95)); bg.addColorStop(0.4, rgb(acc[1], 0.4)); bg.addColorStop(0.72, 'rgba(255,255,255,0.07)'); bg.addColorStop(1, rgb(acc[1], 0.6));
    ctx.strokeStyle = bg; ctx.lineWidth = 1.5; rr(ctx, x + 0.75, y + 0.75, w - 1.5, h - 1.5, r); ctx.stroke();
    // top edge highlight
    const hl = ctx.createLinearGradient(x, 0, x + w, 0);
    hl.addColorStop(0, 'rgba(255,255,255,0)'); hl.addColorStop(0.3, 'rgba(200,240,255,0.5)'); hl.addColorStop(0.65, 'rgba(255,255,255,0)');
    ctx.strokeStyle = hl; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x + r, y + 1.5); ctx.lineTo(x + w - r, y + 1.5); ctx.stroke();
    if (o.flash > 0.01) {
      ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = rgb(o.flashCol || C.cyan, o.flash); ctx.lineWidth = 3;
      rr(ctx, x + 1, y + 1, w - 2, h - 2, r); ctx.stroke();
      ctx.save(); rr(ctx, x, y, w, h, r); ctx.clip(); ctx.fillStyle = rgb(o.flashCol || C.cyan, o.flash * 0.08); ctx.fillRect(x, y, w, h); ctx.restore();
    }
    ctx.restore();
  }
  // rounded icon tile with gradient stroke + glowing line icon
  function tile(ctx, cx, cy, s, icon, o = {}) {
    const a = o.a ?? 1, sc = o.sc ?? 1, col = o.col || [C.cyan, C.violet], glow = o.glow ?? 1, draw = o.draw ?? 1;
    if (a <= 0.003 || sc <= 0.003) return;
    ctx.save(); ctx.translate(cx, cy); ctx.scale(sc, sc); ctx.globalAlpha *= a;
    const r = s * 0.26, h = s / 2;
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const hg = ctx.createRadialGradient(0, 0, s * 0.25, 0, 0, s * 1.15);
    hg.addColorStop(0, rgb(col[0], Math.min(0.5, 0.2 * glow))); hg.addColorStop(0.5, rgb(col[1], Math.min(0.25, 0.07 * glow))); hg.addColorStop(1, rgb(col[1], 0));
    ctx.fillStyle = hg; ctx.fillRect(-s * 1.15, -s * 1.15, s * 2.3, s * 2.3);
    ctx.restore();
    ctx.save(); ctx.shadowColor = 'rgba(0,0,10,0.55)'; ctx.shadowBlur = s * 0.3; ctx.shadowOffsetY = s * 0.1;
    const bg = ctx.createLinearGradient(0, -h, 0, h); bg.addColorStop(0, '#171b4d'); bg.addColorStop(1, '#090a28');
    ctx.fillStyle = bg; rr(ctx, -h, -h, s, s, r); ctx.fill(); ctx.restore();
    ctx.save(); rr(ctx, -h, -h, s, s, r); ctx.clip();
    const ig = ctx.createRadialGradient(-h * 0.5, -h * 0.7, 0, -h * 0.5, -h * 0.7, s);
    ig.addColorStop(0, rgb(col[0], 0.3)); ig.addColorStop(1, rgb(col[0], 0)); ctx.fillStyle = ig; ctx.fillRect(-h, -h, s, s);
    const ig2 = ctx.createRadialGradient(h * 0.6, h * 0.8, 0, h * 0.6, h * 0.8, s * 0.8);
    ig2.addColorStop(0, rgb(col[1], 0.26)); ig2.addColorStop(1, rgb(col[1], 0)); ctx.fillStyle = ig2; ctx.fillRect(-h, -h, s, s);
    if (glow > 1.05) { ctx.fillStyle = rgb(col[0], Math.min(0.25, (glow - 1) * 0.12)); ctx.fillRect(-h, -h, s, s); }
    ctx.restore();
    const sg = ctx.createLinearGradient(-h, -h, h, h); sg.addColorStop(0, H.rgba(H.mix(col[0], '#ffffff', 0.2), 1)); sg.addColorStop(1, col[1]);
    ctx.strokeStyle = sg; ctx.lineWidth = Math.max(1.6, s * 0.022); rr(ctx, -h + 1, -h + 1, s - 2, s - 2, r); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,255,255,0.09)'; ctx.lineWidth = 1; rr(ctx, -h + 6, -h + 6, s - 12, s - 12, r * 0.75); ctx.stroke();
    if (draw > 0) {
      const icg = ctx.createLinearGradient(-h * 0.5, -h * 0.5, h * 0.5, h * 0.5);
      icg.addColorStop(0, H.rgba(H.mix(col[0], '#ffffff', 0.45), 1)); icg.addColorStop(1, H.rgba(H.mix(col[1], '#ffffff', 0.15), 1));
      ctx.strokeStyle = icg; ctx.lineWidth = Math.max(1.8, s * 0.042); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      if (draw < 1) ctx.setLineDash([draw * s * 2.4, 1e4]);
      ctx.beginPath(); ICONS[icon](ctx, s * 0.3); ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.restore();
  }
  // pill label centred at (x, y)
  function pill(ctx, x, y, text, o = {}) {
    const a = o.a ?? 1; if (a <= 0.003) return;
    const size = o.size || 24, col = o.col || [C.cyan, C.violet];
    ctx.save(); ctx.globalAlpha *= a; ctx.translate(x, y); ctx.scale(o.sc ?? 1, o.sc ?? 1);
    ctx.font = F(600, size, UI); const tw = ctx.measureText(text).width, dotW = o.dot ? size * 0.75 : 0;
    const w = tw + size * 1.3 + dotW, h = size * 1.62;
    ctx.fillStyle = o.fill || 'rgba(10,12,42,0.88)'; rr(ctx, -w / 2, -h / 2, w, h, h / 2); ctx.fill();
    const g = ctx.createLinearGradient(-w / 2, 0, w / 2, 0); g.addColorStop(0, rgb(col[0], 0.9)); g.addColorStop(1, rgb(col[1], 0.7));
    ctx.strokeStyle = g; ctx.lineWidth = 1.4; rr(ctx, -w / 2 + 0.7, -h / 2 + 0.7, w - 1.4, h - 1.4, h / 2); ctx.stroke();
    if (o.dot) { ctx.fillStyle = col[0]; ctx.beginPath(); ctx.arc(-w / 2 + size * 0.75, 0, size * 0.17, 0, 6.283); ctx.fill(); }
    ctx.fillStyle = o.textCol || C.white; ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
    ctx.fillText(text, -w / 2 + size * 0.65 + dotW, size * 0.04);
    ctx.restore();
  }
  // gradient-filled text; returns width
  function gtext(ctx, s, x, y, size, o = {}) {
    ctx.font = F(o.w || 700, size, o.fam); ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    ctx.letterSpacing = o.ls || '0px';
    const w = ctx.measureText(s).width, x0 = o.align === 'center' ? x - w / 2 : o.align === 'right' ? x - w : x;
    const cols = o.cols || GRAD_HEAD, g = ctx.createLinearGradient(x0, y - size, x0 + w, y);
    cols.forEach((c, i) => g.addColorStop(i / (cols.length - 1), c));
    ctx.fillStyle = g; ctx.fillText(s, x0, y); ctx.letterSpacing = '0px';
    return w;
  }
  // words revealed one by one (rise + fade), one gradient across the whole line
  function revealLine(ctx, s, x, y, size, prog, o = {}) {
    ctx.font = F(o.w || 700, size, o.fam); ctx.letterSpacing = o.ls || '0px';
    const words = s.split(' '), full = ctx.measureText(s).width, x0 = o.align === 'center' ? x - full / 2 : x;
    const cols = o.cols || GRAD_HEAD, g = ctx.createLinearGradient(x0, y - size, x0 + full, y);
    cols.forEach((c, i) => g.addColorStop(i / (cols.length - 1), c));
    ctx.save(); ctx.fillStyle = g; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    let cx = x0; const n = words.length;
    words.forEach((wd, i) => {
      const p = E.out(cl(prog * (n + 1.5) - i * 1.0, 0, 1)), ww = ctx.measureText(wd + (i < n - 1 ? ' ' : '')).width;
      if (p > 0) { ctx.globalAlpha = p * (o.a ?? 1); ctx.fillText(wd, cx, y + (1 - p) * size * 0.45); }
      cx += ww;
    });
    ctx.restore(); ctx.letterSpacing = '0px';
    return { x0, w: full };
  }
  function eyebrow(ctx, s, x, y, o = {}) {
    const a = o.a ?? 1; if (a <= 0.003) return;
    const size = o.size || 18, col = o.col || C.cyan;
    ctx.save(); ctx.globalAlpha *= a; ctx.font = F(600, size, UI); ctx.letterSpacing = '3px';
    const w = ctx.measureText(s).width + 22, x0 = o.align === 'center' ? x - w / 2 : x;
    ctx.globalCompositeOperation = 'lighter'; glowDot(ctx, x0 + 5, y - size * 0.36, col, 12); ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x0 + 5, y - size * 0.36, 3.2, 0, 6.283); ctx.fill();
    ctx.fillStyle = rgb(H.mix(col, '#ffffff', 0.25), 1); ctx.textAlign = 'left'; ctx.fillText(s, x0 + 22, y);
    ctx.letterSpacing = '0px'; ctx.restore();
  }

  // ---------------------------------------------------------------- connectors (sampled curves) + light pulses
  function bez(x0, y0, x1, y1, x2, y2, x3, y3, n = 48) {
    const P = []; let L = 0, px = x0, py = y0;
    for (let i = 0; i <= n; i++) {
      const u = i / n, m = 1 - u;
      const x = m * m * m * x0 + 3 * m * m * u * x1 + 3 * m * u * u * x2 + u * u * u * x3;
      const y = m * m * m * y0 + 3 * m * m * u * y1 + 3 * m * u * u * y2 + u * u * u * y3;
      if (i) L += Math.hypot(x - px, y - py);
      P.push({ x, y, l: L }); px = x; py = y;
    }
    P.L = L; return P;
  }
  const seg2 = (x0, y0, x1, y1) => bez(x0, y0, lerp(x0, x1, 0.33), lerp(y0, y1, 0.33), lerp(x0, x1, 0.66), lerp(y0, y1, 0.66), x1, y1, 8);
  function ptAt(P, f) {
    const tl = cl(f) * P.L;
    for (let i = 1; i < P.length; i++) if (P[i].l >= tl) { const a = P[i - 1], b = P[i], k = (tl - a.l) / Math.max(1e-6, b.l - a.l); return { x: lerp(a.x, b.x, k), y: lerp(a.y, b.y, k) }; }
    return P[P.length - 1];
  }
  function sub(ctx, P, a, b) {
    a = cl(a); b = cl(b); ctx.beginPath(); if (b <= a) return;
    const s = ptAt(P, a); ctx.moveTo(s.x, s.y);
    const la = a * P.L, lb = b * P.L;
    for (const p of P) if (p.l > la && p.l < lb) ctx.lineTo(p.x, p.y);
    const e = ptAt(P, b); ctx.lineTo(e.x, e.y);
  }
  function pulseOn(ctx, P, p, col, len = 0.16, a = 1) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.lineCap = 'round';
    const n = 8;
    for (let i = 0; i < n; i++) {
      const a0 = p - len * (i + 1) / n, a1 = p - len * i / n;
      if (a1 <= 0 || a0 >= 1) continue;
      ctx.strokeStyle = rgb(col, 0.85 * a * (1 - i / n)); ctx.lineWidth = 3.4 - i * 0.3; sub(ctx, P, a0, a1); ctx.stroke();
    }
    if (p >= 0 && p <= 1) { const h = ptAt(P, p); glowDot(ctx, h.x, h.y, col, 18, a); }
    ctx.restore();
  }
  function connector(ctx, P, o = {}) {
    const d = o.draw ?? 1, a = o.a ?? 1; if (d <= 0 || a <= 0.003) return;
    const c0 = (o.col || [])[0] || C.cyan, c1 = (o.col || [])[1] || C.violet;
    ctx.save(); ctx.globalAlpha *= a; ctx.lineCap = 'round';
    const s = P[0], e = P[P.length - 1], g = ctx.createLinearGradient(s.x, s.y, e.x, e.y);
    g.addColorStop(0, rgb(c0, 0.75)); g.addColorStop(1, rgb(c1, 0.75));
    ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = rgb(c0, 0.08); ctx.lineWidth = 9; sub(ctx, P, 0, d); ctx.stroke();
    ctx.globalCompositeOperation = 'source-over'; ctx.strokeStyle = g; ctx.lineWidth = o.lw || 1.8; sub(ctx, P, 0, d); ctx.stroke();
    if (!o.noEnds) {
      ctx.fillStyle = '#0b0d30'; ctx.strokeStyle = c0; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.arc(s.x, s.y, 4, 0, 6.283); ctx.fill(); ctx.stroke();
      if (d >= 1) { ctx.strokeStyle = c1; ctx.beginPath(); ctx.arc(e.x, e.y, 4, 0, 6.283); ctx.fill(); ctx.stroke(); }
    }
    if (d < 1) { const hpt = ptAt(P, d); ctx.globalCompositeOperation = 'lighter'; glowDot(ctx, hpt.x, hpt.y, c0, 16); }
    ctx.restore();
    for (const p of o.pulses || []) if (p > 0 && p - 0.16 < d) pulseOn(ctx, P, Math.min(p, d), o.pc || '#9ff0ff', o.pl || 0.16, a);
  }

  function finish(ctx, W, Hh, t) {
    bloom(ctx, 1);
    H.vignette(ctx, W, Hh, 0.45, '2,3,16');
  }
  window.TG = { C, GRAD_HEAD, GRAD_NUM, F, ICONS, seg, eo, eio, ebk, fract, rgb, rr, bump,
    background, bloom, glowDot, ring, card, tile, pill, gtext, revealLine, eyebrow,
    bez, seg2, ptAt, sub, pulseOn, connector, finish };
  window.STYLE = { fonts: ['700 80px "Space Grotesk"', '500 18px "Space Grotesk"',
    '600 26px "Inter"', '500 18px "Inter"', '400 22px "Inter"'], finish };
})();
