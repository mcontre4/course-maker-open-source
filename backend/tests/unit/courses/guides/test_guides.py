import json
from dataclasses import replace

import pytest
from fixtures.lesson_plan import lesson_plan

from app.courses.application.guide_chats import (
    ChangeGuideMemory,
    CreateGuideThread,
    GetGuideThread,
    ListGuideMemories,
    ListGuideThreads,
    ListOutlineVersions,
)
from app.courses.application.guide_dto import (
    ChangeGuideMemoryRequest,
    CreateGuideThreadRequest,
    GuideScopeRequest,
    GuideThreadRequest,
    OutlineVersionsRequest,
    SendGuideMessageRequest,
)
from app.courses.application.send_guide_message import SendGuideMessage
from app.courses.application.standalone import CreateStandaloneLesson
from app.courses.application.standalone_dto import CreateStandaloneLessonRequest
from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.guide import OutlineVersion
from app.courses.domain.identifiers import LessonId
from app.courses.ports.guide import GuideToolRequest
from app.courses.ports.syllabus_agent import ConversationTurn, SyllabusConversation

OWNER = "user_00000000-0000-0000-0000-000000000001"
OTHER_OWNER = "user_00000000-0000-0000-0000-000000000002"


def test_discussion_preserves_outline_and_reloads_full_conversation(guide_dependencies, guide_chat):
    d = guide_dependencies
    before = d.lessons.require_by_id(LessonId(guide_chat.resource_id))
    use_case = SendGuideMessage(d)
    first = use_case.execute(
        SendGuideMessageRequest(OWNER, guide_chat.id, "Discuss audience", "one", 0)
    )
    second = use_case.execute(
        SendGuideMessageRequest(OWNER, guide_chat.id, "What did I ask?", "two", 1)
    )
    assert second.revision == 2
    assert d.agent.requests[1].history_json == " next"
    assert d.lessons.require_by_id(before.content.id) == before
    reopened = GetGuideThread(d).execute(GuideThreadRequest(OWNER, guide_chat.id))
    assert reopened.turns == second.turns
    assert first.turns[0].user == "Discuss audience"


def test_retries_do_not_duplicate_messages_or_delegate_twice(guide_dependencies, guide_chat):
    d = guide_dependencies
    d.agent.actions = [GuideToolRequest("revise_outline", text="Generate an outline")]
    request = SendGuideMessageRequest(OWNER, guide_chat.id, "Create it", "same-request", 0)
    first = SendGuideMessage(d).execute(request)
    retried = SendGuideMessage(d).execute(request)
    assert retried == first
    assert len(d.lesson_agent.calls) == 1
    assert len(d.agent.requests) == 1
    with pytest.raises(CourseConflict):
        SendGuideMessage(d).execute(replace(request, message="Different message"))


def test_user_memory_crosses_lessons_but_lesson_memory_and_history_do_not(
    guide_dependencies, guide_chat
):
    d = guide_dependencies
    d.agent.actions = [
        GuideToolRequest("remember", key="language", text="Spanish", scope="user"),
        GuideToolRequest("remember", key="audience", text="Chemistry beginners"),
    ]
    SendGuideMessage(d).execute(
        SendGuideMessageRequest(OWNER, guide_chat.id, "Remember these", "one", 0)
    )
    second_chat = CreateGuideThread(d).execute(
        CreateGuideThreadRequest(OWNER, guide_chat.resource_id, "storyboard", "Script ideas")
    )
    d.agent.actions = []
    SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, second_chat.id, "Hello", "two", 0))
    context = json.loads(d.agent.requests[-1].context_json)
    assert {m["key"] for m in context["memories"]} == {"language", "audience"}
    assert context["previous_messages"] == []
    other_lesson = CreateStandaloneLesson(d.lessons, d.uow, d.ids).execute(
        CreateStandaloneLessonRequest(OWNER, "Physics", "Explain force", 3)
    )
    memories = ListGuideMemories(d).execute(GuideScopeRequest(OWNER, other_lesson.id))
    assert [m.key for m in memories.items] == ["language"]


