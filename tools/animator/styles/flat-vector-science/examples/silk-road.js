// Worked example: drawing and visual choreography, not lesson facts to copy.
const {sky,finish,glow,spark,crescent,ball,arrow,text,pill,rr,bez,seg,back}=FV;
const C={ink:"#141846",yellow:"#ffd23f",pink:"#ff5d8f",cyan:"#56e8ff",tan:["#ffe9be","#ecb676","#b4723c"]};
const TAU=Math.PI*2, cl=H.clamp,lerp=H.lerp,eo=H.ease.out,eio=H.ease.inOut;
function shape(param, t, gain, dur, a, hold) {
      a = Math.min(a == null ? 0.004 : a, dur * 0.9);
      hold = Math.min(hold || 0, dur - a);
      param.setValueAtTime(0, t);
      param.linearRampToValueAtTime(gain, t + a);
      if (hold > 0) param.setValueAtTime(gain, t + a + hold);
      param.exponentialRampToValueAtTime(TINY, t + dur);
      param.setValueAtTime(0, t + dur + 0.001);
    }
    function out(node, p) {
      const pan = ctx.createStereoPanner(); pan.pan.value = Math.max(-1, Math.min(1, p.pan || 0));
      node.connect(pan); pan.connect(bus[p.bus || 'sfx']);
      if (p.verb) { const s = ctx.createGain(); s.gain.value = p.verb; pan.connect(s); s.connect(verbIn); }
    }
    function filterNode(p, t) {
      if (!p.filter) return null;
      const f = ctx.createBiquadFilter(); f.type = p.filter; f.Q.value = p.q == null ? 1 : p.q;
      sweep(f.frequency, p.f == null ? 1000 : p.f, t);
      return f;
    }

    // ---- primitives
    // tone(t, { f, type, dur, gain, a, hold, pan, verb, bus, filter, f2 (filter freq), q, detune })
    function tone(time, p) {
      const t = at(time), dur = p.dur || 0.2;
      if (t + dur < ctx.currentTime || (time < T0 - 0.001 && dur < 1.5)) return;
      const osc = ctx.createOscillator(); osc.type = p.type || 'sine';
      sweep(osc.frequency, Array.isArray(p.f) ? p.f.map(([d, v]) => [d, hz(v)]) : hz(p.f || 440), t);
      if (p.detune) osc.detune.value = p.detune;
      const g = ctx.createGain(); shape(g.gain, t, gainOf(p, 0.3), dur, p.a, p.hold);
      let node = osc;
      if (p.filter) { const f = ctx.createBiquadFilter(); f.type = p.filter; f.Q.value = p.q == null ? 0.8 : p.q; sweep(f.frequency, p.f2 || 2000, t); osc.connect(f); node = f; }
      node.connect(g); out(g, p);
      osc.start(t); osc.stop(t + dur + 0.02);
    }
    // noise(t, { dur, color, filter, f, q, gain, a, hold, pan, verb, bus, rate })
    function noise(time, p) {
      const t = at(time), dur = p.dur || 0.2;
      if (t + dur < ctx.currentTime || (time < T0 - 0.001 && dur < 1.5)) return;
      const src = ctx.createBufferSource(); src.buffer = noiseBuf[p.color || 'white']; src.loop = true;
      if (p.rate) src.playbackRate.value = p.rate;
      const g = ctx.createGain(); shape(g.gain, t, gainOf(p, 0.3), dur, p.a, p.hold);
      const f = filterNode(p, t);
      if (f) { src.connect(f); f.connect(g); } else src.connect(g);
      out(g, p);
      const off = rand('off' + time + (p.f || ''))() * 2;
      src.start(t, off); src.stop(t + dur + 0.02);
    }

    // ---- named sounds. play(name, t, opts): opts.gain scales the whole sound, opts.pan places it.
    const S = {
      // UI / motion graphics
      pop: (t, o) => { tone(t, { f: [[0, o.f || 620], [0.07, (o.f || 620) * 0.45]], dur: 0.1, gain: 0.32 * o.g, pan: o.pan }); noise(t, { dur: 0.012, filter: 'highpass', f: 3000, gain: 0.12 * o.g, pan: o.pan }); },
      tick: (t, o) => noise(t, { dur: 0.018, filter: 'bandpass', f: o.f || 4200, q: 2.5, gain: 0.3 * o.g, pan: o.pan }),
      click: (t, o) => { tone(t, { f: o.f || 1900, type: 'square', dur: 0.02, gain: 0.08 * o.g, filter: 'lowpass', f2: 3000, pan: o.pan }); noise(t, { dur: 0.01, filter: 'highpass', f: 2500, gain: 0.15 * o.g, pan: o.pan }); },
      tock: (t, o) => { tone(t, { f: o.f || 820, dur: 0.07, gain: 0.25 * o.g, pan: o.pan }); noise(t, { dur: 0.05, filter: 'bandpass', f: o.f || 820, q: 9, gain: 0.35 * o.g, pan: o.pan }); },
      blip: (t, o) => tone(t, { f: o.f || 'E6', type: o.type || 'square', dur: o.dur || 0.07, gain: 0.07 * o.g, a: 0.002, hold: (o.dur || 0.07) * 0.6, pan: o.pan }),
      whoosh: (t, o) => { const d = o.dur || 0.45; noise(t, { dur: d, color: 'pink', filter: 'bandpass', f: [[0, 350], [d * 0.55, o.top || 2600], [d, 700]], q: 0.9, gain: 0.32 * o.g, a: d * 0.5, pan: o.pan, verb: 0.15 }); },
      swish: (t, o) => { const d = o.dur || 0.18; noise(t, { dur: d, filter: 'highpass', f: [[0, 1800], [d, 5200]], q: 0.7, gain: 0.22 * o.g, a: d * 0.35, pan: o.pan }); },
      riser: (t, o) => { const d = o.dur || 0.8; noise(t, { dur: d, color: 'pink', filter: 'bandpass', f: [[0, 300], [d, 4000]], q: 1.2, gain: 0.25 * o.g, a: d * 0.95, pan: o.pan, verb: 0.2 }); tone(t, { f: [[0, 180], [d, 720]], type: 'triangle', dur: d, gain: 0.06 * o.g, a: d * 0.9 }); },
      thud: (t, o) => { tone(t, { f: [[0, o.f || 130], [0.16, 42]], dur: 0.26, gain: 0.55 * o.g, pan: o.pan }); noise(t, { dur: 0.09, color: 'brown', filter: 'lowpass', f: 500, gain: 0.35 * o.g, pan: o.pan }); },
      impact: (t, o) => { S.thud(t, o); noise(t, { dur: 0.7, color: 'pink', filter: 'lowpass', f: [[0, 2400], [0.6, 300]], gain: 0.3 * o.g, verb: 0.35, pan: o.pan }); },
      stamp: (t, o) => { S.thud(t, { ...o, f: 160 }); noise(t, { dur: 0.05, filter: 'bandpass', f: 1300, q: 1.2, gain: 0.4 * o.g, pan: o.pan }); noise(t + 0.004, { dur: 0.012, filter: 'highpass', f: 3500, gain: 0.25 * o.g, pan: o.pan }); },
      ding: (t, o) => { const f = hz(o.f || 'E6'); tone(t, { f, dur: 1.3, gain: 0.2 * o.g, verb: 0.3, pan: o.pan }); tone(t, { f: f * 2.76, dur: 0.5, gain: 0.05 * o.g, verb: 0.3, pan: o.pan }); },
      success: (t, o) => { S.ding(t, { ...o, f: o.f || 'C6' }); S.ding(t + 0.09, { ...o, f: hz(o.f || 'C6') * 1.5, g: o.g * 0.9 }); },
      error: (t, o) => { tone(t, { f: o.f || 'A3', type: 'square', dur: 0.13, gain: 0.09 * o.g, hold: 0.08, filter: 'lowpass', f2: 1400, pan: o.pan }); tone(t + 0.15, { f: hz(o.f || 'A3') * 0.8, type: 'square', dur: 0.22, gain: 0.09 * o.g, hold: 0.14, filter: 'lowpass', f2: 1200, pan: o.pan }); },
      buzz: (t, o) => { const d = o.dur || 0.3; tone(t, { f: o.f || 110, type: 'sawtooth', dur: d, gain: 0.12 * o.g, hold: d * 0.7, filter: 'lowpass', f2: 900, pan: o.pan }); tone(t, { f: (o.f || 110) * 1.01, type: 'sawtooth', dur: d, gain: 0.1 * o.g, hold: d * 0.7, filter: 'lowpass', f2: 900, pan: o.pan }); },
      sparkle: (t, o) => { const r = rand('sparkle' + t), notes = ['C6', 'D6', 'E6', 'G6', 'A6', 'C7']; for (let i = 0; i < (o.n || 6); i++) { const ti = t + i * 0.04 + r() * 0.01, f = hz(notes[Math.floor(r() * notes.length)]), pan = r() * 1.2 - 0.6; tone(ti, { f, dur: 0.6, gain: 0.04 * o.g, a: 0.002, verb: 0.35, pan }); tone(ti, { f: f * 2.76, dur: 0.2, gain: 0.012 * o.g, a: 0.002, pan }); } },
      glitch: (t, o) => { const r = rand('glitch' + t); for (let i = 0; i < 7; i++) tone(t + i * 0.022, { f: 200 + r() * 1800, type: 'square', dur: 0.02, gain: 0.07 * o.g, a: 0.001, hold: 0.015, pan: r() * 1.4 - 0.7 }); noise(t, { dur: 0.16, filter: 'bandpass', f: 2500, q: 0.6, gain: 0.12 * o.g }); },
      shutter: (t, o) => { S.click(t, o); noise(t + 0.06, { dur: 0.04, filter: 'bandpass', f: 2200, q: 1, gain: 0.2 * o.g, pan: o.pan }); },
      count: (t, o) => S.tick(t, { ...o, f: o.f || 5200, g: o.g * 0.7 }),

      // hand-made media
      // stroke: a pen/marker/chalk/pencil stroke over `dur` seconds. material sets the surface sound.
      stroke: (t, o) => {
        const d = o.dur || 0.4, m = o.material || 'marker', r = rand('stroke' + m + t);
        const M = {
          marker: { f: 2900, q: 2.2, g: 0.16, grain: 0.05 },
          chalk: { f: 1700, q: 0.6, g: 0.22, grain: 0.028 },
          pencil: { f: 4600, q: 0.8, g: 0.16, grain: 0.04, filter: 'highpass' },
          pen: { f: 4200, q: 1.6, g: 0.08, grain: 0.06 },
          brush: { f: 900, q: 0.5, g: 0.1, grain: 0.09, color: 'pink' },
          sharpie: { f: 2400, q: 1.4, g: 0.2, grain: 0.045 },
        }[m];
        for (let x = 0; x < d; x += M.grain * (0.7 + r() * 0.6)) {
          const gd = M.grain * (0.8 + r() * 0.9);
          noise(t + x, { dur: gd, color: M.color, filter: M.filter || 'bandpass', f: M.f * (0.8 + r() * 0.4), q: M.q, gain: M.g * o.g * (0.6 + r() * 0.5), a: gd * 0.3, pan: (o.pan || 0) + (r() - 0.5) * 0.2 });
        }
      },
      // paper: picking up / slapping down / turning a sheet
      paper: (t, o) => { const d = o.dur || 0.35, r = rand('paper' + t); for (let x = 0; x < d; x += 0.025 + r() * 0.03) noise(t + x, { dur: 0.05, filter: 'bandpass', f: 1200 + r() * 2600, q: 0.9, gain: 0.12 * o.g * (1 - x / d * 0.5), pan: o.pan }); },
      slap: (t, o) => { noise(t, { dur: 0.07, filter: 'highpass', f: 900, gain: 0.45 * o.g, a: 0.001, pan: o.pan }); tone(t, { f: [[0, 180], [0.06, 70]], dur: 0.1, gain: 0.25 * o.g, pan: o.pan }); },
      tape: (t, o) => { noise(t, { dur: o.dur || 0.5, filter: 'bandpass', f: [[0, 900], [o.dur || 0.5, 2200]], q: 1.8, gain: 0.18 * o.g, a: 0.02, pan: o.pan }); },
      press: (t, o) => { S.thud(t, { ...o, f: 95, g: o.g * 0.9 }); noise(t + 0.01, { dur: 0.25, color: 'brown', filter: 'lowpass', f: 700, gain: 0.25 * o.g, pan: o.pan }); },
      roller: (t, o) => { const d = o.dur || 0.6; noise(t, { dur: d, color: 'brown', filter: 'bandpass', f: 380, q: 1.5, gain: 0.3 * o.g, a: 0.05, hold: d * 0.6, pan: o.pan }); for (let x = 0; x < d; x += 0.07) S.tock(t + x, { f: 300, g: o.g * 0.15, pan: o.pan }); },
      erase: (t, o) => { const d = o.dur || 0.6, r = rand('erase' + t); for (let x = 0; x < d; x += 0.06 + r() * 0.04) noise(t + x, { dur: 0.08, color: 'pink', filter: 'bandpass', f: 700 + r() * 500, q: 0.8, gain: 0.22 * o.g, a: 0.03, pan: (r() - 0.5) * 0.5 }); },

      // machines and screens
      key: (t, o) => { const r = rand('key' + t); noise(t, { dur: 0.025, filter: 'bandpass', f: 2600 + r() * 1200, q: 2, gain: 0.25 * o.g, a: 0.001, pan: o.pan }); tone(t, { f: 160 + r() * 40, dur: 0.04, gain: 0.12 * o.g, pan: o.pan }); },
      typing: (t, o) => { const r = rand('typing' + t), n = o.n || 8, rate = o.rate || 0.09; for (let i = 0; i < n; i++) S.key(t + i * rate * (0.75 + r() * 0.5), { g: o.g * (0.7 + r() * 0.4), pan: o.pan }); },
      typebar: (t, o) => { S.key(t, o); noise(t + 0.008, { dur: 0.03, filter: 'bandpass', f: 1100, q: 4, gain: 0.35 * o.g, pan: o.pan }); },
      bell: (t, o) => S.ding(t, { ...o, f: o.f || 'A6' }),
      boot: (t, o) => { tone(t, { f: [[0, 80], [0.35, 1600]], type: 'sine', dur: 0.5, gain: 0.08 * o.g, a: 0.3 }); S.blip(t + 0.45, { ...o, f: 'C6', dur: 0.12 }); },
      crtOn: (t, o) => { noise(t, { dur: 0.25, filter: 'highpass', f: 2000, gain: 0.2 * o.g, a: 0.001 }); tone(t, { f: 15700, dur: 1.5, gain: 0.02 * o.g, a: 0.1, hold: 1 }); S.thud(t, { ...o, f: 90, g: o.g * 0.5 }); },
      neon: (t, o) => { const d = o.dur || 0.25, r = rand('neon' + t); for (let x = 0; x < d; x += 0.035 + r() * 0.04) tone(t + x, { f: 120, type: 'sawtooth', dur: 0.03, gain: 0.3 * o.g * (0.5 + r() * 0.5), filter: 'bandpass', f2: 1200, q: 1.2, pan: o.pan }); },
      // chip (8-bit console) sounds: raw square/triangle, no filtering
      coin: (t, o) => { tone(t, { f: 'B5', type: 'square', dur: 0.07, gain: 0.07 * o.g, a: 0.001, hold: 0.06 }); tone(t + 0.07, { f: 'E6', type: 'square', dur: 0.3, gain: 0.07 * o.g, a: 0.001, hold: 0.1 }); },
      jump: (t, o) => tone(t, { f: [[0, 260], [0.16, 820]], type: 'square', dur: 0.18, gain: 0.07 * o.g, a: 0.001, hold: 0.12 }),
      hurt: (t, o) => { tone(t, { f: [[0, 600], [0.25, 90]], type: 'square', dur: 0.28, gain: 0.08 * o.g, a: 0.001, hold: 0.2 }); noise(t, { dur: 0.2, filter: 'lowpass', f: 1800, gain: 0.15 * o.g, rate: 0.25 }); },
      powerup: (t, o) => ['C5', 'E5', 'G5', 'C6', 'E6', 'G6', 'C7'].forEach((n, i) => tone(t + i * 0.045, { f: n, type: 'square', dur: 0.06, gain: 0.06 * o.g, a: 0.001, hold: 0.05 })),
      select: (t, o) => { S.blip(t, { ...o, f: 'A5', dur: 0.04 }); S.blip(t + 0.05, { ...o, f: 'E6', dur: 0.05 }); },
      text: (t, o) => { const n = o.n || 10, rate = o.rate || 0.05; for (let i = 0; i < n; i++) tone(t + i * rate, { f: i % 2 ? 'C6' : 'G5', type: 'square', dur: 0.025, gain: 0.04 * o.g, a: 0.001, hold: 0.015 }); },
    };

    function play(name, t, opts) {
      const fn = S[name];
      if (!fn) throw new Error('unknown sound: ' + name);
      const o2 = Object.assign({}, opts); o2.g = o2.gain == null ? 1 : o2.gain;
      if (opts && opts.minor) withMinor(() => fn(t, o2)); else fn(t, o2);
    }

    // everything scheduled inside fn counts as minor (quieter in voiceover mode)
    function withMinor(fn) { const was = inMinor; inMinor = true; try { fn(); } finally { inMinor = was; } }

    // ---- beds: continuous sound under a stretch of time. bed(name, t0, t1, opts)
    function bed(name, t0, t1, p) {
      if (VO) return;
      p = p || {}; const g = p.gain == null ? 1 : p.gain, d = t1 - t0, fade = Math.min(0.4, d / 4);
      const long = (q) => Object.assign({ dur: d, a: fade, hold: d - fade * 2, bus: 'amb' }, q);
      if (name === 'room') noise(t0, long({ color: 'brown', filter: 'lowpass', f: 320, gain: 0.12 * g }));
      else if (name === 'hiss') noise(t0, long({ color: 'pink', filter: 'highpass', f: 5000, gain: 0.02 * g }));
      else if (name === 'hum') { tone(t0, long({ f: 60, gain: 0.05 * g })); tone(t0, long({ f: 120, gain: 0.025 * g })); tone(t0, long({ f: 180, type: 'triangle', gain: 0.012 * g })); }
      else if (name === 'rain') { noise(t0, long({ color: 'pink', filter: 'bandpass', f: 2500, q: 0.4, gain: 0.08 * g })); const r = rand('rain'); for (let x = 0; x < d; x += 0.04 + r() * 0.08) noise(t0 + x, { dur: 0.01, filter: 'highpass', f: 4000, gain: 0.04 * g * r(), bus: 'amb', pan: r() * 1.6 - 0.8 }); }
      else if (name === 'projector') { noise(t0, long({ color: 'pink', filter: 'highpass', f: 3000, gain: 0.03 * g })); for (let x = 0; x < d; x += 1 / 24) S.tock(t0 + x, { f: 700, g: 0.04 * g, pan: 0.3 }); }
      else if (name === 'vinyl') { noise(t0, long({ color: 'pink', filter: 'bandpass', f: 1500, q: 0.5, gain: 0.025 * g })); const r = rand('vinyl'); for (let x = 0; x < d; x += 0.08 + r() * 0.4) noise(t0 + x, { dur: 0.006, filter: 'highpass', f: 2500, gain: 0.08 * g * r(), bus: 'amb' }); }
      else throw new Error('unknown bed: ' + name);
    }

    // ---- music: optional light beds that sit under the effects. music(name, t0, t1, { bpm, chords, gain })
    // chords: list of note arrays, one per bar, cycled. e.g. [['C4','E4','G4','B4'], ['A3','C4','E4','G4']]
    function music(name, t0, t1, p) {
      if (VO) return;
      p = p || {}; const g = p.gain == null ? 1 : p.gain, bpm = p.bpm || 100, beat = 60 / bpm, bar = beat * 4;
      const chords = p.chords || [['C4', 'E4', 'G4', 'B4'], ['A3', 'C4', 'E4', 'G4'], ['F3', 'A3', 'C4', 'E4'], ['G3', 'B3', 'D4', 'F4']];
      let i = 0;
      for (let t = t0; t < t1 - 0.05; t += bar, i++) {
        const ch = chords[i % chords.length], len = Math.min(bar, t1 - t);
        if (name === 'pad' || name === 'pulse') ch.forEach((n, k) => { tone(t, { f: n, type: 'triangle', dur: len + 0.3, gain: 0.035 * g, a: 0.25, hold: len - 0.3, bus: 'music', filter: 'lowpass', f2: 1400, pan: (k - 1.5) * 0.25, verb: 0.25 }); tone(t, { f: hz(n) * 1.004, type: 'sine', dur: len + 0.3, gain: 0.03 * g, a: 0.3, hold: len - 0.3, bus: 'music' }); });
        if (name === 'pulse') for (let b = 0; b < 4 && t + b * beat < t1 - 0.05; b++) {
          const tb = t + b * beat;
          tone(tb, { f: [[0, 110], [0.1, 50]], dur: 0.18, gain: (b % 2 ? 0.16 : 0.26) * g, bus: 'music' });
          noise(tb + beat / 2, { dur: 0.04, filter: 'highpass', f: 7000, gain: 0.05 * g, bus: 'music' });
          tone(tb + beat / 2, { f: hz(ch[0]) / 2, type: 'triangle', dur: beat * 0.45, gain: 0.08 * g, bus: 'music' });
        }
        if (name === 'chip') for (let s = 0; s < 8 && t + s * beat / 2 < t1 - 0.05; s++) {
          const ts = t + s * beat / 2;
          tone(ts, { f: hz(ch[0]) / 2, type: 'triangle', dur: beat * 0.45, gain: 0.12 * g, a: 0.001, hold: beat * 0.35, bus: 'music' });
          tone(ts, { f: ch[[0, 1, 2, 3, 2, 1, 2, 3][s]], type: 'square', dur: beat * 0.4, gain: 0.03 * g, a: 0.001, hold: beat * 0.25, bus: 'music' });
        }
      }
    }

    return { play, bed, music, tone, noise, withMinor, hz, vo: VO, sounds: Object.keys(S) };
  };

  // Live playback for a player: SOUND.live(scoreFn, fromT, { voiceover, master }) starts the score from explainer time
  // fromT right now and returns stop(). Call stop() on pause or seek, and SOUND.live again on play.
  SOUND.live = function (fn, fromT, opts) {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    fn(SOUND.kit(ctx, Object.assign({}, opts, { start: fromT || 0, delay: 0.03 })));
    return () => { try { ctx.close(); } catch (e) {} };
  };

  // Render a style's explainerSound into an OfflineAudioContext; returns interleaved float stereo.
  SOUND.renderOffline = async function (fn, duration, sampleRate, kitOpts) {
    const sr = sampleRate || 48000, len = Math.ceil(duration * sr);
    const ctx = new OfflineAudioContext(2, len, sr);
    fn(SOUND.kit(ctx, kitOpts || {}));
    const buf = await ctx.startRendering();
    const L = buf.getChannelData(0), R = buf.getChannelData(1), inter = new Float32Array(len * 2);
    let peak = 0;
    for (let i = 0; i < len; i++) { inter[2 * i] = L[i]; inter[2 * i + 1] = R[i]; peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i])); }
    return { inter, peak, frames: len, sr };
  };
})();

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

  // ---------- timeline of the explainer (shared with explainerSound) ----------
  const TL = {
    title: 0.15, titleShrink: [1.8, 2.4], robotIn: [0.5, 1.4], robotMove: [1.9, 2.8],
    arrow: [2.55, 3.1], count: [2.8, 5.6], travel: 1.5,
    zoom: [4.55, 5.8], sweep: [5.95, 6.85],
    catIn: [6.35, 6.95], guess: 6.95, bubble: 7.15, check: 7.6, wrong: 7.75,
    err: [8.05, 8.6], adjust: 8.6, zoomIn: [8.65, 9.1], rewire: [8.75, 9.35], zoomBack: [9.45, 9.85],
    guess2: 9.6, right: 9.75, toC: [10.3, 10.8], acc: [11.0, 12.55], hit: 12.55,
    take: [13.0, 13.75], line1: 13.3, line2: 13.55, D: 15,
  };
  // creature spawn times on the data stream
  const SPAWN = (() => { const a = []; let s = 2.75, i = 0; while (s < 5.3) { a.push(s); s += Math.max(0.18, 0.38 - i * 0.03); i++; } return a; })();
  const KIND = (i) => ['cat', 'dog', 'cat', 'cat', 'dog', 'dog', 'cat', 'dog'][i % 8];

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


