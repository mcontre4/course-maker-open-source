import { ElementPreparationToggle } from "./ElementPreparationToggle";
import { CancelGenerationButton } from "./CancelGenerationButton";
import { useState } from "react";
import { AnimatorModelSelector } from "./AnimatorModelSelector";
import type { AnimatorModelChoice } from "../application/animator-model";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { GenerationMode } from "../application/generation-mode";
import type { CourseResponse, LessonResponse } from "../application/dto";
import { useApplication } from "./application-context";
import { useGenerationMode } from "./generation-mode";
import { QualitySettings } from "./GenerationModeSelector";
import { Button } from "./primitives/Button";
import { ErrorNotice } from "./components";

export function CourseMedia({
  course,
  lesson,
  disabled,
  onBusyChange,
  mode: selectedMode,
  onModeChange,
}: {
  course: CourseResponse;
  lesson: LessonResponse;
  disabled?: boolean;
  onBusyChange?(busy: boolean): void;
  mode?: GenerationMode;
  onModeChange?(mode: GenerationMode): void;
}) {
  const [animatorModel, setAnimatorModel] = useState<AnimatorModelChoice>("");
  const [prepareElements, setPrepareElements] = useState(
    lesson.animation?.prepareElements ?? false,
  );
  const app = useApplication();
  const cache = useQueryClient();
  const [storedMode, setStoredMode] = useGenerationMode(
    "course-lesson:" + course.id + ":" + lesson.id,
    "course:" + course.id,
  );
  const mode = selectedMode ?? storedMode;
  const setMode = onModeChange ?? setStoredMode;
  const generate = useMutation({
    mutationFn: async () => {
      if (!app.generateMedia || !app.generateLesson)
        throw new Error("Connect to the server to generate a video.");
      onBusyChange?.(true);
      try {
        return await app.generateMedia.execute({
          courseId: course.id,
          lessonId: lesson.id,
          stage: "video",
          generationMode: mode,
          ...(animatorModel ? { animatorModel } : {}),
          ...(prepareElements ? { prepareElements } : {}),
          animationBackend: "direct",
        });
      } finally {
        onBusyChange?.(false);
      }
    },
    onSettled: () => {
      void cache.invalidateQueries({ queryKey: ["courses", course.id] });
    },
  });
  const pending =
    generate.isPending ||
    !!course.activeOperation?.includes("video") ||
    /storyboard|speech|animation/.test(course.activeOperation ?? "");
  if (!app.generateMedia || !lesson.plan) return null;
  return (
    <section className="style-panel" aria-label="Lesson media generation">
      <QualitySettings
        value={mode}
        onChange={setMode}
        disabled={pending || disabled}
      >
        <AnimatorModelSelector
          value={animatorModel}
          onChange={setAnimatorModel}
          mode={mode}
          disabled={pending || disabled}
        />
        <ElementPreparationToggle
          checked={prepareElements}
          onChange={setPrepareElements}
          disabled={pending || disabled}
        />
      </QualitySettings>
      {lesson.animation && lesson.animation.reviewStatus !== "pending" ? (
        <p>
          Script, narration and animation are saved. Watch your lesson in the
          player above.
        </p>
      ) : (
        <>
          <Button
            disabled={pending || disabled}
            onClick={() => generate.mutate()}
          >
            {pending ? "Generating…" : "Generate lesson video →"}
          </Button>
          {pending && (
            <p role="status">
              In Progress — creating your lesson video… Each completed stage is
              saved.
            </p>
          )}
        </>
      )}
      <CancelGenerationButton
        kind="course"
        id={course.id}
        pending={pending}
        operation={course.activeOperation}
        label="video generation"
      />
      <ErrorNotice error={generate.error} />
    </section>
  );
}