def test_ownership_is_checked_before_model_calls(guide_dependencies, guide_chat):
    d = guide_dependencies
    with pytest.raises(CourseNotFound):
        SendGuideMessage(d).execute(
            SendGuideMessageRequest(OTHER_OWNER, guide_chat.id, "Hello", "one", 0)
        )
    with pytest.raises(CourseNotFound):
        ListGuideMemories(d).execute(GuideScopeRequest(OTHER_OWNER, guide_chat.resource_id))
    assert not d.agent.requests


def test_failed_model_does_not_save_staged_outline_or_memory(guide_dependencies, guide_chat):
    d = guide_dependencies
    before = d.lessons.require_by_id(LessonId(guide_chat.resource_id))
    d.agent.actions = [
        GuideToolRequest("revise_outline", text="Generate an outline"),
        GuideToolRequest("remember", key="audience", text="Beginners"),
    ]
    d.agent.error = RuntimeError("Provider failed after tools")
    with pytest.raises(RuntimeError):
        SendGuideMessage(d).execute(
            SendGuideMessageRequest(OWNER, guide_chat.id, "Revise", "one", 0)
        )
    assert d.lessons.require_by_id(before.content.id) == before
    assert not d.repository.memories
    assert not GetGuideThread(d).execute(GuideThreadRequest(OWNER, guide_chat.id)).turns


def test_failed_commit_rolls_back_chat_outline_and_memory(guide_dependencies, guide_chat):
    d = guide_dependencies
    before = d.lessons.require_by_id(LessonId(guide_chat.resource_id))
    d.agent.actions = [
        GuideToolRequest("revise_outline", text="Generate an outline"),
        GuideToolRequest("remember", key="audience", text="Beginners"),
    ]
    d.uow.fail_commit = True
    with pytest.raises(RuntimeError):
        SendGuideMessage(d).execute(
            SendGuideMessageRequest(OWNER, guide_chat.id, "Revise", "one", 0)
        )
    assert d.lessons.require_by_id(before.content.id) == before
    assert not d.repository.memories
    assert not GetGuideThread(d).execute(GuideThreadRequest(OWNER, guide_chat.id)).turns


def test_concurrent_outline_change_rejects_stale_guide_result(guide_dependencies, guide_chat):
    d = guide_dependencies
    before = d.lessons.require_by_id(LessonId(guide_chat.resource_id))
    d.agent.actions = [GuideToolRequest("revise_outline", text="Generate an outline")]
    d.agent.during_run = lambda: d.lessons.save(replace(before, revision=before.revision + 1))
    with pytest.raises(CourseConflict):
        SendGuideMessage(d).execute(
            SendGuideMessageRequest(OWNER, guide_chat.id, "Revise", "one", 0)
        )
    assert not d.repository.turns


def test_restore_uses_saved_outline_and_resets_approval(guide_dependencies, guide_chat):
    d = guide_dependencies
    lesson = d.lessons.require_by_id(LessonId(guide_chat.resource_id))
    plan = lesson_plan(lesson.brief())
    lesson = lesson.apply_guide_plan(plan).approve()
    d.lessons.save(lesson)
    d.codec.plans["saved-plan"] = plan
    d.repository.versions[guide_chat.resource_id, 1] = OutlineVersion(
        guide_chat.resource_id, 1, "saved-plan", "First outline"
    )
    d.agent.actions = [GuideToolRequest("restore_outline_version", revision=1)]
    SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, guide_chat.id, "Restore", "one", 0))
    restored = d.lessons.require_by_id(lesson.content.id)
    assert restored.content.plan == plan
    assert not restored.approved
    assert restored.revision == lesson.revision + 1
    assert not d.lesson_agent.calls


def test_memory_can_be_corrected_and_forgotten(guide_dependencies, guide_chat):
    d = guide_dependencies
    d.agent.actions = [GuideToolRequest("remember", key="audience", text="Beginners")]
    SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, guide_chat.id, "Remember", "one", 0))
    memory = ListGuideMemories(d).execute(GuideScopeRequest(OWNER, guide_chat.resource_id)).items[0]
    corrected = (
        ChangeGuideMemory(d)
        .execute(
            ChangeGuideMemoryRequest(
                OWNER, guide_chat.resource_id, memory.id, memory.revision, "Advanced learners"
            )
        )
        .items[0]
    )
    assert corrected.content == "Advanced learners"
    with pytest.raises(CourseConflict):
        ChangeGuideMemory(d).execute(
            ChangeGuideMemoryRequest(
                OWNER, guide_chat.resource_id, memory.id, memory.revision, "Stale edit"
            )
        )
    remaining = ChangeGuideMemory(d).execute(
        ChangeGuideMemoryRequest(
            OWNER, guide_chat.resource_id, memory.id, corrected.revision, delete=True
        )
    )
    assert not remaining.items
    assert GetGuideThread(d).execute(GuideThreadRequest(OWNER, guide_chat.id)).turns


