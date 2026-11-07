import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.courses.adapters.http.lesson_video import (
    get_standalone_video_reader,
    router,
)
from app.courses.adapters.http.standalone import get_owner
from app.courses.application.lesson_video import LessonVideoResponse

pytestmark = pytest.mark.integration


class SavedVideo:
    def execute(self, request):
        assert request.lesson_id == "lesson_saved"
        assert request.owner_id == "owner"
        return LessonVideoResponse(b"0123456789")


@pytest.mark.parametrize(
    ("byte_range", "status", "content", "content_range"),
    [
        (None, 200, b"0123456789", None),
        ("bytes=0-3", 206, b"0123", "bytes 0-3/10"),
        ("bytes=7-", 206, b"789", "bytes 7-9/10"),
        ("bytes=-3", 206, b"789", "bytes 7-9/10"),
        ("bytes=0-999", 206, b"0123456789", "bytes 0-9/10"),
        ("bytes=20-", 416, b"", "bytes */10"),
        ("bytes=8-3", 416, b"", "bytes */10"),
        ("bytes=-0", 416, b"", "bytes */10"),
        ("bytes=0-1,3-4", 416, b"", "bytes */10"),
    ],
)
def test_playback_maps_byte_ranges_for_seekable_video(byte_range, status, content, content_range):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_owner] = lambda: "owner"
    app.dependency_overrides[get_standalone_video_reader] = SavedVideo
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/lessons/lesson_saved/video",
            headers={"Range": byte_range} if byte_range else {},
        )
    assert response.status_code == status
    assert response.content == content
    assert response.headers.get("content-range") == content_range
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["accept-ranges"] == "bytes"


@pytest.mark.parametrize("kind", ["standalone", "course"])
def test_playback_selection_and_isolated_html_headers(kind):
    from app.courses.adapters.http.lesson_video import (
        get_course_playback,
        get_standalone_playback,
    )
    from app.courses.application.lesson_playback import LessonPlaybackResponse

    class SavedPlayback:
        def execute(self, request):
            assert request.lesson_id == "lesson_saved"
            if kind == "standalone":
                assert request.owner_id == "owner"
            else:
                assert request.course_id == "course_saved"
            if request.preview:
                assert request.source_hash == "b" * 64
                return LessonPlaybackResponse("b" * 64, preview_html="<html>code</html>")
            return LessonPlaybackResponse("b" * 64, video_ready=False)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_owner] = lambda: "owner"
    dependency = get_standalone_playback if kind == "standalone" else get_course_playback
    app.dependency_overrides[dependency] = SavedPlayback
    base = (
        "/api/v1/lessons/lesson_saved"
        if kind == "standalone"
        else "/api/v1/courses/course_saved/lessons/lesson_saved"
    )
    with TestClient(app) as client:
        status = client.get(base + "/playback")
        assert status.json() == {"sourceHash": "b" * 64, "videoReady": False}
        assert status.headers["cache-control"] == "private, no-store"
        preview = client.get(base + "/preview", params={"v": "b" * 64})
        assert preview.text == "<html>code</html>"
        assert preview.headers["content-type"].startswith("text/html")
        policy = preview.headers["content-security-policy"]
        assert "sandbox allow-scripts" in policy
        assert "allow-same-origin" not in policy
        assert "connect-src 'none'" in policy
        assert client.get(base + "/preview").status_code == 422