const beats=[["0\u20132 s", "The Silk Roads", "A world connected by trade", "Hook: pull back from a silk ribbon to a glowing route network. The title moves into the corner at 2 s.", "Soft rising pluck; four route-point chimes."], ["2\u20135 s", "2nd century BCE", "Han missions expand connections", "Continuous: keep the same route network; pan east to Chang\u2019an. A scroll opens beside a Han-era gateway.", "Scroll flutter; low pluck on the date; point chime."], ["5\u20139 s", "Many routes. Many traders.", "Chang\u2019an \u2022 Samarkand \u2022 Mediterranean", "Continuous: pull back to reveal branches. A caravan follows one leg; goods pass between traders at an oasis.", "Soft hoof taps; dotted-route ticks; handover boops."], ["9\u201312 s", "More than silk", "Silk \u2022 spices \u2022 glass", "Scene change: a large silk ribbon sweeps across the lens, taking us from routes into a market close-up. Goods land one by one.", "Fabric flutter wipe; three warm wooden plucks."], ["12\u201316 s", "Ideas traveled, too", "Beliefs \u2022 knowledge \u2022 inventions", "Continuous: market objects move down; a manuscript, lotus, and compass rise along branching arrows.", "Page flutter; three glassy chimes; quiet pause."], ["16\u201320 s", "13th\u201314th centuries", "Mongol rule boosts exchange", "Scene change: dive into the compass glow and emerge above the route network. Extra links and relay stations illuminate.", "Soft airy bloom; relay-point chimes; fuller chord."], ["20\u201324 s", "Trade routes shifted", "Sea trade gained importance", "Continuous: camera glides south. Land routes dim but remain visible; a sailing ship follows a bright sea route.", "Low transition breath; water hush; ship-arrival pluck."], ["24\u201328 s", "Goods moved. Ideas spread.", "The Silk Roads connected cultures.", "Continuous: pull back to a circular network of cities and goods. Hold the completed takeaway for the last 1.5 s.", "Warm resolving chord; small final shimmer; fade."]];