def test_conversations_continue_beyond_fifty_turns(guide_dependencies, guide_chat):
    d = guide_dependencies
    for index in range(55):
        SendGuideMessage(d).execute(
            SendGuideMessageRequest(
                OWNER, guide_chat.id, f"Discuss idea {index}", f"request-{index}", index
            )
        )
    chat = GetGuideThread(d).execute(GuideThreadRequest(OWNER, guide_chat.id))
    assert chat.revision == len(chat.turns) == 55


def test_legacy_course_chat_preserves_native_history_and_pages_transcript(
    guide_dependencies, guide_course
):
    d = guide_dependencies
    original = SyllabusConversation(
        str(guide_course.id),
        revision=1,
        history_json="native-history-including-early-decisions",
        turns=tuple(
            ConversationTurn(f"Question {index}", f"Answer {index}") for index in range(125)
        ),
    )
    d.syllabuses.save(original, expected_revision=0)
    request = CreateGuideThreadRequest(OWNER, str(guide_course.id), "syllabus", "Migrated")
    chat = CreateGuideThread(d).execute(request)
    assert chat.has_more and len(chat.turns) == 100
    assert chat.turns[0].user == "Question 25"
    stored = d.repository.require_by_id(chat.id)
    assert stored.history_json == original.history_json
    older = GetGuideThread(d).execute(GuideThreadRequest(OWNER, chat.id, before=26))
    assert older.turns[0].user == "Question 0"
    assert not older.has_more
    fresh = CreateGuideThread(d).execute(replace(request, title="Independent chat"))
    assert fresh.revision == 0 and not fresh.turns
    assert not d.repository.require_by_id(fresh.id).history_json
    listed = ListGuideThreads(d).execute(GuideScopeRequest(OWNER, str(guide_course.id), "syllabus"))
    assert [item.id for item in listed.items] == [chat.id, fresh.id]


def test_course_guide_delegates_restores_and_reads_version_history(
    guide_dependencies, guide_course
):
    d = guide_dependencies
    chat = CreateGuideThread(d).execute(
        CreateGuideThreadRequest(OWNER, str(guide_course.id), "syllabus", "Course ideas")
    )
    d.agent.actions = [GuideToolRequest("revise_outline", text="Revise syllabus")]
    chat = SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, chat.id, "Revise", "one", 0))
    state = d.syllabuses.get_by_course_id(guide_course.id)
    assert state.curriculum is not None
    version = (
        ListOutlineVersions(d).execute(OutlineVersionsRequest(OWNER, str(guide_course.id))).items[0]
    )
    d.codec.curriculums[version.outline_json] = state.curriculum
    d.agent.actions = [
        GuideToolRequest("list_outline_versions"),
        GuideToolRequest("get_outline_version", revision=version.revision),
        GuideToolRequest("compare_outline_versions", version.revision, version.revision),
        GuideToolRequest("search_lesson_history", text="Revise"),
        GuideToolRequest("restore_outline_version", revision=version.revision),
    ]
    chat = SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, chat.id, "Restore", "two", 1))
    assert d.syllabuses.get_by_course_id(guide_course.id).revision == 2
    assert chat.revision == 2
    assert "Revise" in d.agent.results[-2].content


def test_guide_can_correct_and_forget_memory_through_tools(guide_dependencies, guide_chat):
    d = guide_dependencies
    d.agent.actions = [GuideToolRequest("remember", key="audience", text="Beginners")]
    SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, guide_chat.id, "Remember", "one", 0))
    d.agent.actions = [GuideToolRequest("remember", key="audience", text="Advanced")]
    SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, guide_chat.id, "Correct", "two", 1))
    memory = ListGuideMemories(d).execute(GuideScopeRequest(OWNER, guide_chat.resource_id)).items[0]
    assert memory.revision == 2 and memory.content == "Advanced"
    d.agent.actions = [GuideToolRequest("forget_memory", key="audience")]
    SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, guide_chat.id, "Forget", "three", 2))
    assert not ListGuideMemories(d).execute(GuideScopeRequest(OWNER, guide_chat.resource_id)).items


