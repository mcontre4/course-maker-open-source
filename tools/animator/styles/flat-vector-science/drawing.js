(function(){
  const TAU = Math.PI * 2;
  const cl = H.clamp, lerp = H.lerp;
  const seg = (t, a, b) => cl((t - a) / (b - a));
  const eo = H.ease.out, eio = H.ease.inOut;
  // gentle overshoot
  const back = (u, s = 1.5) => { if (u <= 0) return 0; if (u >= 1) return 1; return 1 + (s + 1) * Math.pow(u - 1, 3) + s * Math.pow(u - 1, 2); };
  const FONT = '"Nunito", "Fredoka", sans-serif';
  const F = (w, px) => `${w} ${px}px ${FONT}`;

  const C = {
    sky0: '#090b2c', sky1: '#18134f', sky2: '#3a1a6c',
    ink: '#141846', visor: '#10164a',
    teal: ['#a4fbef', '#3ccbdc', '#1d64b0'],
    orange: ['#ffcc7a', '#ff8d3f', '#d24a2a'],
    tan: ['#ffe9be', '#ecb676', '#b4723c'],
    yellow: '#ffd23f', pink: '#ff5d8f', red: '#ff3b5c', green: '#38e08e', cyan: '#56e8ff', violet: '#8b5cff',
  };

  // ---------- small helpers ----------
  function rr(x, X, Y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    x.beginPath(); x.moveTo(X + r, Y); x.arcTo(X + w, Y, X + w, Y + h, r); x.arcTo(X + w, Y + h, X, Y + h, r);
    x.arcTo(X, Y + h, X, Y, r); x.arcTo(X, Y, X + w, Y, r); x.closePath();
  }
  function glow(x, cx, cy, r, col, a) {
    if (a <= 0 || r <= 0) return;
    const g = x.createRadialGradient(cx, cy, 0, cx, cy, r);
    g.addColorStop(0, H.rgba(col, a)); g.addColorStop(0.35, H.rgba(col, a * 0.4)); g.addColorStop(1, H.rgba(col, 0));
    x.fillStyle = g; x.beginPath(); x.arc(cx, cy, r, 0, TAU); x.fill();
  }
  function spark(x, cx, cy, r, col, a) {
    if (a <= 0 || r <= 0) return;
    x.save(); x.globalAlpha *= a; x.fillStyle = col; x.beginPath();
    x.moveTo(cx, cy - r); x.quadraticCurveTo(cx, cy, cx + r, cy); x.quadraticCurveTo(cx, cy, cx, cy + r);
    x.quadraticCurveTo(cx, cy, cx - r, cy); x.quadraticCurveTo(cx, cy, cx, cy - r); x.fill(); x.restore();
  }
  // region of circle (cx,cy,r) NOT covered by the same circle shifted by (dx,dy)
  function crescent(x, cx, cy, r, dx, dy, fill) {
    x.save(); x.beginPath(); x.arc(cx, cy, r, 0, TAU); x.clip();
    x.beginPath(); x.rect(cx - r - 2, cy - r - 2, 2 * r + 4, 2 * r + 4); x.arc(cx + dx, cy + dy, r * 1.02, 0, TAU);
    x.fillStyle = fill; x.fill('evenodd'); x.restore();
  }
  // the core flat-vector ball: multi-stop gradient, two stepped flat shadow crescents, rim highlight
  function ball(x, cx, cy, r, col, o = {}) {
    if (r <= 0.3) return;
    const la = o.la == null ? -2.25 : o.la, lx = Math.cos(la), ly = Math.sin(la);
    const g = x.createLinearGradient(cx + lx * r, cy + ly * r, cx - lx * r, cy - ly * r);
    g.addColorStop(0, col[0]); g.addColorStop(0.45, col[1]); g.addColorStop(1, H.rgba(H.mix(col[1], col[2], 0.6)));
    x.fillStyle = g; x.beginPath(); x.arc(cx, cy, r, 0, TAU); x.fill();
    if (o.inner) { x.save(); x.beginPath(); x.arc(cx, cy, r, 0, TAU); x.clip(); o.inner(); x.restore(); }
    const sh = o.sh == null ? 0.3 : o.sh;
    crescent(x, cx, cy, r, lx * r * sh, ly * r * sh, H.rgba(col[2], o.sha == null ? 0.5 : o.sha));
    crescent(x, cx, cy, r, lx * r * sh * 2.2, ly * r * sh * 2.2, H.rgba(col[2], (o.sha == null ? 0.5 : o.sha) * 0.45));
    crescent(x, cx, cy, r, -lx * r * 0.075, -ly * r * 0.075, H.rgba(o.rim || '#ffffff', o.rima == null ? 0.42 : o.rima));
  }
  const bez = (P, u) => { const v = 1 - u; return [v * v * v * P[0][0] + 3 * v * v * u * P[1][0] + 3 * v * u * u * P[2][0] + u * u * u * P[3][0], v * v * v * P[0][1] + 3 * v * v * u * P[1][1] + 3 * v * u * u * P[2][1] + u * u * u * P[3][1]]; };
  // rounded dotted / solid arrow along a cubic, drawn on to `prog`
  function arrow(x, P, prog, col, lw, o = {}) {
    if (prog <= 0) return;
    const n = 48, a = o.a == null ? 1 : o.a;
    x.save(); x.globalAlpha *= a; x.strokeStyle = col; x.fillStyle = col; x.lineWidth = lw; x.lineCap = 'round'; x.lineJoin = 'round';
    if (o.dots) x.setLineDash([0.01, lw * 1.9]);
    x.beginPath(); const p0 = bez(P, o.from || 0); x.moveTo(p0[0], p0[1]);
    for (let i = 1; i <= n; i++) { const u = (o.from || 0) + ((prog - (o.from || 0)) * i) / n; const p = bez(P, u); x.lineTo(p[0], p[1]); }
    x.stroke(); x.setLineDash([]);
    if (o.head !== false && prog > 0.08) {
      const e = bez(P, prog), e0 = bez(P, prog - 0.02), ang = Math.atan2(e[1] - e0[1], e[0] - e0[0]), hs = lw * 1.5 * cl(prog * 5);
      x.translate(e[0], e[1]); x.rotate(ang); x.beginPath(); x.moveTo(hs * 1.1, 0); x.lineTo(-hs * 0.8, hs); x.lineTo(-hs * 0.8, -hs); x.closePath();
      x.lineWidth = lw * 0.7; x.fill(); x.stroke();
    }
    x.restore();
  }
  // flat text with a darker offset "long shadow"
  function text(x, s, cx, cy, px, col, o = {}) {
    x.save(); x.font = F(o.w || 900, px); x.textAlign = o.align || 'center'; x.textBaseline = 'middle';
    x.globalAlpha *= o.a == null ? 1 : o.a;
    x.fillStyle = o.shadow || 'rgba(10,8,46,0.55)'; x.fillText(s, cx + px * 0.03, cy + px * 0.07);
    x.fillStyle = col; x.fillText(s, cx, cy); x.restore();
  }
  // rounded label pill, optional pointer below
  function pill(x, cx, cy, s, px, o = {}) {
    const sc = o.s == null ? 1 : o.s, a = o.a == null ? 1 : o.a;
    if (sc <= 0.01 || a <= 0.01) return;
    x.save(); x.font = F(o.w || 900, px);
    const tw = x.measureText(s).width, w = tw + px * 1.15, h = px * 1.6;
    x.translate(cx, cy); x.scale(sc, sc); x.globalAlpha *= a;
    x.fillStyle = 'rgba(10,8,46,0.4)'; rr(x, -w / 2, -h / 2 + px * 0.2, w, h, h / 2); x.fill();
    x.fillStyle = o.bg || '#ffffff';
    if (o.ptr) { x.beginPath(); x.moveTo(-px * 0.35, h / 2 - 2); x.lineTo(0, h / 2 + px * 0.45); x.lineTo(px * 0.35, h / 2 - 2); x.fill(); }
    rr(x, -w / 2, -h / 2, w, h, h / 2); x.fill();
    x.fillStyle = 'rgba(255,255,255,0.35)'; rr(x, -w / 2 + h * 0.25, -h / 2 + h * 0.12, w - h * 0.5, h * 0.16, h * 0.08); x.fill();
    x.fillStyle = o.fg || C.ink; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(s, 0, px * 0.06);
    x.restore();
    return w;
  }

  // ---------- sky: gradient, nebula glows, parallax stars and sparkles ----------
  let STARS = null;
  function stars() {
    if (STARS) return STARS;
    const r = H.rng(77), a = [], sp = [];
    for (let i = 0; i < 620; i++) a.push({ x: r.range(0, 1680), y: r.range(0, 1120), d: r.pick([0.15, 0.3, 0.3, 0.55, 1]), s: r.range(0.6, 2.0), ph: r.range(0, TAU), sp: r.range(0.8, 2.6), c: r.pick(['#ffffff', '#cfe4ff', '#ffe9c7', '#dccbff']) });
    for (let i = 0; i < 16; i++) sp.push({ x: r.range(0, 1680), y: r.range(0, 1120), d: r.range(0.3, 0.9), s: r.range(6, 13), ph: r.range(0, TAU) });
    STARS = { a, sp }; return STARS;
  }
  function sky(x, W, H_, t, cam = {}) {
    const px = cam.x || 0, py = cam.y || 0, lz = Math.log(cam.z || 1);
    const g = x.createLinearGradient(0, 0, W * 0.3, H_);
    g.addColorStop(0, C.sky0); g.addColorStop(0.5, C.sky1); g.addColorStop(1, C.sky2);
    x.fillStyle = g; x.fillRect(0, 0, W, H_);
    glow(x, W * 0.86, H_ * 0.12, 700, '#7b34c6', 0.34);
    glow(x, W * 0.05, H_ * 1.0, 620, '#2448b4', 0.4);
    glow(x, W * 0.45, H_ * 0.6, 520, '#4a2a9c', 0.16);
    const S = stars();
    const place = (s) => {
      const k = Math.exp(lz * s.d * 0.6);
      let sx = (((s.x - px * s.d) % 1680) + 1680) % 1680 - 200, sy = (((s.y - py * s.d) % 1120) + 1120) % 1120 - 200;
      return [(sx - 640) * k + 640, (sy - 360) * k + 360];
    };
    for (const s of S.a) {
      const [sx, sy] = place(s);
      if (sx < -4 || sx > W + 4 || sy < -4 || sy > H_ + 4) continue;
      x.globalAlpha = (0.55 + 0.45 * Math.sin(t * s.sp + s.ph)) * (0.45 + s.d * 0.55);
      x.fillStyle = s.c; x.beginPath(); x.arc(sx, sy, s.s * (0.7 + 0.35 * s.d), 0, TAU); x.fill();
    }
    x.globalAlpha = 1;
    for (const s of S.sp) {
      const [sx, sy] = place(s); const tw = 0.6 + 0.4 * Math.sin(t * 1.7 + s.ph);
      glow(x, sx, sy, s.s * 2.2, '#bfa8ff', 0.25 * tw);
      spark(x, sx, sy, s.s * tw, '#ffffff', 0.9);
    }
  }

  let GRAIN = null;
  function grainTex() {
    if (GRAIN) return GRAIN;
    const S = 256, tile = H.layer(S, S), tc = tile.getContext('2d'), img = tc.createImageData(S, S), d = img.data, r = H.rng(4242);
    for (let i = 0; i < d.length; i += 4) { const v = 128 + (r() + r() + r() - 1.5) * 92; d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; }
    tc.putImageData(img, 0, 0);
    const MW = 320, MH = 180, mot = H.layer(MW, MH), mc = mot.getContext('2d'), mi = mc.createImageData(MW, MH), md = mi.data, nz = H.makeNoise(88);
    for (let y = 0; y < MH; y++) for (let x = 0; x < MW; x++) { const v = 128 + nz.fbm2(x * 0.035, y * 0.035, 4) * 70 + nz.n2(x * 0.22, y * 0.22) * 14, k = (y * MW + x) * 4; md[k] = md[k + 1] = md[k + 2] = v; md[k + 3] = 255; }
    mc.putImageData(mi, 0, 0);
    GRAIN = { tile, mot };
    return GRAIN;
  }
  function finish(x, W, H_, t) {
    const G = grainTex(), f = Math.floor(t * 24);
    x.save(); x.globalCompositeOperation = 'overlay';
    x.globalAlpha = 0.12; x.imageSmoothingEnabled = true; x.drawImage(G.mot, 0, 0, W, H_);
    const pat = x.createPattern(G.tile, 'repeat'); pat.setTransform(new DOMMatrix().translateSelf((f * 73) % 256, (f * 151) % 256));
    x.globalAlpha = 0.09; x.fillStyle = pat; x.fillRect(0, 0, W, H_);
    x.restore();
  }


window.FV={sky,finish,glow,spark,crescent,ball,arrow,text,pill,rr,bez,seg,back};
window.STYLE={fonts:["900 64px Nunito","700 28px Nunito","600 44px Fredoka"],finish};
})();
