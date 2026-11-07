// Trusted host bridge. Generated animation stays inside an opaque-origin sandbox.
(async () => {
  const send = (type, extra = {}) =>
    parent.postMessage({ channel: "lesson-preview", type, ...extra }, "*");
  window.addEventListener("error", () => send("error"));
  window.addEventListener("unhandledrejection", () => send("error"));
  try {
    await window.ready;
    const play = document.querySelector("#play");
    const scrub = document.querySelector("#scrub");
    const toggle = play.onclick;
    document.querySelector("#loop").checked = false;
    const seek = window.seek;
    let ended = false;
    let active = false;
    let waiting = false;
    let suspended = false;
    window.seek = (time) => {
      seek(time);
      if (active && time >= window.DURATION && !ended) {
        active = false;
        ended = true;
        send("ended");
      }
    };
    play.onclick = () => {
      if (play.textContent === "Pause") {
        active = false;
        toggle();
      } else if (!waiting) {
        suspended = false;
        waiting = true;
        send("play-request", { time: ended ? 0 : Number(scrub.value) });
      }
    };
    window.addEventListener("message", (event) => {
      if (event.source !== parent || event.data?.channel !== "lesson-preview")
        return;
      if (event.data.type === "play-code") {
        if (suspended) return;
        waiting = false;
        ended = false;
        if (Number.isFinite(event.data.time)) {
          window.seek(event.data.time);
          scrub.dispatchEvent(new Event("input"));
        }
        active = true;
        toggle();
      } else if (event.data.type === "pause") {
        suspended = true;
        waiting = false;
        if (active) {
          active = false;
          toggle();
        }
      } else if (event.data.type === "retry") {
        waiting = false;
      }
    });
    const fullscreen = document.createElement("button");
    fullscreen.textContent = "Fullscreen";
    fullscreen.onclick = () =>
      document.documentElement.requestFullscreen().catch(() => {});
    document.querySelector("nav").append(fullscreen);
    const style = document.createElement("style");
    style.textContent = `
      html, body { width:100%; height:100%; overflow:hidden; }
      body { display:block; }
      main { height:100%; display:flex; flex-direction:column; }
      canvas { width:100%; height:calc(100% - 60px); object-fit:contain; min-height:0; }
      nav { height:60px; box-sizing:border-box; gap:8px; width:100%; flex-shrink:0; }
      #scrub { flex:1; min-width:20px; }
      #clock { font:12px sans-serif; white-space:nowrap; }
      nav label { display:none; }
      button { cursor:pointer; padding:8px 10px; white-space:nowrap; }
      @media(max-width:480px) { #clock { display:none; } }
    `;
    document.head.append(style);
    send("ready");
  } catch {
    send("error");
  }
})();
