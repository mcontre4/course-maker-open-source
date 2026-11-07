from dataclasses import dataclass

from app.courses.application.standalone import _StandaloneUseCase
from app.courses.application.standalone_dto import StandaloneLessonResponse, standalone_response


@dataclass(frozen=True)
class SaveStandaloneScriptRequest:
    lesson_id: str
    owner_id: str
    expected_revision: int
    narrations: tuple[str, ...]


class SaveStandaloneScript(_StandaloneUseCase):
    def execute(self, request: SaveStandaloneScriptRequest) -> StandaloneLessonResponse:
        with self._uow:
            before = self._load(request.lesson_id, request.owner_id, lock=True)
            before.require_revision(request.expected_revision)
            updated = before.edit_script(request.narrations)
            self._lessons.save(updated)
            self._uow.commit()
        return standalone_response(updated)
