import hashlib
import json
from dataclasses import asdict, replace

import pytest
from fixtures.animation import animation_inputs

from app.courses.adapters.http.schema import LessonView
from app.courses.adapters.persistence.codec import _lesson, encode_lesson
from app.courses.application.dto import lesson_response
from app.courses.domain.interactive import InteractiveSpec, LessonInteractive

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("legacy", [False, True])
def test_saved_interactive_survives_storage_and_is_exposed_as_transport_dto(legacy):
    _, course, _, _ = animation_inputs()
    lesson = course.chapters[0].lessons[0]
    if legacy:
        lesson = replace(lesson, plan=replace(lesson.plan, feasibility_status=None))
    plan_payload = asdict(lesson.plan)
    assessment_fields = (
        "feasibility_status", "feasibility_explanation",
        "recommended_video_minutes", "recommended_scope_adjustment",
    )
    if legacy:
        for field in assessment_fields:
            plan_payload.pop(field)
    spec = InteractiveSpec(
        "custom",
        "Explore the idea",
        lesson.plan.objectives[0],
        "Try a value",
        ("Input",),
        "Compare the result",
        ("What changed?",),
        ("Input changes result",),
    )
    activity = LessonInteractive(
        hashlib.sha256(
            json.dumps(plan_payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        "Test the lesson's central idea",
        spec,
        "<!doctype html><html><body><button>Try it</button></body></html>",
    )
    lesson = replace(lesson, interactive=activity)
    payload = encode_lesson(lesson)
    if legacy:
        for field in assessment_fields:
            payload["plan"].pop(field)
    restored = _lesson(payload)
    result = LessonView.model_validate(lesson_response(restored)).model_dump(by_alias=True)
    assert result["interactive"]["html"] == activity.document
    assert result["interactive"]["spec"]["objective"] == lesson.plan.objectives[0]
    assert result["interactive"]["planHash"] == activity.plan_hash
    assert restored.interactive == activity
    assert (
        lesson.revise_outline(lesson.title, lesson.topics, lesson.minutes).interactive == activity
    )
    assert (
        lesson.revise_outline(
            lesson.title, lesson.topics, lesson.minutes, invalidate_content=True
        ).interactive
        is None
    )