function shape(x,pts,col){x.fillStyle=col;x.beginPath();pts.forEach((p,i)=>i?x.lineTo(...p):x.moveTo(...p));x.closePath();x.fill();}
function oval(x,a,b,rx,ry,col){x.fillStyle=col;x.beginPath();x.ellipse(a,b,rx,ry,0,0,TAU);x.fill();}
function box(x,a,b,w,h,col,r=18){x.fillStyle=col;rr(x,a,b,w,h,r);x.fill();}
function camel(x,a,b,s=1){x.save();x.translate(a,b);x.scale(s,s);oval(x,0,0,72,38,'#e9ad66');ball(x,-32,-28,26,C.tan);ball(x,25,-29,27,C.tan);box(x,51,-89,22,94,'#efbd79',10);oval(x,69,-91,29,18,'#f5c98c');shape(x,[[64,-104],[67,-120],[77,-104]],'#efbd79');for(const p of [-48,-20,24,48])box(x,p,17,12,70,'#d38b4b',6);box(x,-33,-18,65,38,'#d75179',8);box(x,-23,-15,45,8,'#ffcb68',3);oval(x,80,-94,3,4,C.ink);x.strokeStyle='#d38b4b';x.lineWidth=9;x.lineCap='round';x.beginPath();x.moveTo(-65,-1);x.quadraticCurveTo(-93,-20,-91,13);x.stroke();x.restore();}
function city(x,a,b,s=1){x.save();x.translate(a,b);x.scale(s,s);box(x,-65,-45,130,88,'#d89a64',5);box(x,-81,-76,30,120,'#f4c78e',5);box(x,51,-76,30,120,'#f4c78e',5);for(let i=-75;i<80;i+=22)box(x,i,-86,13,21,'#ffdc9d',2);x.fillStyle='#32274a';x.beginPath();x.moveTo(-20,43);x.lineTo(-20,0);x.arc(0,0,20,Math.PI,0);x.lineTo(20,43);x.fill();box(x,-90,43,180,10,'#b87259',4);x.restore();}
function silk(x,a,b,s=1){x.save();x.translate(a,b);x.scale(s,s);const g=x.createLinearGradient(-90,-60,90,70);g.addColorStop(0,'#ffb4dc');g.addColorStop(.5,'#f35b9c');g.addColorStop(1,'#aa3f88');x.fillStyle=g;x.beginPath();x.moveTo(-85,-55);x.bezierCurveTo(-20,-90,18,-12,90,-50);x.lineTo(90,58);x.bezierCurveTo(20,97,-20,17,-85,58);x.closePath();x.fill();x.strokeStyle='#ffce82';x.lineWidth=6;for(let i=0;i<3;i++){x.beginPath();x.moveTo(-76,-28+i*30);x.bezierCurveTo(-15,-60+i*30,20,22+i*30,82,-22+i*30);x.stroke();}x.restore();}
function scroll(x,a,b,s=1){x.save();x.translate(a,b);x.scale(s,s);box(x,-65,-68,130,136,'#ffe5aa',10);box(x,-79,-80,158,22,'#f2b56c',11);box(x,-79,58,158,22,'#d89655',11);for(let i=0;i<4;i++)box(x,-42,-38+i*24,i===3?55:85,6,'#b08a72',3);x.restore();}
function spice(x,a,b){shape(x,[[a-73,b+42],[a+73,b+42],[a+49,b-35],[a-49,b-35]],'#d6a269');oval(x,a,b-29,50,19,'#7b3f32');for(let i=0;i<22;i++)ball(x,a+Math.cos(i*2.4)*((i%5)*9),b-35+Math.sin(i*2.4)*12,7,['#ffcc67','#e89039','#b95426']);box(x,a-57,b-9,114,9,'#ffe5b2',4);}
function glass(x,a,b){x.save();glow(x,a,b,110,C.cyan,.22);shape(x,[[a-13,b-77],[a+13,b-77],[a+13,b-43],[a+47,b+27],[a+36,b+60],[a-36,b+60],[a-47,b+27],[a-13,b-43]],'#54d5e1');shape(x,[[a+3,b-57],[a+12,b-42],[a+39,b+28],[a+30,b+48],[a+17,b+48]],'#218aa6');box(x,a-20,b-84,40,14,'#a6fff2',7);box(x,a-23,b-10,8,44,'#c0ffff',4);x.restore();}
function compass(x,a,b,s=1){x.save();x.translate(a,b);x.scale(s,s);ball(x,0,0,75,['#fff1a4','#ffd15c','#bc773e']);ball(x,0,0,57,['#d3ffed','#61cfce','#357b9f']);shape(x,[[0,-47],[-15,14],[0,4],[15,14]],'#ec6583');shape(x,[[0,47],[-15,-14],[0,-4],[15,-14]],'#f9f4d5');x.restore();}
function lotus(x,a,b){for(let i=-2;i<=2;i++){x.save();x.translate(a,b);x.rotate(i*.35);oval(x,0,-26,22,59,i%2?'#e77bad':'#ffb5d4');x.restore();}oval(x,a,b+26,70,13,'#63cec1');}
function ship(x,a,b,s=1){x.save();x.translate(a,b);x.scale(s,s);shape(x,[[-90,29],[85,29],[56,70],[-60,70]],'#bd825a');box(x,-4,-110,9,150,'#f8ca83',4);shape(x,[[9,-105],[9,14],[88,14]],'#ffedbe');shape(x,[[-12,-82],[-12,14],[-77,14]],'#ffd78c');for(let j=0;j<3;j++){x.strokeStyle='#54d9e8';x.lineWidth=5;x.beginPath();x.moveTo(-120,83+j*18);x.bezierCurveTo(-20,61+j*18,20,102+j*18,120,80+j*18);x.stroke();}x.restore();}
const nodes=[[200,342],[490,300],[750,350],[1080,382]];
function network(x,sea=false){shape(x,[[115,272],[221,213],[325,232],[418,185],[586,231],[689,215],[791,250],[920,207],[1142,283],[1181,411],[1077,454],[985,439],[910,504],[809,466],[717,492],[654,437],[568,480],[473,421],[376,431],[306,372],[194,398]],'#38366c');shape(x,[[505,430],[582,477],[595,555],[534,528],[478,456]],'#353262');shape(x,[[798,460],[858,496],[841,554],[818,506]],'#484072');for(let i=0;i<3;i++){const [a,b]=[nodes[i],nodes[i+1]];arrow(x,[a,[a[0]+95,a[1]-60],[b[0]-70,b[1]+40],b],1,C.yellow,7,{dots:true});}arrow(x,[[490,300],[650,180],[920,230],[1080,382]],1,C.pink,5,{dots:true});arrow(x,[[490,300],[650,470],[900,450],[1080,382]],1,C.cyan,5,{dots:true});nodes.forEach((n,i)=>{glow(x,...n,35,C.yellow,.6);ball(x,...n,10,['#fff6bf','#ffdc72','#c28737']);});if(sea)arrow(x,[[1080,423],[1040,650],[490,630],[220,420]],1,C.cyan,9,{dots:true});}
const DURATION=28;window.DURATION=DURATION;

