from collections.abc import Iterator
from typing import Annotated

import httpx
import pytest
from fakes.courses import SequenceIds
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.courses.adapters.ai.spend import ProviderBilling, ProviderUsageTracking
from app.courses.adapters.ai.thumbnails import OpenRouterThumbnails
from app.courses.adapters.http import standalone, thumbnails
from app.courses.adapters.http.errors import register_error_handlers
from app.courses.adapters.persistence.spend import SqlSpendRepository
from app.courses.adapters.persistence.standalone import SqlAlchemyStandaloneLessons
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.application.standalone import CreateStandaloneLesson, GetStandaloneLesson
from app.courses.application.thumbnails import GenerateStandaloneThumbnail

pytestmark = pytest.mark.integration
OWNER = "user_00000000-0000-0000-0000-000000000001"


def test_draft_create_reload_and_regenerate_with_real_sql_and_http(
    thumbnail_database,
    thumbnail_server,
):
    sessions = sessionmaker(thumbnail_database, expire_on_commit=False)
    spend = SqlSpendRepository(sessions)
    with thumbnail_server() as (url, calls), httpx.Client(base_url=url) as provider:
        tracking = ProviderUsageTracking(spend, ProviderBilling(provider, "", None))
        provider.event_hooks.update(
            {"request": [tracking.request], "response": [tracking.response]}
        )
        generator = OpenRouterThumbnails(provider, "test-key", "fast-svg-model", "Fixed style")

        def session() -> Iterator[Session]:
            with sessions() as scoped:
                yield scoped

        def create(db: Annotated[Session, Depends(session)]):
            return CreateStandaloneLesson(
                SqlAlchemyStandaloneLessons(db),
                CourseUnitOfWork(db),
                SequenceIds(),
            )

        def read(db: Annotated[Session, Depends(session)]):
            return GetStandaloneLesson(SqlAlchemyStandaloneLessons(db), CourseUnitOfWork(db))

        def draw(db: Annotated[Session, Depends(session)]):
            return GenerateStandaloneThumbnail(
                SqlAlchemyStandaloneLessons(db),
                CourseUnitOfWork(db),
                generator,
                tracking,
            )

        app = FastAPI()
        app.include_router(standalone.router)
        app.include_router(thumbnails.router)
        register_error_handlers(app)
        app.dependency_overrides.update(
            {
                standalone.get_owner: lambda: OWNER,
                standalone.get_create: create,
                standalone.get_lesson: read,
                thumbnails.get_lesson_thumbnail: draw,
            }
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/lessons",
                json={
                    "style": {"visualStyleId": "flat-vector-science"},
                    "title": "Inertia",
                    "description": "Newton's first law",
                    "minutes": 3,
                    "generationMode": "fast",
                },
            )
            assert response.status_code == 201, response.text
            draft = response.json()
            assert draft["content"]["image"] == ""
            assert calls == []
            assert not draft["approved"]
            path = f"/api/v1/lessons/{draft['id']}"
            assert client.get(path).json() == draft
            assert len(spend.list_by_lesson_id(draft["id"])) == 0
            drawn = client.post(path + "/thumbnail", json={})
            assert drawn.status_code == 200, drawn.text
            illustrated = drawn.json()
            assert illustrated["content"]["image"].startswith("data:image/svg+xml;base64,")
            assert client.get(path).json() == illustrated
            assert client.post(path + "/thumbnail", json={}).json() == illustrated
            assert len(calls) == 1
            regenerated = client.post(path + "/thumbnail", json={"regenerate": True})
            assert regenerated.status_code == 200, regenerated.text
            assert regenerated.json()["revision"] == illustrated["revision"]
            assert len(calls) == 2
            charges = spend.list_by_lesson_id(draft["id"])
            assert len(charges) == 2
            assert all(charge.stage == "thumbnail" for charge in charges)
            steps = SqlSpendRepository(sessions).list_steps(lesson_id=draft["id"])
            assert len(steps) == 2
            assert all(step.stage == "thumbnail" for step in steps)
            assert all(step.finished_at >= step.started_at for step in steps)
            assert spend.list_steps(lesson_id="other_lesson") == ()
