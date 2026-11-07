// Original clay extrusion, shading and finishing helpers from the supplied reference.
(function () {
  // ---------- soft "clay" 3D faked in 2D: extrusion + gradient face + inner shadows + rim + specular ----------
  // rounded polygon with per-vertex radius (pts: [x,y,r])
  function roundedPoly(pts) {
    const p = new Path2D();
    const n = pts.length;
    const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    const start = mid(pts[n - 1], pts[0]);
    p.moveTo(start[0], start[1]);
    for (let i = 0; i < n; i++) {
      const c = pts[i], nx = pts[(i + 1) % n];
      const m = mid(c, nx);
      p.arcTo(c[0], c[1], m[0], m[1], c[2] || 0);
    }
    p.closePath();
    return p;
  }
  // inner shadow: the casting fill is pushed far off-canvas in device space so only its shadow lands (no hairline)
  function innerShadow(ctx, path, rule, bb, color, blur, dx, dy) {
    const OFF = 5000;
    ctx.save();
    ctx.clip(path, rule);
    const p2 = new Path2D();
    const m = 400;
    p2.rect(bb[0] - m, bb[1] - m, bb[2] - bb[0] + 2 * m, bb[3] - bb[1] + 2 * m);
    p2.addPath(path);
    const M = ctx.getTransform();
    ctx.setTransform(new DOMMatrix().translate(OFF, 0).multiply(M));
    ctx.shadowColor = color; ctx.shadowBlur = blur; ctx.shadowOffsetX = dx - OFF; ctx.shadowOffsetY = dy;
    ctx.fillStyle = '#000';
    ctx.fill(p2, 'evenodd');
    ctx.restore();
  }
  let EXT = null;
  // o: {x,y,rot,s, path, rule, bb, face:[light,mid,dark], side:[light,dark], ext:[ex,ey], spec:[x,y,rx,ry]}
  function puffy(ctx, o) {
    const rule = o.rule || 'nonzero';
    const [ex, ey] = o.ext;
    const n = Math.ceil(Math.hypot(ex, ey) * 1.5);
    const W = ctx.canvas.width, Hh = ctx.canvas.height;
    const base = ctx.getTransform();
    let lc = ctx;
    if (!o.fast) {
      if (!EXT || EXT.width !== W) EXT = H.layer(W, Hh);
      lc = EXT.getContext('2d');
      lc.setTransform(1, 0, 0, 1, 0, 0); lc.clearRect(0, 0, W, Hh);
    } else ctx.save();
    const bounce = H.mix(o.side[0], '#ffffff', 0.35);
    for (let i = n; i >= 1; i--) {
      const k = i / n;
      lc.setTransform(base); lc.translate(o.x + ex * k, o.y + ey * k); lc.rotate(o.rot || 0); lc.scale(o.s, o.s);
      const c = k > 0.86 ? H.mix(o.side[1], bounce, (k - 0.86) / 0.14) : k < 0.25 ? H.mix(o.face[2], o.side[0], k / 0.25) : H.mix(o.side[0], o.side[1], (k - 0.25) / 0.61);
      lc.fillStyle = H.rgba(c);
      lc.fill(o.path, rule);
    }
    if (!o.fast) { ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.filter = 'blur(1.4px)'; ctx.drawImage(EXT, 0, 0); ctx.restore(); }
    else { ctx.restore(); ctx.setTransform(base); }
    ctx.save(); ctx.translate(o.x, o.y); ctx.rotate(o.rot || 0); ctx.scale(o.s, o.s);
    const bb = o.bb;
    const g = ctx.createLinearGradient(bb[0], bb[1], bb[2], bb[3]);
    g.addColorStop(0, H.rgba(o.face[0])); g.addColorStop(0.5, H.rgba(o.face[1])); g.addColorStop(1, H.rgba(o.face[2]));
    ctx.fillStyle = g; ctx.fill(o.path, rule);
    const S = o.s * Math.hypot(base.a, base.b);
    innerShadow(ctx, o.path, rule, bb, H.rgba(o.side[1], 0.5), 40 * S, -16 * S, -20 * S); // core shadow toward bottom-right
    innerShadow(ctx, o.path, rule, bb, H.rgba(o.side[0], 0.35), 14 * S, 0, 0);            // rounded falloff at every edge
    innerShadow(ctx, o.path, rule, bb, 'rgba(255,255,255,0.72)', 26 * S, 12 * S, 14 * S);  // soft top-left highlight
    if (o.spec) {
      ctx.save(); ctx.clip(o.path, rule);
      const [sx, sy, rx, ry] = o.spec;
      const sg = ctx.createRadialGradient(sx, sy, 0, sx, sy, rx);
      sg.addColorStop(0, 'rgba(255,255,255,0.95)'); sg.addColorStop(0.35, 'rgba(255,255,255,0.45)'); sg.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.translate(sx, sy); ctx.scale(1, ry / rx); ctx.translate(-sx, -sy);
      ctx.fillStyle = sg; ctx.beginPath(); ctx.arc(sx, sy, rx, 0, 7); ctx.fill();
      ctx.restore();
    }
    ctx.restore();
  }
  function sphere(ctx, x, y, r, light, mid, dark) {
    const g = ctx.createRadialGradient(x - r * 0.35, y - r * 0.4, r * 0.05, x, y, r * 1.05);
    g.addColorStop(0, H.rgba(light)); g.addColorStop(0.55, H.rgba(mid)); g.addColorStop(1, H.rgba(dark));
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
    const p = new Path2D(); p.arc(x, y, r, 0, 7);
    innerShadow(ctx, p, 'nonzero', [x - r, y - r, x + r, y + r], H.rgba(H.mix(light, '#ffffff', 0.5), 0.8), r * 0.12, -r * 0.05, -r * 0.06);
    const s = ctx.createRadialGradient(x - r * 0.38, y - r * 0.45, 0, x - r * 0.38, y - r * 0.45, r * 0.42);
    s.addColorStop(0, 'rgba(255,255,255,0.9)'); s.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = s; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
  }
  function contactShadow(ctx, x, y, w, h, alpha, blur) {
    ctx.save(); ctx.filter = `blur(${blur}px)`;
    ctx.fillStyle = `rgba(110,80,170,${alpha})`;
    ctx.beginPath(); ctx.ellipse(x, y, w, h, 0, 0, 7); ctx.fill();
    ctx.filter = `blur(${blur * 0.4}px)`; ctx.fillStyle = `rgba(90,60,150,${alpha * 0.8})`;
    ctx.beginPath(); ctx.ellipse(x, y, w * 0.55, h * 0.45, 0, 0, 7); ctx.fill();
    ctx.restore();
  }
  // ---------- shapes (local coords) ----------
  const bubblePath = () => roundedPoly([[-170, -115, 78], [170, -115, 78], [170, 95, 70], [-40, 95, 22], [-120, 160, 12], [-100, 95, 16], [-170, 95, 60]]);
  const BUBBLE_BB = [-170, -115, 170, 160];
  function gearPath(R, teeth, holeR) {
    const pts = [];
    const r0 = R * 0.78;
    for (let i = 0; i < teeth; i++) {
      const a = (i / teeth) * Math.PI * 2, w = (Math.PI * 2) / teeth;
      pts.push([Math.cos(a - w * 0.5) * r0, Math.sin(a - w * 0.5) * r0, R * 0.12]);
      pts.push([Math.cos(a - w * 0.2) * R, Math.sin(a - w * 0.2) * R, R * 0.1]);
      pts.push([Math.cos(a + w * 0.2) * R, Math.sin(a + w * 0.2) * R, R * 0.1]);
    }
    const p = roundedPoly(pts);
    p.moveTo(holeR, 0); p.arc(0, 0, holeR, 0, Math.PI * 2, true); p.closePath();
    return p;
  }
  const cursorPath = () => roundedPoly([[0, 0, 10], [0, 150, 12], [38, 114, 8], [64, 168, 10], [92, 154, 10], [66, 102, 8], [114, 102, 12]]);
  const CURSOR_BB = [0, 0, 114, 168];
  function bulbGlassPath(r) {
    const p = new Path2D();
    // glass: big circle flowing into a neck
    p.moveTo(-r * 0.5, r * 0.95);
    p.bezierCurveTo(-r * 0.55, r * 0.6, -r, r * 0.45, -r, -0.05 * r);
    p.arc(0, -0.05 * r, r, Math.PI, 0);
    p.bezierCurveTo(r, r * 0.45, r * 0.55, r * 0.6, r * 0.5, r * 0.95);
    p.closePath();
    return p;
  }
  function ringPath(R, r) {
    const p = new Path2D();
    p.ellipse(0, 0, R, R * 0.42, 0, 0, Math.PI * 2);
    p.moveTo(r, 0); p.ellipse(0, 0, r, r * 0.36, 0, 0, Math.PI * 2, true);
    return p;
  }

  // ================= EXPLAINER: a wide pastel set the camera dollies across (with parallax), clay props springing in =================
  const HX = (h) => H.hex(h);
  const PAL = {
    lav: { face: [HX('#e6e0ff'), HX('#b9abff'), HX('#9a88f5')], side: [HX('#8f7cf0'), HX('#5d48c2')] },
    peach: { face: [HX('#fff0e6'), HX('#ffcfb3'), HX('#ffad8a')], side: [HX('#f79d7a'), HX('#cf6b4f')] },
    mint: { face: [HX('#e6fff6'), HX('#b3eedb'), HX('#86d7bf')], side: [HX('#7fcbb3'), HX('#4f9f8a')] },
    white: { face: [HX('#ffffff'), HX('#f7f3ff'), HX('#e2d9fb')], side: [HX('#d4c8f5'), HX('#9a87de')] },
    pink: { face: [HX('#ffe3ea'), HX('#ffb1c2'), HX('#ff8fa8')], side: [HX('#f57f9b'), HX('#cc4f72')] },
    blue: { face: [HX('#e3f1ff'), HX('#b4d6ff'), HX('#8fbaf5')], side: [HX('#86b0ee'), HX('#5a7fc7')] },
    coral: { face: [HX('#ffd9d2'), HX('#ff8f7e'), HX('#f2675a')], side: [HX('#e85d4f'), HX('#b23a33')] },
    butter: { face: [HX('#fffbe0'), HX('#ffe58f'), HX('#f7c45e')], side: [HX('#f2b955'), HX('#d98f3a')] },
  };
  const pill = (w, h) => roundedPoly([[-w / 2, -h / 2, h / 2], [w / 2, -h / 2, h / 2], [w / 2, h / 2, h / 2], [-w / 2, h / 2, h / 2]]);
  const rrect = (w, h, r) => roundedPoly([[-w / 2, -h / 2, r], [w / 2, -h / 2, r], [w / 2, h / 2, r], [-w / 2, h / 2, r]]);
  function clay(ctx, path, bb, x, y, pal, o = {}) {
    puffy(ctx, { x, y, rot: o.rot || 0, s: o.s || 1, path, bb, face: pal.face, side: pal.side, ext: o.ext || [6, 11], spec: o.spec, fast: o.fast, z: o.z });
  }
  function clayPet(ctx, kind, x, y, r) {
    const fur = kind === 'cat' ? [HX('#efeaff'), HX('#c4b8ff'), HX('#9a88f5')] : [HX('#fff1e2'), HX('#ffcf9e'), HX('#e9a46a')];
    ctx.save();
    if (kind === 'cat') for (const sx of [-1, 1]) { const g = ctx.createLinearGradient(x, y - r * 1.2, x, y); g.addColorStop(0, H.rgba(fur[0])); g.addColorStop(1, H.rgba(fur[2])); ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x + sx * 0.88 * r, y - 0.15 * r); ctx.quadraticCurveTo(x + sx * 0.8 * r, y - 1.25 * r, x + sx * 0.6 * r, y - 1.12 * r); ctx.quadraticCurveTo(x + sx * 0.3 * r, y - 0.95 * r, x + sx * 0.1 * r, y - 0.8 * r); ctx.closePath(); ctx.fill(); }
    else for (const sx of [-1, 1]) { ctx.fillStyle = H.rgba(H.mix(fur[2], '#8a5a3b', 0.3)); ctx.beginPath(); ctx.ellipse(x + sx * 0.9 * r, y + 0.05 * r, 0.3 * r, 0.62 * r, sx * 0.35, 0, 7); ctx.fill(); }
    sphere(ctx, x, y, r, fur[0], fur[1], fur[2]);
    ctx.fillStyle = '#3b2f5c';
    for (const sx of [-1, 1]) { ctx.beginPath(); ctx.ellipse(x + sx * 0.36 * r, y - 0.08 * r, r * 0.1, r * 0.14, 0, 0, 7); ctx.fill(); ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x + sx * 0.36 * r - r * 0.03, y - 0.13 * r, r * 0.035, 0, 7); ctx.fill(); ctx.fillStyle = '#3b2f5c'; }
    ctx.fillStyle = 'rgba(255,120,150,0.45)'; for (const sx of [-1, 1]) { ctx.beginPath(); ctx.ellipse(x + sx * 0.6 * r, y + 0.22 * r, r * 0.15, r * 0.09, 0, 0, 7); ctx.fill(); }
    ctx.fillStyle = kind === 'cat' ? '#ff8fa8' : '#3b2f5c'; ctx.beginPath(); ctx.ellipse(x, y + 0.2 * r, r * (kind === 'cat' ? 0.09 : 0.16), r * (kind === 'cat' ? 0.07 : 0.11), 0, 0, 7); ctx.fill();
    ctx.restore();
  }
  function clayLabel(ctx, x, y, text, pal, o = {}) {
    const k = o.k ?? 1; if (k <= 0.01) return;
    ctx.save(); ctx.translate(x, y); ctx.scale(k, k);
    ctx.font = o.font || '700 28px "Fredoka"';
    const fsz = parseInt((ctx.font.match(/(\d+)px/) || [0, 28])[1]);
    const w = ctx.measureText(text).width + (o.padX || fsz * 1.5), h = o.h || Math.round(fsz * 1.8);
    clay(ctx, pill(w, h), [-w / 2, -h / 2, w / 2, h / 2], 0, 0, pal, { ext: [3, 6], fast: true, z: o.z });
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const col = o.col || '#4a3a8a';
    if (col === '#fff') { ctx.fillStyle = 'rgba(70,45,170,0.32)'; ctx.fillText(text, fsz * 0.06, 2 + fsz * 0.09); } // pressed-in ink shadow, like the bubble text
    else { ctx.fillStyle = 'rgba(255,255,255,0.55)'; ctx.fillText(text, 0, 3.5); }                                 // dark text: soft lower highlight (debossed)
    ctx.fillStyle = col; ctx.fillText(text, 0, 2);
    ctx.restore();
  }
  function clayTube(ctx, a, c, b, prog, pal, w = 14) {
    if (prog <= 0) return null;
    const q = (u) => [(1 - u) * (1 - u) * a[0] + 2 * u * (1 - u) * c[0] + u * u * b[0], (1 - u) * (1 - u) * a[1] + 2 * u * (1 - u) * c[1] + u * u * b[1]];
    const N = 36, pts = []; for (let i = 0; i <= N; i++) pts.push(q(prog * i / N * 0.93));
    const path = (off) => { ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0] + off[0], p[1] + off[1]) : ctx.moveTo(p[0] + off[0], p[1] + off[1])); };
    ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.strokeStyle = 'rgba(90,60,150,0.18)'; ctx.lineWidth = w; path([3, 7]); ctx.stroke();
    ctx.strokeStyle = H.rgba(pal.side[1]); ctx.lineWidth = w; path([0, 0]); ctx.stroke();
    ctx.strokeStyle = H.rgba(pal.face[1]); ctx.lineWidth = w * 0.72; path([-w * 0.1, -w * 0.12]); ctx.stroke();
    ctx.strokeStyle = 'rgba(255,255,255,0.75)'; ctx.lineWidth = w * 0.2; path([-w * 0.2, -w * 0.25]); ctx.stroke();
    const e = q(prog), e0 = q(Math.max(0, prog - 0.05)), ang = Math.atan2(e[1] - e0[1], e[0] - e0[0]);
    ctx.restore();
    const hp = roundedPoly([[w * 1.3, 0, w * 0.35], [-w * 0.9, -w * 1.15, w * 0.35], [-w * 0.9, w * 1.15, w * 0.35]]);
    clay(ctx, hp, [-w, -w, w, w], e[0], e[1], pal, { rot: ang, ext: [3, 6], fast: true });
    return q;
  }

  function background(ctx, W, H_, t) {
    const bg = ctx.createLinearGradient(0, 0, 0, H_);
    bg.addColorStop(0, '#f3ecff'); bg.addColorStop(0.5, '#e8dffb'); bg.addColorStop(0.62, '#dccff5'); bg.addColorStop(0.78, '#e6dcf9'); bg.addColorStop(1, '#efe7fe');
    ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H_);
    const glow = ctx.createRadialGradient(W * 0.5, H_ * 0.35, 40, W * 0.5, H_ * 0.35, 700);
    glow.addColorStop(0, 'rgba(255,250,255,0.8)'); glow.addColorStop(1, 'rgba(255,250,255,0)');
    ctx.fillStyle = glow; ctx.fillRect(0, 0, W, H_);
  }
  function finish(ctx, W, H_, t) { H.grain(ctx, W, H_, 0.018, 9 + Math.floor(t * 12)); }
  window.CLAY = { roundedPoly, innerShadow, puffy, sphere, contactShadow, bubblePath, BUBBLE_BB,
    gearPath, cursorPath, CURSOR_BB, bulbGlassPath, ringPath, PAL, pill, rrect, clay, clayPet, clayLabel, clayTube, background, finish };
  window.STYLE = { fonts: ['600 44px "Fredoka"', '700 64px "Fredoka"'], finish };
})();
