import { useEffect, useRef, useState, type ReactNode } from "react";
import { InteractiveFrame } from "./InteractiveFrame";

/**
 * The surface every interactive runs on, for creators and learners alike: a
 * running page with a restart and a full-screen control.
 */
export function InteractiveStage({
  html,
  title,
  width = "full",
  tools,
  notice,
}: {
  html: string;
  title: string;
  width?: "full" | "phone";
  tools?: ReactNode;
  notice?: ReactNode;
}) {
  const surface = useRef<HTMLDivElement>(null);
  const [run, setRun] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [fullscreenError, setFullscreenError] = useState(false);
  useEffect(() => {
    const changed = () =>
      setExpanded(document.fullscreenElement === surface.current);
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, []);
  return (
    <div className="interactive-stage" ref={surface} data-expanded={expanded}>
      <div className="interactive-stage-bar">
        {tools}
        {notice}
        <div className="interactive-stage-actions">
          <button type="button" onClick={() => setRun((value) => value + 1)}>
            Start over
          </button>
          {document.fullscreenEnabled && (
            <button
              type="button"
              onClick={async () => {
                setFullscreenError(false);
                try {
                  if (expanded) await document.exitFullscreen();
                  else await surface.current?.requestFullscreen();
                } catch {
                  setFullscreenError(true);
                }
              }}
            >
              {expanded ? "Exit full screen" : "Full screen"}
            </button>
          )}
        </div>
      </div>
      {fullscreenError && (
        <p className="interactive-stage-note" role="alert">
          Full screen isn’t available here. You can still use the interactive on
          this page.
        </p>
      )}
      <div className="interactive-stage-well" data-width={width}>
        <InteractiveFrame
          key={run}
          html={html}
          title={title}
          className="interactive-stage-frame"
        />
      </div>
    </div>
  );
}