function enter(x,t,at,fn,delay=0){const u=back(seg(t,at+delay,at+delay+.5));if(u<=0)return;x.save();x.globalAlpha*=Math.min(1,u);fn(u);x.restore();}
function label(x,s,a,b,t,at,size=32,color=C.yellow){pill(x,a,b,s,size,{s:back(seg(t,at,at+.45)),bg:color});}
function title(x,s,t,at){enter(x,t,at,u=>text(x,s,640,136+(1-u)*28, s.length>28?58:64,'#fff'));}
function sceneOne(x,t){network(x);const z=lerp(1.65,1,eo(seg(t,0,1.8)));x.save();x.translate(640,360);x.scale(z,z);silk(x,0,0,1.9);x.restore();title(x,'The Silk Roads',t,.1);enter(x,t,.65,u=>text(x,'A world connected by trade',640,610,40,'#ffdd83'));}
function sceneTwo(x,t){const u=eio(seg(t,2,2.8));x.save();x.globalAlpha=1-u;network(x);x.restore();city(x,lerp(1080,355,u),lerp(382,418,u),lerp(.5,1.6,u));enter(x,t,2.6,v=>scroll(x,830,381+(1-v)*70,1.35*v));title(x,'2nd century BCE',t,2.15);label(x,'Chang’an',355,563,t,2.6);enter(x,t,2.9,v=>text(x,'Han missions expand connections',820,567,33,'#fff0c6'));arrow(x,[[640,440],[590,470],[570,470],[530,440]],eo(seg(t,3.2,3.85)),C.cyan,9,{dots:true});}
function sceneThree(x,t){network(x);title(x,'Many routes. Many traders.',t,5.15);label(x,'Mediterranean',202,272,t,5.45,28,'#fff');label(x,'Samarkand',489,227,t,5.65,28,'#fff');label(x,'Chang’an',1080,307,t,5.85,28,'#fff');let u=eo(seg(t,5.3,8.4));camel(x,lerp(750,450,u),435+Math.sin(t*10)*3,.8);camel(x,lerp(930,650,u),467+Math.sin(t*10+1)*3,.7);if(t>7.2){const q=seg(t,7.2,8.15);silk(x,lerp(550,635,q),390-Math.sin(q*Math.PI)*48,.25);}enter(x,t,6.1,u=>text(x,'Goods passed from trader to trader',640,610,37,'#ffdf91'));}
function sceneFour(x,t){title(x,'More than silk',t,9.2);[295,640,991].forEach((a,j)=>enter(x,t,9.4+j*.55,u=>{if(j===0)silk(x,a,370+(1-u)*50,1.25*u);if(j===1){x.save();x.translate(a,377);x.scale(u,u);spice(x,0,0);x.restore();}if(j===2){x.save();x.translate(a,372);x.scale(u,u);glass(x,0,0);x.restore();}}));['Silk','Spices','Glass'].forEach((s,j)=>label(x,s,[295,640,991][j],535,t,9.65+j*.55,35,[C.pink,C.yellow,C.cyan][j]));}
function sceneFive(x,t){title(x,'Ideas traveled, too',t,12.1);enter(x,t,12.25,u=>scroll(x,640,369+(1-u)*150,1.12*u));enter(x,t,12.7,u=>{x.save();x.translate(279,382+(1-u)*100);x.scale(u,u);lotus(x,0,0);x.restore();});enter(x,t,13.2,u=>compass(x,1005,370+(1-u)*100,u));arrow(x,[[370,370],[445,285],[470,285],[535,358]],eo(seg(t,13.0,13.6)),C.cyan,8,{dots:true});arrow(x,[[742,365],[820,285],[846,285],[907,359]],eo(seg(t,13.65,14.25)),C.cyan,8,{dots:true});['Beliefs','Knowledge','Inventions'].forEach((s,j)=>label(x,s,[279,640,1005][j],550,t,13+j*.45));}
function sceneSix(x,t){network(x);title(x,'13th–14th centuries',t,16.2);[270,550,860,1100].forEach((a,j)=>enter(x,t,16.6+j*.35,u=>city(x,a,430+(j%2)*25+(1-u)*40,.55*u)));label(x,'Mongol rule boosts exchange',640,559,t,17.4,37);enter(x,t,18.05,u=>text(x,'Connections strengthened across Eurasia',640,624,31,'#d5d1f3'));for(let i=0;i<5;i++){let u=(t*.25+i/5)%1;const p=bez([[200,342],[550,230],[820,440],[1080,382]],u);glow(x,...p,20,C.yellow,.5);ball(x,...p,5,['#fff8cc','#ffdf68','#b97533']);}}
function sceneSeven(x,t){network(x);title(x,'Trade routes shifted',t,20.15);text(x,'Land routes continued',975,230,29,'#d3c8ed',{a:eo(seg(t,20.4,21.1))});const p=eo(seg(t,20.6,22.6));arrow(x,[[1080,423],[1040,650],[490,630],[220,420]],p,C.cyan,9,{dots:true});const pos=bez([[1080,423],[1040,650],[490,630],[220,420]],.12+.7*eo(seg(t,21,23.8)));enter(x,t,21,u=>ship(x,pos[0],pos[1]-70+Math.sin(t*2)*4,.75*u));label(x,'Sea trade gained importance',640,631,t,22,36,C.cyan);}
function sceneEight(x,t){title(x,'Goods moved. Ideas spread.',t,24.15);arrow(x,[[280,360],[400,580],[880,580],[1000,360]],eo(seg(t,24.3,25.6)),C.yellow,9,{dots:true});enter(x,t,24.35,u=>silk(x,280,350,.7*u));enter(x,t,24.6,u=>scroll(x,475,418,.65*u));enter(x,t,24.85,u=>compass(x,805,418,.7*u));enter(x,t,25.1,u=>city(x,1000,370,.7*u));enter(x,t,25.45,u=>text(x,'The Silk Roads',640,558+(1-u)*22,47,'#fff'));enter(x,t,25.85,u=>text(x,'connected cultures.',640,617+(1-u)*22,51,'#ffdc73'));}
