from urllib.parse import parse_qs, urlparse

import pytest
from google.cloud.storage import Client
from google.oauth2.service_account import Credentials

from app.courses.adapters.storage.gcs import GoogleCloudStorage

pytestmark = pytest.mark.integration


def test_gcs_upload_signs_exact_content_type_size_and_create_only_precondition(
    service_account_info,
):
    credentials = Credentials.from_service_account_info(service_account_info)
    with Client(project="local-test", credentials=credentials) as client:
        storage = GoogleCloudStorage(client, "local-test-bucket", credentials)
        url = storage.upload_url("courses/course_1/asset_1", "image/png", 123)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.path == "/local-test-bucket/courses/course_1/asset_1"
    assert query["X-Goog-Expires"] == ["900"]
    assert query["X-Goog-SignedHeaders"] == [
        "content-length;content-type;host;x-goog-if-generation-match"
    ]
    assert query["X-Goog-Signature"]
