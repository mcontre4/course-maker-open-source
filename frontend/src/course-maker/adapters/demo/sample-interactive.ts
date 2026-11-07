import type { InteractiveDetails } from "../../domain/lesson-interactive";

type PendulumSettings = Readonly<{
  gravity: number;
  length: number;
  mass: number;
  angle: number;
  resistance: number;
  graph: boolean;
}>;

const defaults: PendulumSettings = {
  gravity: 9.81,
  length: 1.2,
  mass: 1,
  angle: 30,
  resistance: 0,
  graph: true,
};

/** Reads the requests made so far, so asking for a change visibly changes something. */
function settingsFrom(requests: readonly string[]): PendulumSettings {
  return requests.reduce<PendulumSettings>((settings, request) => {
    const text = request.toLowerCase();
    const next = { ...settings };
    if (/\bmoon\b/.test(text)) next.gravity = 1.62;
    if (/\bmars\b/.test(text)) next.gravity = 3.71;
    if (/\bjupiter\b/.test(text)) next.gravity = 24.79;
    if (/\b(air|drag|damp|resistance|friction)/.test(text))
      next.resistance = 0.25;
    if (/\b(longer|long string)\b/.test(text)) next.length = 2.2;
    if (/\b(shorter|short string)\b/.test(text)) next.length = 0.6;
    if (/\b(no|hide|remove|without)\b.*\b(graph|chart|trace)\b/.test(text))
      next.graph = false;
    if (/\b(add|show)\b.*\b(graph|chart|trace)\b/.test(text)) next.graph = true;
    return next;
  }, defaults);
}

/** Stands in for the server's builder: drafts the pendulum lab for any description. */
export function sampleInteractiveDetails(): InteractiveDetails {
  return {
    title: "Pendulum lab",
    goal: "Find out which settings change how long one swing takes, and which don’t.",
    prompts: [
      "Double the length. Does one swing take twice as long?",
      "Change only the mass. Predict the swing time first, then test it.",
      "Switch to the Moon. Why does the swing slow down?",
      "Turn up air resistance. Now does a heavier bob behave differently?",
    ],
  };
}

export function sampleInteractiveHtml(requests: readonly string[]): string {
  const settings = settingsFrom(requests);
  const matches = requests.some((request) =>
    /pendul|swing|gravity|oscillat/i.test(request),
  );
  return template
    .replace("__SETTINGS__", JSON.stringify(settings))
    .replace("__NOTICE__", matches ? "" : notice);
}

const notice = `<p class="notice">Sample interactive. The real builder will follow your description.</p>`;

