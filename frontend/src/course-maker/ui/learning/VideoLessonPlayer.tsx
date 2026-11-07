import { useRef, useState } from "react";
import type { LessonPlayerProps } from "./LessonPlayer";

export function VideoLessonPlayer({
  lesson,
  courseTitle,
  onWatched,
  watched,
  pending,
  autoPlay = false,
  resumeAt = 0,
  beforePlay,
}: LessonPlayerProps & {
  autoPlay?: boolean;
  resumeAt?: number;
  beforePlay?: (time: number) => Promise<boolean>;
}) {
  const permitted = useRef(autoPlay);
  const checking = useRef(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  if (!lesson.videoUrl) {
    return (
      <section
        className="video-unavailable"
        aria-label="Video not ready"
        role="status"
      >
        <p className="eyebrow">{courseTitle}</p>
        <div className="video-placeholder-message">
          <span className="video-play-symbol" aria-hidden="true">
            <img src="/course-maker/lesson-imgFrame1.svg" alt="" />
          </span>
          <h2>Your video lesson belongs here.</h2>
          <p>{lesson.title}</p>
          <span className="video-status">VIDEO NOT READY YET</span>
        </div>
        <p className="video-status-note">
          This lesson will be a video with playback controls and fullscreen.
          Your teaching plan is created first; video production follows in a
          later stage.
        </p>
      </section>
    );
  }

  return (
    <section
      className="video-player"
      aria-label={lesson.title + " video player"}
    >
      <video
        key={attempt}
        className="lesson-video"
        src={lesson.videoUrl}
        aria-label={lesson.title + " video"}
        controls
        playsInline
        preload="metadata"
        onPlay={(event) => {
          if (!beforePlay) return;
          const video = event.currentTarget;
          if (permitted.current) {
            permitted.current = false;
            return;
          }
          video.pause();
          if (checking.current) return;
          checking.current = true;
          void beforePlay(video.currentTime)
            .then((continueVideo) => {
              if (continueVideo && video.isConnected) {
                permitted.current = true;
                void video.play().catch(() => {
                  permitted.current = false;
                });
              }
            })
            .catch(() => setFailed(true))
            .finally(() => {
              checking.current = false;
            });
        }}
        onEnded={() => {
          if (!watched && !pending) onWatched?.();
        }}
        onLoadStart={() => setLoading(true)}
        onLoadedMetadata={(event) => {
          setLoading(false);
          if (resumeAt) event.currentTarget.currentTime = resumeAt;
          if (autoPlay) void event.currentTarget.play().catch(() => {});
        }}
        onError={() => {
          setLoading(false);
          setFailed(true);
        }}
      >
        Your browser does not support video playback.
      </video>
      {lesson.animation?.reviewStatus === "skipped" && (
        <p className="video-playback-status">
          Ready for your review · AI review was turned off.
        </p>
      )}
      {lesson.animation?.reviewStatus === "repaired" && (
        <p className="video-playback-status">
          Visual review fixes applied · Final video technically verified.
        </p>
      )}
      {loading && !failed && (
        <p role="status" className="video-playback-status">
          Preparing your video for playback… The first playback can take a few
          minutes.
        </p>
      )}
      {failed ? (
        <div className="video-error" role="alert">
          <p>
            This video couldn’t be loaded. Check your connection and try again.
          </p>
          <button
            className="btn btn-secondary"
            onClick={() => {
              setFailed(false);
              setAttempt((value) => value + 1);
            }}
          >
            Retry video
          </button>
        </div>
      ) : onWatched ? (
        <p className="video-playback-status" aria-live="polite">
          {pending
            ? "Saving video progress…"
            : watched
              ? "✓ Video watched"
              : "Watch the video to unlock the lesson quiz."}
        </p>
      ) : null}
    </section>
  );
}
