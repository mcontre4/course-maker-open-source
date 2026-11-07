import pytest
from fixtures.lesson_plan import lesson_plan
from fixtures.syllabus import COURSE_ID, LESSON_ID, make_planned_course
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.conversations import SqlAlchemySyllabusConversations
from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.domain.identifiers import CourseId
from app.courses.domain.lesson_plan import PlanGeneration
from app.courses.ports.syllabus_agent import SyllabusConversation

pytestmark = pytest.mark.integration


def test_plan_survives_new_repository_and_is_exposed_by_http(api, clean_mysql):
    course, curriculum = make_planned_course()
    brief = curriculum.chapters[0].lessons[0]
    plan = lesson_plan(brief)
    generation = PlanGeneration("openai/gpt-6.1-sol", 2, 1, 1000)
    planned = course.approve().plan_lesson(LESSON_ID, plan, generation)
    with Session(clean_mysql) as session:
        MySqlCourseRepository(session).add(planned)
        session.flush()
        SqlAlchemySyllabusConversations(session).save(
            SyllabusConversation(COURSE_ID, 1, curriculum=curriculum), 0
        )
        session.commit()
    with Session(clean_mysql) as session:
        saved = MySqlCourseRepository(session).require_by_id(CourseId(COURSE_ID))
        assert saved.lesson(LESSON_ID).plan == plan
        assert saved.lesson(LESSON_ID).plan_generation == generation
    path = f"/api/v1/courses/{COURSE_ID}"
    result = api.get(path + f"/lessons/{LESSON_ID}")
    assert result.status_code == 200
    assert result.json()["plan"]["lessonId"] == LESSON_ID
    assert result.json()["plan"]["beats"][0]["seconds"] == 600
    # Cached generation succeeds even with provider keys explicitly disabled.
    cached = api.post(path + "/lessons/generate", json={"lessonId": LESSON_ID})
    assert cached.status_code == 200, cached.text
    assert cached.json()["chapters"][0]["lessons"][0]["plan"] == result.json()["plan"]


def test_missing_credentials_returns_503_without_saving_plan(api, clean_mysql):
    draft, curriculum = make_planned_course()
    with Session(clean_mysql) as session:
        MySqlCourseRepository(session).add(draft.approve())
        session.flush()
        SqlAlchemySyllabusConversations(session).save(
            SyllabusConversation(COURSE_ID, 1, curriculum=curriculum), 0
        )
        session.commit()
    path = f"/api/v1/courses/{COURSE_ID}"
    result = api.post(path + "/lessons/generate", json={"lessonId": LESSON_ID})
    assert result.status_code == 503
    assert api.get(path + f"/lessons/{LESSON_ID}").json()["plan"] is None


@pytest.mark.parametrize("lesson_id", ["", "   ", 42])
def test_invalid_lesson_selector_is_rejected_at_http_boundary(api, draft_payload, lesson_id):
    course_id = api.post("/api/v1/courses", json=draft_payload).json()["id"]
    result = api.post(f"/api/v1/courses/{course_id}/lessons/generate", json={"lessonId": lesson_id})
    assert result.status_code == 422
