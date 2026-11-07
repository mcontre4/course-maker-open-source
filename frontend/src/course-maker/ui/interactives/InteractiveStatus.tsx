import {
  interactiveState,
  type LessonInteractive,
} from "../../application/lesson-interactives";

const labels = {
  building: { text: "Building", tone: "working" },
  failed: { text: "Build stopped", tone: "attention" },
  draft: { text: "Not in lesson", tone: undefined },
  live: { text: "In lesson", tone: "ready" },
  live_with_changes: { text: "New version not in lesson", tone: "attention" },
} as const;

export function InteractiveStatus({
  interactive,
}: {
  interactive: LessonInteractive;
}) {
  const { text, tone } = labels[interactiveState(interactive)];
  return (
    <span className="workflow-status" role="status" data-tone={tone}>
      {text}
    </span>
  );
}
