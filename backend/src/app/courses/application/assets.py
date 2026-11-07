from dataclasses import dataclass

from app.courses.domain.assets import UploadSpecification
from app.courses.domain.identifiers import AssetId, CourseId
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.storage import Storage
from app.shared.application.unit_of_work import UnitOfWork
from app.shared.domain.id_generator import IdGenerator


@dataclass(frozen=True)
class UploadAssetRequest:
    course_id: str
    content_type: str
    size: int


@dataclass(frozen=True)
class DownloadAssetRequest:
    course_id: str
    asset_id: str


@dataclass(frozen=True)
class AssetResponse:
    id: str
    url: str
    method: str
    expires_in: int
    content_type: str | None = None
    size: int | None = None
    required_headers: tuple[tuple[str, str], ...] = ()


class CreateAssetUpload:
    def __init__(
        self, courses: CourseRepository, storage: Storage, ids: IdGenerator, uow: UnitOfWork
    ) -> None:
        self._courses, self._storage, self._ids = courses, storage, ids
        self._uow = uow

    def execute(self, request: UploadAssetRequest) -> AssetResponse:
        upload = UploadSpecification(request.content_type, request.size)
        with self._uow:
            self._courses.require_by_id(CourseId(request.course_id))
        asset_id = f"asset_{self._ids.new_uuid()}"
        object_name = f"courses/{request.course_id}/{asset_id}"
        url = self._storage.upload_url(object_name, upload.content_type, upload.size)
        return AssetResponse(
            asset_id,
            url,
            "PUT",
            900,
            upload.content_type,
            upload.size,
            (
                ("Content-Type", upload.content_type),
                ("Content-Length", str(upload.size)),
                ("x-goog-if-generation-match", "0"),
            ),
        )


class GetAssetDownload:
    def __init__(self, courses: CourseRepository, storage: Storage, uow: UnitOfWork) -> None:
        self._courses, self._storage = courses, storage
        self._uow = uow

    def execute(self, request: DownloadAssetRequest) -> AssetResponse:
        with self._uow:
            self._courses.require_by_id(CourseId(request.course_id))
        asset_id = str(AssetId(request.asset_id))
        object_name = f"courses/{request.course_id}/{asset_id}"
        return AssetResponse(asset_id, self._storage.download_url(object_name), "GET", 900)
