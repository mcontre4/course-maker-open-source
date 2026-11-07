// Adapter-owned player: only this layer has a playback clock or loads local media.
window.ready = (async () => {
  const timeline = await (await fetch("timeline.json")).json();
  const canvas = document.querySelector("canvas"),
    ctx = canvas.getContext("2d");
  const slider = document.querySelector("#scrub"),
    clock = document.querySelector("#clock");
  await Promise.all(
    (window.STYLE?.fonts ?? ["900 64px Nunito", "700 28px Nunito", "600 44px Fredoka"]).map((f) =>
      document.fonts.load(f),
    ),
  );
  window.DURATION = timeline.duration_sec;
  slider.max = window.DURATION;
  let current = 0,
    playing = false,
    sound = true,
    stop = null,
    last = 0;
  const narration = timeline.scenes.map((s) => ({
    ...s,
    media: new Audio(s.audio),
  }));
  const stopAudio = () => {
    if (stop) stop();
    stop = null;
    narration.forEach((s) => s.media.pause());
  };
  const syncAudio = () => {
    stopAudio();
    if (!playing || !sound) return;
    stop = SOUND.live(window.scoreSound, current, { voiceover: true });
    narration.forEach((s) => {
      const local = current - s.start_sec;
      if (local >= 0 && local < s.duration_sec) {
        s.media.currentTime = local;
        s.media.play().catch(() => {});
      }
    });
  };
  window.seek = (t) => {
    current = H.clamp(t, 0, window.DURATION);
    ctx.resetTransform();
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
    ctx.clearRect(0, 0, 1280, 720);
    ctx.save();
    window.STYLE?.beginFrame?.();
    window.explainer(ctx, 1280, 720, current);
    ctx.restore();
    // Apply the selected medium's surface finish after restoring the drawing transform.
    (window.STYLE ?? window.FV).finish(ctx, 1280, 720, current);
    slider.value = current;
    clock.textContent =
      current.toFixed(1) + " / " + window.DURATION.toFixed(1) + " s";
  };
  window.renderSound = async () => {
    const r = await SOUND.renderOffline(
      window.scoreSound,
      window.DURATION,
      48000,
      { voiceover: true },
    );
    const bytes = new Uint8Array(r.inter.buffer);
    let value = "";
    for (let i = 0; i < bytes.length; i += 16384)
      value += String.fromCharCode(...bytes.subarray(i, i + 16384));
    return { data: btoa(value), peak: r.peak };
  };
  document.querySelector("#play").onclick = () => {
    if (!playing && current >= window.DURATION) window.seek(0);
    playing = !playing;
    document.querySelector("#play").textContent = playing ? "Pause" : "Play";
    syncAudio();
  };
  document.querySelector("#sound").onclick = (e) => {
    sound = !sound;
    e.target.textContent = sound ? "Sound on" : "Sound off";
    syncAudio();
  };
  slider.oninput = () => {
    window.seek(Number(slider.value));
    syncAudio();
  };
  function tick(now) {
    if (playing) {
      const previous = current;
      current += (now - last) / 1000;
      if (current >= window.DURATION) {
        if (document.querySelector("#loop").checked) {
          current = 0;
          syncAudio();
        } else {
          current = window.DURATION;
          playing = false;
          document.querySelector("#play").textContent = "Play";
          stopAudio();
        }
      } else if (
        narration.some((s) => previous < s.start_sec && current >= s.start_sec)
      )
        syncAudio();
      window.seek(current);
    }
    last = now;
    requestAnimationFrame(tick);
  }
  window.seek(0);
  window.done = true;
  requestAnimationFrame(tick);
})();
