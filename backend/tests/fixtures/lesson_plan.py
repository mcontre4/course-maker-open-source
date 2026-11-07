from dataclasses import replace

from app.courses.domain.lesson_plan import LessonPlan, ResearchSource, TeachingBeat, WorkedExample


def lesson_plan(brief):
    return LessonPlan(
        brief.lesson_id,
        brief.objectives,
        ("No prior programming",),
        ("Assignment",),
        (
            TeachingBeat(
                "Assignment",
                "Name a value",
                "Use score = 3",
                brief.concepts,
                brief.video_minutes * 60,
                "What is score?",
                "3",
            ),
        ),
        ("Assignment binds a name to a value",),
        (),
        (WorkedExample("Store a score", ("Write score = 3",), "score is 3"),),
        ("Assignment is not equality",),
        ("Defer functions",),
        (ResearchSource("Python tutorial", "https://docs.python.org/3/tutorial/"),),
        feasibility_status="feasible",
    )


def infeasible_lesson_plan(brief):
    plan = lesson_plan(brief)
    return replace(
        plan,
        beats=(replace(plan.beats[0], seconds=(brief.video_minutes + 2) * 60),),
        feasibility_status="infeasible",
        feasibility_explanation="The required reasoning and example need two more minutes.",
        recommended_video_minutes=brief.video_minutes + 2,
        recommended_scope_adjustment="Move one approved objective into a separate lesson.",
        sources=(),
    )
