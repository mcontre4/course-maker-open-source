import pytest
from fakes.courses import InMemoryCourses

from app.courses.application.authorize_access import AuthorizeCourseAccess, AuthorizeCourseRequest
from app.courses.domain.errors import CourseNotFound


def test_missing_course_does_not_reveal_resource_details():
    with pytest.raises(CourseNotFound, match="Course not found"):
        AuthorizeCourseAccess(InMemoryCourses()).execute(
            AuthorizeCourseRequest(
                "course_00000000-0000-0000-0000-000000000001",
                "owner",
            )
        )
