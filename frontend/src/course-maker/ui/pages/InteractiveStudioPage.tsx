import { useParams } from "react-router-dom";
import { useCourse } from "../application-context";
import { QueryStatus } from "../components";
import { InteractiveStudio } from "../interactives/InteractiveStudio";
import {
  courseInteractiveHome,
  standaloneInteractiveHome,
} from "../interactives/interactive-paths";
import { useStandaloneLesson } from "../lesson-context";

export function StandaloneInteractiveStudioPage() {
  const { lessonId = "", interactiveId = "new" } = useParams();
  const query = useStandaloneLesson(lessonId);
  if (!query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  return (
    <InteractiveStudio
      lesson={{
        lessonId,
        title: query.data.content.title,
        topics: query.data.content.topics,
      }}
      home={standaloneInteractiveHome(lessonId)}
      interactiveId={interactiveId}
    />
  );
}

export function CourseInteractiveStudioPage() {
  const { courseId = "", lessonId = "", interactiveId = "new" } = useParams();
  const query = useCourse(courseId);
  if (!query.data)
    return (
      <QueryStatus
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  const lesson = query.data.chapters
    .flatMap((chapter) => chapter.lessons)
    .find((item) => item.id === lessonId);
  if (!lesson)
    return (
      <div className="status-panel">
        <h1>Lesson not found.</h1>
      </div>
    );
  return (
    <InteractiveStudio
      lesson={{ lessonId, title: lesson.title, topics: lesson.topics }}
      home={courseInteractiveHome(courseId, lessonId)}
      interactiveId={interactiveId}
    />
  );
}