const template = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pendulum lab</title>
<style>
  :root { --ink:#292b28; --muted:#686b62; --line:#e6e3db; --paper:#fdfcf9; --accent:#6f5a96; --soft:#e7dff4; --warm:#b5583a; --sage:#4d6b47; }
  * { box-sizing:border-box; }
  html, body { height:100%; margin:0; }
  body { display:flex; flex-direction:column; font:14px/1.45 Manrope,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--paper); }
  .notice { margin:0; padding:8px 16px; background:#fbe4d5; font-size:12.5px; font-weight:600; }
  main { flex:1; min-height:0; display:grid; grid-template-columns:minmax(0,1fr) 300px; }
  .bench { position:relative; display:flex; flex-direction:column; min-width:0; min-height:0; }
  canvas { display:block; width:100%; }
  #swing { flex:1; min-height:220px; touch-action:none; cursor:grab; }
  #swing:active { cursor:grabbing; }
  #trace { height:84px; flex:none; border-top:1px solid var(--line); }
  .readouts { position:absolute; top:14px; left:16px; display:flex; flex-wrap:wrap; gap:18px; pointer-events:none; }
  .readouts div { display:flex; flex-direction:column; }
  .readouts b { font-size:22px; font-weight:800; letter-spacing:-.02em; font-variant-numeric:tabular-nums; line-height:1.15; }
  .readouts span { color:var(--muted); font-size:12px; }
  aside { display:flex; flex-direction:column; gap:15px; padding:16px; border-left:1px solid var(--line); background:#fff; overflow:auto; }
  label { display:grid; grid-template-columns:1fr auto; gap:3px 8px; font-weight:700; font-size:13px; }
  output { color:var(--accent); font-weight:800; font-variant-numeric:tabular-nums; }
  input[type=range] { grid-column:1/-1; width:100%; margin:0; height:24px; accent-color:var(--accent); }
  .worlds { display:grid; grid-template-columns:repeat(4,1fr); gap:4px; margin-top:-7px; }
  button { min-height:34px; padding:4px; border:1px solid var(--line); border-radius:9px; background:#fff; color:var(--ink); font:inherit; font-size:12.5px; font-weight:700; cursor:pointer; }
  button:hover { background:var(--paper); }
  button[aria-pressed=true] { border-color:var(--accent); background:var(--soft); }
  button:focus-visible, input:focus-visible, canvas:focus-visible { outline:3px solid var(--accent); outline-offset:2px; }
  .actions { display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:auto; }
  .actions button { min-height:40px; }
  #play { background:var(--ink); border-color:var(--ink); color:#fff; }
  @media (max-width:640px) {
    main { grid-template-columns:1fr; grid-template-rows:minmax(300px,1fr) auto; overflow:auto; }
    aside { border-left:0; border-top:1px solid var(--line); overflow:visible; }
    #trace { height:64px; }
  }
</style>
</head>
<body>
__NOTICE__
<main>
  <section class="bench" aria-label="Pendulum">
    <canvas id="swing" tabindex="0" role="img" aria-label="Pendulum. Drag the bob to set its starting angle."></canvas>
    <div class="readouts" aria-live="off">
      <div><b id="period">0.00 s</b><span>One full swing</span></div>
      <div><b id="speed">0.00 m/s</b><span>Bob speed</span></div>
    </div>
    <canvas id="trace" aria-hidden="true"></canvas>
  </section>
  <aside aria-label="Pendulum controls">
    <label>Gravity<output id="gravityOut"></output><input id="gravity" type="range" min="0.5" max="26" step="0.01"></label>
    <div class="worlds" role="group" aria-label="Gravity presets">
      <button type="button" data-g="1.62">Moon</button>
      <button type="button" data-g="3.71">Mars</button>
      <button type="button" data-g="9.81">Earth</button>
      <button type="button" data-g="24.79">Jupiter</button>
    </div>
    <label>String length<output id="lengthOut"></output><input id="length" type="range" min="0.3" max="2.5" step="0.05"></label>
    <label>Bob mass<output id="massOut"></output><input id="mass" type="range" min="0.2" max="5" step="0.1"></label>
    <label>Starting angle<output id="angleOut"></output><input id="angle" type="range" min="5" max="85" step="1"></label>
    <label>Air resistance<output id="resistanceOut"></output><input id="resistance" type="range" min="0" max="1" step="0.01"></label>
    <div class="actions">
      <button type="button" id="play">Pause</button>
      <button type="button" id="restart">Restart swing</button>
    </div>
  </aside>
</main>
<script>
(function () {
  var initial = __SETTINGS__;
  var s = Object.assign({}, initial);
  var $ = function (id) { return document.getElementById(id); };
  var swing = $("swing"), trace = $("trace");
  var ctx = swing.getContext("2d"), tctx = trace.getContext("2d");
  var calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var theta, omega, clock = 0, lastCross, period, history, last, dragging = false, running = !calm;
  var fields = {
    gravity: function (v) { return v.toFixed(2) + " m/s²"; },
    length: function (v) { return v.toFixed(2) + " m"; },
    mass: function (v) { return v.toFixed(1) + " kg"; },
    angle: function (v) { return Math.round(v) + "°"; },
    resistance: function (v) { return v === 0 ? "Off" : v.toFixed(2); }
  };
  function restart() {
    theta = s.angle * Math.PI / 180; omega = 0; lastCross = null; period = null; history = [];
  }
  function show() {
    Object.keys(fields).forEach(function (key) {
      $(key).value = s[key];
      $(key + "Out").textContent = fields[key](s[key]);
    });
    document.querySelectorAll("[data-g]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(Math.abs(Number(b.dataset.g) - s.gravity) < 0.01));
    });
    $("play").textContent = running ? "Pause" : "Play";
  }
  Object.keys(fields).forEach(function (key) {
    $(key).addEventListener("input", function (e) {
      s[key] = Number(e.target.value);
      if (key === "angle") restart();
      lastCross = null; period = null;
      show(); draw();
    });
  });
  document.querySelectorAll("[data-g]").forEach(function (b) {
    b.addEventListener("click", function () { s.gravity = Number(b.dataset.g); lastCross = null; period = null; show(); draw(); });
  });
  $("play").addEventListener("click", function () { running = !running; show(); });
  $("restart").addEventListener("click", function () { restart(); running = true; show(); });
  function step(dt) {
    // Drag slows a light bob more than a heavy one, so mass only matters with air resistance on.
    var accel = -(s.gravity / s.length) * Math.sin(theta) - (s.resistance / s.mass) * omega;
    omega += accel * dt;
    clock += dt;
    var before = theta;
    theta += omega * dt;
    if (before < 0 && theta >= 0) {
      if (lastCross !== null) period = clock - lastCross;
      lastCross = clock;
    }
  }
  function size(canvas, context) {
    var ratio = window.devicePixelRatio || 1;
    var w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.round(w * ratio) || canvas.height !== Math.round(h * ratio)) {
      canvas.width = Math.round(w * ratio); canvas.height = Math.round(h * ratio);
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { w: w, h: h };
  }
  function geometry(box) {
    var pivot = { x: box.w / 2, y: 78 };
    var scale = (box.h - pivot.y - 44) / 2.6;
    var reach = s.length * scale;
    return { pivot: pivot, reach: reach, bob: { x: pivot.x + reach * Math.sin(theta), y: pivot.y + reach * Math.cos(theta) } };
  }
  function draw() {
    var box = size(swing, ctx), g = geometry(box);
    ctx.clearRect(0, 0, box.w, box.h);
    ctx.strokeStyle = "#e6e3db"; ctx.lineWidth = 1; ctx.setLineDash([3, 5]);
    ctx.beginPath(); ctx.arc(g.pivot.x, g.pivot.y, g.reach, Math.PI * 0.05, Math.PI * 0.95); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(g.pivot.x, g.pivot.y); ctx.lineTo(g.pivot.x, g.pivot.y + g.reach); ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = "#292b28"; ctx.lineWidth = 3; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(g.pivot.x - 34, g.pivot.y); ctx.lineTo(g.pivot.x + 34, g.pivot.y); ctx.stroke();
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(g.pivot.x, g.pivot.y); ctx.lineTo(g.bob.x, g.bob.y); ctx.stroke();
    var radius = 10 + Math.sqrt(s.mass) * 9;
    ctx.fillStyle = "#6f5a96";
    ctx.beginPath(); ctx.arc(g.bob.x, g.bob.y, radius, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,.28)";
    ctx.beginPath(); ctx.arc(g.bob.x - radius * .3, g.bob.y - radius * .3, radius * .32, 0, Math.PI * 2); ctx.fill();
    $("period").textContent = period ? period.toFixed(2) + " s" : "Timing…";
    $("speed").textContent = Math.abs(omega * s.length).toFixed(2) + " m/s";
    drawTrace();
  }
  function drawTrace() {
    trace.style.display = s.graph ? "" : "none";
    if (!s.graph) return;
    var box = size(trace, tctx), mid = box.h / 2;
    tctx.clearRect(0, 0, box.w, box.h);
    tctx.strokeStyle = "#e6e3db"; tctx.lineWidth = 1;
    tctx.beginPath(); tctx.moveTo(0, mid); tctx.lineTo(box.w, mid); tctx.stroke();
    tctx.fillStyle = "#686b62"; tctx.font = "600 11px sans-serif"; tctx.fillText("Angle over time", 12, 15);
    tctx.strokeStyle = "#b5583a"; tctx.lineWidth = 2; tctx.lineJoin = "round";
    tctx.beginPath();
    history.forEach(function (value, i) {
      var x = box.w - (history.length - 1 - i) * 1.5;
      var y = mid - (value / (Math.PI / 2)) * (mid - 8);
      if (i === 0) tctx.moveTo(x, y); else tctx.lineTo(x, y);
    });
    tctx.stroke();
  }
  function frame(now) {
    if (running && !dragging && last) {
      var elapsed = Math.min((now - last) / 1000, 0.05);
      var steps = Math.ceil(elapsed / 0.002);
      for (var i = 0; i < steps; i++) step(elapsed / steps);
      history.push(theta);
      if (history.length > 1200) history.shift();
    }
    last = now;
    draw();
    requestAnimationFrame(frame);
  }
  function aim(event) {
    var rect = swing.getBoundingClientRect();
    var g = geometry({ w: rect.width, h: rect.height });
    var next = Math.atan2(event.clientX - rect.left - g.pivot.x, event.clientY - rect.top - g.pivot.y);
    theta = Math.max(-1.5, Math.min(1.5, next)); omega = 0;
    s.angle = Math.max(5, Math.min(85, Math.round(Math.abs(theta) * 180 / Math.PI)));
    lastCross = null; period = null; history = []; show();
  }
  swing.addEventListener("pointerdown", function (event) { dragging = true; swing.setPointerCapture(event.pointerId); aim(event); });
  swing.addEventListener("pointermove", function (event) { if (dragging) aim(event); });
  swing.addEventListener("pointerup", function () { dragging = false; running = true; show(); });
  swing.addEventListener("pointercancel", function () { dragging = false; });
  restart(); show(); requestAnimationFrame(frame);
})();
</script>
</body>
</html>`;
