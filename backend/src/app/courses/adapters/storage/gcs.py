from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from google.api_core.exceptions import GoogleAPIError, NotFound
from google.auth import credentials
from google.auth.exceptions import GoogleAuthError
from google.cloud.storage import Client  # type: ignore[import-untyped]

from app.courses.application.errors import StorageUnavailable
from app.courses.domain.errors import CourseNotFound


@contextmanager
def _storage_errors() -> Iterator[None]:
    try:
        yield
    except NotFound as exc:
        raise CourseNotFound("Asset has not been uploaded") from exc
    except (GoogleAPIError, GoogleAuthError) as exc:
        raise StorageUnavailable("Cloud Storage is unavailable") from exc


class GoogleCloudStorage:
    def __init__(
        self, client: Client, bucket: str, signing_credentials: credentials.Credentials
    ) -> None:
        self._bucket = client.bucket(bucket)
        self._credentials = signing_credentials

    def upload_url(self, object_name: str, content_type: str, size: int) -> str:
        with _storage_errors():
            return str(
                self._bucket.blob(object_name).generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=15),
                    method="PUT",
                    content_type=content_type,
                    headers={"Content-Length": str(size), "x-goog-if-generation-match": "0"},
                    credentials=self._credentials,
                )
            )

    def download_url(self, object_name: str) -> str:
        with _storage_errors():
            blob = self._bucket.blob(object_name)
            blob.reload()
            return str(
                blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(minutes=15),
                    method="GET",
                    generation=blob.generation,
                    credentials=self._credentials,
                )
            )
