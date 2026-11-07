import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useApplication } from "./application-context";
import { useLessonMutation } from "./lesson-context";
import { CopyLessonDialog } from "./CopyLessonDialog";
import { Button } from "./primitives/Button";
import { useSignedIn } from "./authentication";
import { accountPath } from "./auth-routes";

export function CopyLessonButton({
  lessonId,
  courseId,
  title,
  image,
  disabled = false,
}: {
  lessonId: string;
  courseId?: string;
  title: string;
  image: string;
  disabled?: boolean;
}) {
  const copy = useApplication().lessons?.copy;
  const navigate = useNavigate();
  const location = useLocation();
  const signedIn = useSignedIn();
  const [open, setOpen] = useState(false);
  const mutation = useLessonMutation<string>(async (copyTitle) => {
    if (!copy) throw new Error("Lesson copying is unavailable.");
    return copy.execute({ id: lessonId, courseId, title: copyTitle });
  });
  if (!copy) return null;
  const close = () => {
    setOpen(false);
    mutation.reset();
  };
  return (
    <div className="workflow-inline-actions">
      <Button
        variant="secondary"
        disabled={disabled}
        aria-haspopup={signedIn ? "dialog" : undefined}
        onClick={() =>
          // Copies belong to an account, so visitors sign in and come straight back.
          signedIn
            ? setOpen(true)
            : navigate(
                accountPath("/login", location.pathname + location.search),
              )
        }
      >
        Copy lesson
      </Button>
      {open && (
        <CopyLessonDialog
          title={title}
          image={image}
          pending={mutation.isPending}
          error={mutation.error}
          onClose={close}
          onSubmit={(copyTitle) =>
            mutation.mutate(copyTitle, {
              onSuccess: (lesson) => {
                close();
                navigate(`/lessons/${lesson.id}?step=review`);
              },
            })
          }
        />
      )}
    </div>
  );
}
