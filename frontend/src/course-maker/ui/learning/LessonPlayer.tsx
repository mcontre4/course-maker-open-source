import { useContext } from "react";
import { ApplicationContext } from "../application-context";
import { LiveLessonPlayer } from "./LiveLessonPlayer";
import { VideoLessonPlayer } from "./VideoLessonPlayer";
import type { LessonResponse } from "../../application/dto";

export type LessonPlayerProps = {
  lesson: LessonResponse;
  courseTitle: string;
  courseId?: string;
  onWatched?: () => void;
  watched?: boolean;
  pending?: boolean;
};

export function LessonPlayer(props: LessonPlayerProps) {
  const app = useContext(ApplicationContext);
  if (
    props.lesson.animation?.projectKey.endsWith("/javascript") &&
    app?.playback
  ) {
    return <LiveLessonPlayer {...props} playback={app.playback} />;
  }
  return <VideoLessonPlayer {...props} />;
}
