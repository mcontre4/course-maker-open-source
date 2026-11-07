import { useEffect, useState } from "react";

export function LessonGenerationProgress({
  minutes,
  phase = "outline",
}: {
  minutes: number;
  phase?: "outline" | "video";
}) {
  const [index, setIndex] = useState(0);
  const outlineMessages = [
    {
      title: "Finding the clearest way to teach it…",
      subtitle: `Your guide will research the topic and build a focused outline for your ${minutes}-minute lesson.`,
    },
    {
      title: "Making room for the aha moment…",
      subtitle:
        "A clear explanation starts with the essentials and builds one idea at a time.",
    },
    {
      title: "Connecting ideas to everyday examples…",
      subtitle:
        "Familiar examples help new concepts click and make the learning stick.",
    },
    {
      title: "Keeping it focused on your goals…",
      subtitle: `Your ${minutes}-minute lesson is taking shape. A little focus goes a long way.`,
    },
  ];
  const videoMessages = [
    {
      title: "Bringing your lesson to life…",
      subtitle: "Your outline is becoming a script, narration and animation.",
    },
    {
      title: "Giving every idea a moment to land…",
      subtitle:
        "Clear pacing makes space for explanations, examples and those little aha moments.",
    },
    {
      title: "Making the explanation feel natural…",
      subtitle:
        "Words, voice and visuals work together to guide you through the topic.",
    },
    {
      title: "Turning a little curiosity into understanding…",
      subtitle: `Your ${minutes}-minute lesson is on its way. Each completed step is saved as it goes.`,
    },
  ];
  const messages = phase === "outline" ? outlineMessages : videoMessages;
  const messageCount = messages.length;

  useEffect(() => {
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % messageCount);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [messageCount]);

  return (
    <div className="lesson-planning-progress" role="status" aria-atomic="true">
      {messages.map((message, messageIndex) => (
        <div
          key={message.title}
          className={`lesson-planning-message${index === messageIndex ? " is-current" : ""}`}
          aria-hidden={index !== messageIndex}
        >
          <h3>
            <span className="loading-spinner" aria-hidden="true" />
            {message.title}
          </h3>
          <p className="muted">{message.subtitle}</p>
        </div>
      ))}
    </div>
  );
}
