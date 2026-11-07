from dataclasses import asdict, replace

import pytest
from fakes.syllabus import (
    rename_course,
)

from app.courses.application.generate_syllabus import (
    GenerateSyllabusRequest,
    GetSyllabusSession,
    SyllabusSessionRequest,
)
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.identifiers import CourseId
from app.courses.ports.syllabus_errors import SyllabusUnavailable


def test_generate_and_resume_same_conversation(generation, draft, dependencies):
    service, agent, conversations, uow = generation
    first = service.execute(GenerateSyllabusRequest(draft.id, "  Teach Python  ", 0))
    assert agent.requests[0].message == "  Teach Python  "
    persisted = dependencies[0].require_by_id(CourseId(draft.id))
    assert persisted.chapters[0].lessons[0].title == "Variables"
    assert first.session.revision == 1
    assert first.session.session_id == draft.id
    plan = asdict(first.session.curriculum)
    lesson_ids = [ls.id for ls in persisted.chapters[0].lessons]
    assert plan["chapters"][0]["lessons"][1]["prerequisites"] == (str(lesson_ids[0]),)
    agent.plan = replace(
        agent.plan,
        chapters=(
            replace(
                agent.plan.chapters[0],
                chapter_id=str(persisted.chapters[0].id),
                lessons=tuple(
                    replace(
                        ls,
                        lesson_id=str(lesson_ids[i]),
                        chapter_id=str(persisted.chapters[0].id),
                        prerequisites=() if i == 0 else (str(lesson_ids[0]),),
                    )
                    for i, ls in enumerate(agent.plan.chapters[0].lessons)
                ),
            ),
        ),
        required_topic_coverage=tuple(
            replace(item, lesson_ids=(str(lesson_ids[0]),))
            for item in agent.plan.required_topic_coverage
        ),
    )
    second = service.execute(GenerateSyllabusRequest(draft.id, "Add examples", 1))
    assert second.session.revision == 2
    assert second.course.chapters[0].id == first.course.chapters[0].id
    assert second.course.chapters[0].lessons[0].id == first.course.chapters[0].lessons[0].id
    assert agent.requests[1].history_json == "[] next turn"
    assert agent.requests[1].curriculum.guide.teaching_level == "beginner"
    assert agent.requests[1].course.chapters[0].lessons[0].id == str(lesson_ids[0])
    saved = conversations.get_by_course_id(CourseId(draft.id))
    assert [turn.user for turn in saved.turns] == ["  Teach Python  ", "Add examples"]
    assert uow.commits == 2


def test_clarification_keeps_existing_syllabus(generation, draft, dependencies):
    service, agent, conversations, _ = generation
    agent.plan = None
    result = service.execute(GenerateSyllabusRequest(draft.id, "Help me choose a subject"))
    assert result.course == draft
    assert not dependencies[0].require_by_id(CourseId(draft.id)).chapters
    assert conversations.get_by_course_id(CourseId(draft.id)).curriculum is None
    assert result.session.turns[0].user == "Help me choose a subject"


def test_read_session_without_generating(generation, draft, dependencies):
    service, _, conversations, uow = generation
    reader = GetSyllabusSession(dependencies[0], conversations, uow)
    empty = reader.execute(SyllabusSessionRequest(draft.id))
    assert empty.revision == 0 and empty.turns == ()
    service.execute(GenerateSyllabusRequest(draft.id, "Teach Python"))
    assert reader.execute(SyllabusSessionRequest(draft.id)).revision == 1


def test_stale_revision_does_not_call_model(generation, draft):
    service, agent, conversations, _ = generation
    with pytest.raises(CourseConflict):
        service.execute(GenerateSyllabusRequest(draft.id, "Change it", 1))
    assert agent.requests == [] and conversations.items == {}


@pytest.mark.parametrize("message", ["", " ", "x" * 20001])
def test_invalid_message_does_not_call_model(generation, draft, message):
    service, agent, _, _ = generation
    with pytest.raises(CourseError):
        service.execute(GenerateSyllabusRequest(draft.id, message))
    assert not agent.requests


def test_provider_failure_keeps_course_and_history(generation, draft, dependencies):
    service, agent, conversations, uow = generation
    agent.error = SyllabusUnavailable("Offline")
    with pytest.raises(SyllabusUnavailable):
        service.execute(GenerateSyllabusRequest(draft.id, "Teach Python"))
    assert not conversations.items and uow.commits == 0
    assert not dependencies[0].require_by_id(CourseId(draft.id)).chapters


def test_failed_commit_rolls_back_course_and_history(generation, draft, dependencies):
    service, _, conversations, uow = generation
    uow.fail_commit = True
    with pytest.raises(RuntimeError, match="Commit failed"):
        service.execute(GenerateSyllabusRequest(draft.id, "Teach Python"))
    assert not conversations.items
    assert not dependencies[0].require_by_id(CourseId(draft.id)).chapters


def test_concurrent_course_edit_is_not_overwritten(generation, draft, dependencies):
    service, agent, conversations, _ = generation
    agent.during_run = lambda: rename_course(dependencies[0], CourseId(draft.id))
    with pytest.raises(CourseConflict):
        service.execute(GenerateSyllabusRequest(draft.id, "Teach Python"))
    assert dependencies[0].require_by_id(CourseId(draft.id)).title == "Concurrent edit"
    assert not conversations.items


def test_approved_course_cannot_be_generated(generation, ready):
    service, agent, _, _ = generation
    with pytest.raises(CourseConflict):
        service.execute(GenerateSyllabusRequest(ready.id, "Change it"))
    assert not agent.requests


def test_missing_course_cannot_create_conversation(generation):
    service, _, conversations, _ = generation
    with pytest.raises(CourseNotFound):
        service.execute(
            GenerateSyllabusRequest("course_00000000-0000-0000-0000-000000999999", "Hi")
        )
    assert not conversations.items


def test_syllabus_history_is_scoped_to_its_course_owner(generation, draft, dependencies):
    from app.courses.domain.errors import CourseNotFound

    _, _, conversations, uow = generation
    courses = dependencies[0]
    original = courses.require_by_id(CourseId(draft.id))
    owner = "user_00000000-0000-0000-0000-000000000001"
    other = "user_00000000-0000-0000-0000-000000000002"
    courses.save(replace(original, owner_id=owner))
    reader = GetSyllabusSession(courses, conversations, uow)
    with pytest.raises(CourseNotFound):
        reader.execute(SyllabusSessionRequest(draft.id, other))
    assert reader.execute(SyllabusSessionRequest(draft.id, owner)).session_id == draft.id
