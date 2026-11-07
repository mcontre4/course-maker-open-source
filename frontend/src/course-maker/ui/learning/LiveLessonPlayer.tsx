import { useCallback, useEffect, useRef, useState } from "react";
import type {
  LessonPlaybackResponse,
  SelectLessonPlayback,
} from "../../application/lesson-playback";
import type { LessonPlayerProps } from "./LessonPlayer";
import { VideoLessonPlayer } from "./VideoLessonPlayer";
import "./live-lesson-player.css";

type Props = LessonPlayerProps & {
  playback: Pick<SelectLessonPlayback, "execute">;
};

export function LiveLessonPlayer(props: Props) {
  return (
    <LivePlayback
      key={`${props.courseId ?? ""}:${props.lesson.id}`}
      {...props}
    />
  );
}

function LivePlayback({ playback, ...props }: Props) {
  const { lesson, courseId, watched, pending, onWatched } = props;
  const [selection, setSelection] = useState<LessonPlaybackResponse | null>(
    null,
  );
  const [completed, setCompleted] = useState(false);
  const completionReported = useRef(false);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const selected = useRef<LessonPlaybackResponse | null>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const autoplay = useRef(false);
  const resumeAt = useRef(0);
  const checking = useRef(false);
  const mounted = useRef(true);
  const send = useCallback((type: string) => {
    frame.current?.contentWindow?.postMessage(
      {
        channel: "lesson-preview",
        type,
        time: resumeAt.current,
      },
      "*",
    );
  }, []);

  const select = useCallback(
    async (play: boolean, time = 0) => {
      if (checking.current) return;
      checking.current = true;
      setFailed(false);
      try {
        const next = await playback.execute({
          lessonId: lesson.id,
          courseId,
          ...(lesson.animation?.outputHash
            ? { sourceHash: lesson.animation.outputHash }
            : {}),
        });
        if (!mounted.current) return;
        autoplay.current = play;
        resumeAt.current = time;
        if (
          selected.current?.sourceHash === next.sourceHash &&
          !next.videoReady
        ) {
          if (play) send("play-code");
        } else {
          selected.current = next;
          setLoading(!next.videoReady);
          setSelection(next);
        }
      } catch {
        if (mounted.current) {
          setFailed(true);
          setLoading(false);
          send("retry");
        }
      } finally {
        checking.current = false;
      }
    },
    [playback, lesson.id, lesson.animation?.outputHash, courseId, send],
  );

  useEffect(() => {
    mounted.current = true;
    // Polling may publish repaired source while this preview is playing.
    // Select that source (or the finished video) on the next play/resume.
    if (!selected.current) void select(false);
    return () => {
      mounted.current = false;
    };
  }, [select]);

  useEffect(() => {
    if (!selection || selection.videoReady || !loading) return;
    const timeout = window.setTimeout(() => {
      setFailed(true);
      setLoading(false);
    }, 20000);
    return () => window.clearTimeout(timeout);
  }, [selection, loading]);

  useEffect(() => {
    const message = (event: MessageEvent) => {
      if (
        event.source !== frame.current?.contentWindow ||
        event.data?.channel !== "lesson-preview"
      )
        return;
      switch (event.data.type) {
        case "ready":
          setLoading(false);
          if (autoplay.current) send("play-code");
          break;
        case "play-request":
          void select(
            true,
            Number.isFinite(event.data.time) ? event.data.time : 0,
          );
          break;
        case "ended":
          setCompleted(true);
          break;
        case "error":
          setFailed(true);
          setLoading(false);
          break;
      }
    };
    window.addEventListener("message", message);
    return () => window.removeEventListener("message", message);
  }, [select, send, watched, pending, onWatched]);

  useEffect(() => {
    if (
      completed &&
      !watched &&
      !pending &&
      onWatched &&
      !completionReported.current
    ) {
      completionReported.current = true;
      onWatched();
    }
  }, [completed, watched, pending, onWatched]);

  const checkVideo = async (time: number): Promise<boolean> => {
    const next = await playback.execute({
      lessonId: lesson.id,
      courseId,
      ...(lesson.animation?.outputHash
        ? { sourceHash: lesson.animation.outputHash }
        : {}),
    });
    if (!mounted.current) return false;
    if (next.videoReady && next.sourceHash === selected.current?.sourceHash)
      return true;
    autoplay.current = true;
    resumeAt.current =
      next.sourceHash === selected.current?.sourceHash ? time : 0;
    selected.current = next;
    setSelection(next);
    setLoading(!next.videoReady);
    return false;
  };

  if (selection?.videoReady) {
    return (
      <VideoLessonPlayer
        key={selection.sourceHash}
        beforePlay={checkVideo}
        {...props}
        lesson={{ ...lesson, videoUrl: selection.videoUrl }}
        autoPlay={autoplay.current}
        resumeAt={resumeAt.current}
      />
    );
  }
  return (
    <section
      className="video-player"
      aria-label={`${lesson.title} video player`}
    >
      {selection && (
        <iframe
          key={selection.sourceHash}
          ref={frame}
          title={`${lesson.title} live preview`}
          className="lesson-code-player"
          src={selection.previewUrl}
          sandbox="allow-scripts"
          allow="autoplay; fullscreen"
          allowFullScreen
          referrerPolicy="no-referrer"
        />
      )}
      <p className="video-playback-status" role="status">
        {failed
          ? "Playback unavailable."
          : loading
            ? "Preparing playback…"
            : lesson.animation?.reviewStatus === "pending"
              ? "Preview ready to play. Video processing is still in progress."
              : "Your lesson is ready to play."}
      </p>
      {lesson.animation?.reviewStatus === "pending" && (
        <p className="video-playback-status">
          This is an animation preview. The finished video will appear after
          processing.
        </p>
      )}
      {failed && (
        <div className="video-error" role="alert">
          <p>
            Playback couldn’t be loaded. Check your connection and try again.
          </p>
          <button
            className="btn btn-secondary"
            onClick={() => {
              selected.current = null;
              setSelection(null);
              setLoading(true);
              void select(false);
            }}
          >
            Retry playback
          </button>
        </div>
      )}
      {onWatched && (
        <p className="video-playback-status" aria-live="polite">
          {pending
            ? "Saving video progress…"
            : watched
              ? "✓ Video watched"
              : completed
                ? "Lesson watched."
                : "Watch the video to unlock the lesson quiz."}
        </p>
      )}
    </section>
  );
}
