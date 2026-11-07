// Original ink, halftone and paper recipes extracted from the supplied reference.
(function () {
  // ---------- Risograph: 3 spot-ink separations, multiplied onto stock ----------
  const INK = { pink: [255, 72, 176], blue: [50, 85, 164], yellow: [255, 226, 0] };
  const PAPER = [242, 237, 224];

  const hash = (x, y, s) => {
    let h = (Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(s, 1442695041)) | 0;
    h = Math.imul(h ^ (h >>> 13), 1274126177); h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  };

  // smooth low-frequency noise field (3 channels) via upscaled tiny canvas
  const lowField = (W, H_, seed, gw, gh, freq) => {
    const nz = H.makeNoise(seed), s = H.layer(gw, gh), sx = s.getContext('2d');
    const im = sx.createImageData(gw, gh), d = im.data;
    for (let y = 0; y < gh; y++) for (let x = 0; x < gw; x++) {
      const i = (y * gw + x) * 4;
      d[i] = 128 + 127 * H.clamp(nz.fbm2(x * freq, y * freq, 3) * 1.6, -1, 1);
      d[i + 1] = 128 + 127 * H.clamp(nz.fbm2(x * freq + 40, y * freq + 9, 3) * 1.6, -1, 1);
      d[i + 2] = 128 + 127 * H.clamp(nz.fbm2(x * freq + 80, y * freq + 31, 3) * 1.6, -1, 1);
      d[i + 3] = 255;
    }
    sx.putImageData(im, 0, 0);
    const big = H.layer(W, H_), bx = big.getContext('2d');
    bx.imageSmoothingEnabled = true; bx.imageSmoothingQuality = 'high';
    bx.drawImage(s, 0, 0, W, H_);
    return bx.getImageData(0, 0, W, H_).data;
  };

  let RX_CACHE = null;
  const rxStatic = (W, H_) => {
    if (RX_CACHE && RX_CACHE.W === W && RX_CACHE.H === H_) return RX_CACHE;
    const mott = lowField(W, H_, 5, 96, 54, 0.11), fine = lowField(W, H_, 9, 320, 180, 0.22);
    const streaks = [11, 22, 33].map((sd) => {
      const a = new Float32Array(W), nz = H.makeNoise(sd + 3), rr = H.rng(sd + 5), lines = [];
      for (let i = 0; i < 6; i++) lines.push([rr.range(0, W), rr.range(1, 4), rr.range(0.15, 0.35)]);
      for (let x = 0; x < W; x++) { let v = 1 - 0.1 * Math.abs(nz.fbm2(x * 0.012, 0.3, 3)) * 2 - 0.05 * (nz.n2(x * 0.09, 3.1) + 1); for (const [lx, lw, ls] of lines) v -= ls * Math.exp(-((x - lx) * (x - lx)) / (lw * lw)); a[x] = v; }
      return a;
    });
    return (RX_CACHE = { W, H: H_, mott, fine, streaks });
  };

  const qpt = (p0, c, p1, s) => [(1 - s) * (1 - s) * p0[0] + 2 * (1 - s) * s * c[0] + s * s * p1[0], (1 - s) * (1 - s) * p0[1] + 2 * (1 - s) * s * c[1] + s * s * p1[1]];
  const arrowQ = (x, p0, c, p1, u, w, dash) => {
    if (u <= 0) return;
    x.save(); x.lineWidth = w; x.lineCap = 'round'; x.lineJoin = 'round'; if (dash) x.setLineDash(dash);
    x.beginPath(); x.moveTo(p0[0], p0[1]);
    const N = 30; for (let i = 1; i <= N * u; i++) { const q = qpt(p0, c, p1, i / N); x.lineTo(q[0], q[1]); }
    const e = qpt(p0, c, p1, u); x.lineTo(e[0], e[1]); x.stroke(); x.setLineDash([]);
    const b = qpt(p0, c, p1, Math.max(0, u - 0.04)), a = Math.atan2(e[1] - b[1], e[0] - b[0]), hs = w * 3.2;
    x.beginPath(); x.moveTo(e[0] + Math.cos(a) * hs * 0.6, e[1] + Math.sin(a) * hs * 0.6);
    x.lineTo(e[0] + Math.cos(a + 2.5) * hs, e[1] + Math.sin(a + 2.5) * hs); x.lineTo(e[0] + Math.cos(a - 2.5) * hs, e[1] + Math.sin(a - 2.5) * hs); x.closePath(); x.fill();
    x.restore();
  };
  const T = (x, s, font, px, py, align = 'left', ls = 0) => { x.font = font; x.textAlign = align; x.letterSpacing = ls + 'px'; x.fillText(s, px, py); x.letterSpacing = '0px'; };

  // animal line drawings (blue plate) for cards
  const scribbleCircle = (x, cx, cy, rx, ry, u, w) => {
    if (u <= 0) return;
    x.save(); x.lineWidth = w; x.lineCap = 'round'; x.beginPath();
    const N = 60, turns = 1.15;
    for (let i = 0; i <= N * u; i++) { const a = -2.2 + (i / N) * turns * Math.PI * 2, rr = 1 + 0.06 * Math.sin(i * 0.5); const px = cx + Math.cos(a) * rx * rr, py = cy + Math.sin(a) * ry * rr; i ? x.lineTo(px, py) : x.moveTo(px, py); }
    x.stroke(); x.restore();
  };

  function plates(W, H_, t = 0) {
    const jr = H.rng(2000 + Math.floor(t * 8));
    return [
      { k: 'yellow', ink: INK.yellow, dx: -5, dy: 6, ang: 0.26, cell: 5.2 },
      { k: 'pink', ink: INK.pink, dx: 6, dy: -3, ang: 1.31, cell: 5.2 },
      { k: 'blue', ink: INK.blue, dx: 0, dy: 0, ang: 0.79, cell: 5.2 },
    ].map((p, k) => {
      p.canvas = H.layer(W, H_); p.ctx = p.canvas.getContext('2d', { willReadFrequently: true });
      p.ctx.fillStyle = '#fff'; p.ctx.fillRect(0, 0, W, H_);
      p.ctx.translate(p.dx + jr.range(-1, 1) * (k < 2), p.dy + jr.range(-1, 1) * (k < 2));
      p.reveal = 1e9;
      return p;
    });
  }
  function composite(ctx, base, W, H_, t) {
    const st = rxStatic(W, H_), step = Math.floor(t * 8), cl = H.clamp;
    const seps = base.map(p => p.ctx.getImageData(0, 0, W, H_).data);
    const { mott, fine, streaks } = st;
    const out = ctx.createImageData(W, H_), o = out.data;
    const cs = base.map((p) => Math.cos(p.ang)), sn = base.map((p) => Math.sin(p.ang));
    for (let y = 0; y < H_; y++) for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      const pf = (fine[i] - 128) / 128, pg = hash(x, y, 7) - 0.5;
      let r = PAPER[0] * (1 + pf * 0.018 + pg * 0.035), g = PAPER[1] * (1 + pf * 0.018 + pg * 0.035), b = PAPER[2] * (1 + pf * 0.022 + pg * 0.04);
      for (let k = 0; k < 3; k++) {
        const d = 1 - seps[k][i] / 255; if (d < 0.01) continue;
        const p = base[k];
        let edgeF = 1;
        if (p.reveal < 1e8) { const ed = p.reveal + Math.sin(x * 0.031 + k * 2) * 5 - y; if (ed < 0) continue; if (ed < 18) edgeF = ed / 18; }
        let cov;
        if (d > 0.96) cov = 1;
        else {
          const u = (x * cs[k] + y * sn[k]) * (6.2832 / p.cell), v = (-x * sn[k] + y * cs[k]) * (6.2832 / p.cell);
          const thr = (0.5 + 0.25 * (Math.cos(u) + Math.cos(v))) * 0.72 + hash(x, y, 50 + k) * 0.28;
          cov = cl((d * 1.05 - thr) * 5 + 0.5);
        }
        if (cov <= 0) continue;
        const m = (k === 0 ? mott[i + 2] - 128 : k === 1 ? mott[i] - 128 : mott[i + 1] - 128) / 128;
        let dens = 0.88 + m * 0.15 + ((fine[i + k] - 128) / 128) * 0.07 + (hash(x, y, 90 + k + step * 7) - 0.5) * 0.16;
        dens *= streaks[k][x];
        if (hash(x, y, 120 + k) < 0.012 + Math.max(0, -m) * 0.04) dens *= 0.35;
        cov *= cl(dens) * edgeF;
        r *= 1 - cov * (1 - p.ink[0] / 255); g *= 1 - cov * (1 - p.ink[1] / 255); b *= 1 - cov * (1 - p.ink[2] / 255);
      }
      o[i] = r; o[i + 1] = g; o[i + 2] = b; o[i + 3] = 255;
    }
    ctx.putImageData(out, 0, 0);
  }

  // Ink density, halftone, roller streaks and paper grain are inseparable from composite().
  // The player must not add a second finishing pass to the already printed image.
  window.RISO = { INK, PAPER, hash, lowField, rxStatic, qpt, arrowQ, T, scribbleCircle, plates, composite };
  window.STYLE = { fonts: ['400 64px "Archivo Black"', '400 28px "Space Mono"', '700 28px "Space Mono"'], finish() {} };
})();
