from app.courses.domain.storyboard import SpeechCue, Storyboard, StoryboardScene


def storyboard(plan, minutes=10):
    # Deliberately repetitive test speech exercises structural validation, not pedagogy.
    narration = "Look at the name score. " + "A name refers to a value. " * (minutes * 10)
    scenes = tuple(
        StoryboardScene(
            f"s{i + 1:02}",
            1,
            "Explain assignment",
            narration,
            "Show score on the left, an arrow, and the value 3 on the right.",
            (
                SpeechCue(
                    "name",
                    "Look at the name score",
                    "Reveal the name score",
                    "The name score",
                    "The name refers to the displayed value",
                    "Hold the name and value together while they are explained",
                ),
            ),
            minutes * 60 // 2,
            "Hold the value, then reveal the next explanation.",
            ("score", "3"),
            plan.equations,
            ("Use a labeled arrow and high contrast; never encode meaning with color alone.",),
        )
        for i in range(2)
    )
    return Storyboard(plan.lesson_id, plan.objectives, minutes, scenes)
