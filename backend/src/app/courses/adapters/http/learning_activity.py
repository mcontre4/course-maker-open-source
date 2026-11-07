from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.courses.adapters.http.schema import HttpModel
from app.courses.adapters.http.standalone import Owner
from app.courses.application.learning_activity import (
    GetLearningActivity,
    GetLearningActivityRequest,
    RecordLearningActivity,
    RecordLearningActivityRequest,
)

router = APIRouter(prefix="/api/v1/learning-activity", tags=["learning activity"])


def get_learning_activity() -> GetLearningActivity:
    raise RuntimeError("Learning activity is not configured")


def get_record_learning_activity() -> RecordLearningActivity:
    raise RuntimeError("Learning activity is not configured")


class LearningActivityItemView(HttpModel):
    item_id: str
    last_opened_at: str


class LearningActivityView(HttpModel):
    items: tuple[LearningActivityItemView, ...]


@router.get("")
def learning_activity(
    owner: Owner,
    service: Annotated[GetLearningActivity, Depends(get_learning_activity)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> LearningActivityView:
    return LearningActivityView.model_validate(
        service.execute(GetLearningActivityRequest(owner, limit))
    )


@router.put("/{item_id}", status_code=204)
def record_learning_activity(
    item_id: str,
    owner: Owner,
    service: Annotated[RecordLearningActivity, Depends(get_record_learning_activity)],
) -> None:
    # Returning nothing keeps the owner cookie set on FastAPI's injected response.
    service.execute(RecordLearningActivityRequest(owner, item_id))