@pytest.mark.parametrize(
    "action",
    [
        GuideToolRequest("get_lesson_artifact", key="unknown"),
        GuideToolRequest("unknown"),
        GuideToolRequest("remember", key="language", text="Spanish", scope="other-user"),
        GuideToolRequest("forget_memory", key="language", scope="other-user"),
    ],
)
def test_invalid_tools_leave_no_saved_changes(guide_dependencies, guide_chat, action):
    d = guide_dependencies
    d.agent.actions = [action]
    with pytest.raises(CourseError):
        SendGuideMessage(d).execute(
            SendGuideMessageRequest(OWNER, guide_chat.id, "Hello", "one", 0)
        )
    assert not GetGuideThread(d).execute(GuideThreadRequest(OWNER, guide_chat.id)).turns


@pytest.mark.parametrize("revise", [False, True])
def test_thumbnail_does_not_interrupt_guide_or_get_overwritten(
    guide_dependencies, guide_chat, revise
):
    d = guide_dependencies
    before = d.lessons.require_by_id(LessonId(guide_chat.resource_id))
    if revise:
        d.agent.actions = [GuideToolRequest("revise_outline", text="Generate an outline")]
    d.agent.during_run = lambda: d.lessons.save(
        replace(before, content=replace(before.content, image="concurrent-thumbnail"))
    )

    SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, guide_chat.id, "Help", "one", 0))

    saved = d.lessons.require_by_id(LessonId(guide_chat.resource_id))
    assert saved.content.image == "concurrent-thumbnail"
    assert bool(saved.content.plan) is revise
    assert len(d.repository.turns) == 1


def test_guide_keeps_its_history_separate_and_delegates_to_the_producer_session(
    guide_dependencies,
    guide_course,
):
    from app.courses.domain.guide import GuideThreadId
    from app.courses.ports.syllabus_agent import ConversationTurn, SyllabusConversation

    d = guide_dependencies
    producer_id = "agent_00000000-0000-0000-0000-000000000001"
    d.syllabuses.items[str(guide_course.id)] = SyllabusConversation(
        str(guide_course.id),
        revision=1,
        history_json="native producer history",
        turns=(ConversationTurn("Original brief", "Original draft"),),
        agent_session_id=producer_id,
    )
    chat = CreateGuideThread(d).execute(
        CreateGuideThreadRequest(OWNER, str(guide_course.id), "syllabus", "Refine")
    )
    assert not d.repository.require_by_id(GuideThreadId(chat.id)).history_json
    assert not d.repository.list_turns(GuideThreadId(chat.id))
    d.agent.actions = [GuideToolRequest("revise_outline", text="Add examples")]
    SendGuideMessage(d).execute(SendGuideMessageRequest(OWNER, chat.id, "Add examples", "one", 0))
    delegated = d.syllabus_agent.requests[-1].session
    assert delegated.session_id == producer_id
    assert delegated.owner_id == OWNER and delegated.resource_id == str(guide_course.id)


def test_delegated_clarification_saves_the_producer_session_without_an_outline(
    guide_dependencies,
    guide_course,
):
    d = guide_dependencies
    producer_id = "agent_00000000-0000-0000-0000-000000000001"
    d.syllabus_agent.plan = None
    d.syllabus_agent.session_id = producer_id
    chat = CreateGuideThread(d).execute(
        CreateGuideThreadRequest(OWNER, str(guide_course.id), "syllabus", "Plan")
    )
    d.agent.actions = [GuideToolRequest("revise_outline", text="Help me choose")]
    chat = SendGuideMessage(d).execute(
        SendGuideMessageRequest(OWNER, chat.id, "Help me choose", "first", 0)
    )
    saved = d.syllabuses.get_by_course_id(guide_course.id)
    assert saved.agent_session_id == producer_id and saved.curriculum is None
    assert saved.revision == 1
    assert not d.repository.list_versions(str(guide_course.id))
    SendGuideMessage(d).execute(
        SendGuideMessageRequest(OWNER, chat.id, "Python, please", "second", chat.revision)
    )
    assert d.syllabus_agent.requests[-1].session.session_id == producer_id
