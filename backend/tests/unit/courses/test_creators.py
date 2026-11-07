from dataclasses import replace

import pytest
from fakes.courses import RecordingStorage, RecordingUnitOfWork
from fakes.creators import InMemoryCreators

from app.courses.application.creators import (
    CreatorRequest,
    GetCreatorPage,
    GetOwnCreator,
    GetPublishedLesson,
    PublishedLessonRequest,
    SaveCreator,
    SaveCreatorRequest,
)
from app.courses.domain.course import Course
from app.courses.domain.creator import CreatorProfile
from app.courses.domain.duration import Duration
from app.courses.domain.errors import CourseError, CourseNotFound
from app.courses.domain.identifiers import ChapterId, CourseId, LessonId
from app.courses.domain.standalone import LessonOwnerId, StandaloneLesson
from app.courses.domain.syllabus import Chapter, Lesson

OWNER = "user_00000000-0000-0000-0000-000000000001"
OTHER = "user_00000000-0000-0000-0000-000000000002"
LESSON = "lesson_00000000-0000-0000-0000-000000000001"
COURSE = "course_00000000-0000-0000-0000-000000000001"
VIDEO = "https://example.com/lesson.mp4"


@pytest.fixture
def creators():
    return InMemoryCreators()


@pytest.fixture
def lesson():
    return Lesson(LessonId(LESSON), "Inertia", ("Motion",), 3)


def test_save_and_reload_public_identity(creators):
    uow = RecordingUnitOfWork(creators)
    saved = SaveCreator(creators, uow).execute(SaveCreatorRequest(OWNER, "  Ada  "))
    assert saved.name == "Ada"
    assert creators.get_by_id(LessonOwnerId(OWNER)).name == "Ada"
    assert GetOwnCreator(creators, uow).execute(CreatorRequest(OWNER)) == saved
    assert uow.commits == 1
    assert GetOwnCreator(creators, uow).execute(CreatorRequest(OTHER)).name == "Creator"
    SaveCreator(creators, uow).execute(SaveCreatorRequest(OWNER, "Ada Lovelace"))
    assert creators.get_by_id(LessonOwnerId(OWNER)).name == "Ada Lovelace"


@pytest.mark.parametrize(
    "name,picture",
    [
        (" ", None),
        ("a" * 81, None),
        ("Ada", "javascript:alert(1)"),
        ("Ada", "https://example.com/avatar.svg"),
        ("Ada", "data:image/svg+xml;base64,AAAA"),
        ("Ada", "a" * 1_400_001),
    ],
)
def test_invalid_identity(name, picture):
    with pytest.raises(CourseError):
        CreatorProfile(LessonOwnerId(OWNER), name, picture)


def test_avatar_can_be_removed(creators):
    use_case = SaveCreator(creators, RecordingUnitOfWork(creators))
    picture = "data:image/png;base64,AAAA"
    use_case.execute(SaveCreatorRequest(OWNER, "Ada", picture))
    assert creators.get_by_id(LessonOwnerId(OWNER)).picture == picture
    use_case.execute(SaveCreatorRequest(OWNER, "Ada"))
    assert creators.get_by_id(LessonOwnerId(OWNER)).picture is None


def test_profile_only_lists_finished_videos_for_this_creator(creators, lesson):
    creators.lessons = [
        StandaloneLesson(LessonOwnerId(OWNER), "Draft", lesson),
        StandaloneLesson(
            LessonOwnerId(OWNER),
            "Published",
            replace(lesson, id=LessonId(LESSON[:-1] + "2"), video_url=VIDEO),
        ),
        StandaloneLesson(LessonOwnerId(OTHER), "Other creator", replace(lesson, video_url=VIDEO)),
    ]
    chapter = Chapter(
        ChapterId("chapter_00000000-0000-0000-0000-000000000001"),
        "Motion",
        "Learn motion",
        (
            lesson,
            replace(
                lesson,
                id=LessonId(LESSON[:-1] + "2"),
                video_asset_id="asset_00000000-0000-0000-0000-000000000001",
            ),
        ),
    )
    creators.courses = [
        Course(
            CourseId(COURSE),
            "Physics",
            "Basics",
            Duration("total", 1),
            chapters=(chapter,),
            owner_id=OWNER,
        )
    ]
    result = GetCreatorPage(creators).execute(CreatorRequest(OWNER))
    assert [ls.title for ls in result.lessons] == ["Inertia"]
    assert len(result.courses) == 1
    assert len(result.courses[0].lessons) == 1
    assert result.courses[0].lessons[0].course_id == COURSE
    assert result.creator.name == "Creator"


def test_empty_and_unknown_profiles(creators):
    with pytest.raises(CourseNotFound):
        GetCreatorPage(creators).execute(CreatorRequest(OWNER))
    creators.save(CreatorProfile(LessonOwnerId(OWNER)))
    page = GetCreatorPage(creators).execute(CreatorRequest(OWNER))
    assert page.lessons == page.courses == ()


def test_watch_video_and_hide_draft_and_missing_lesson(creators, lesson):
    uow = RecordingUnitOfWork(creators)
    watch = GetPublishedLesson(creators, creators, None, uow)
    with pytest.raises(CourseNotFound):
        watch.execute(PublishedLessonRequest(LESSON))
    creators.lessons = [StandaloneLesson(LessonOwnerId(OWNER), "Private brief", lesson)]
    with pytest.raises(CourseNotFound):
        watch.execute(PublishedLessonRequest(LESSON))
    creators.lessons = [replace(creators.lessons[0], content=replace(lesson, video_url=VIDEO))]
    result = watch.execute(PublishedLessonRequest(LESSON))
    assert result.lesson.video_url == VIDEO
    assert result.creator.id == OWNER


def test_uploaded_video_uses_existing_asset_path_after_transaction(creators, lesson):
    asset = "asset_00000000-0000-0000-0000-000000000001"
    lesson = replace(lesson, video_asset_id=asset)
    chapter = Chapter(
        ChapterId("chapter_00000000-0000-0000-0000-000000000001"), "Motion", "Basics", (lesson,)
    )
    creators.courses = [
        Course(
            CourseId(COURSE),
            "Physics",
            "Basics",
            Duration("total", 1),
            chapters=(chapter,),
            owner_id=OWNER,
        )
    ]
    uow = RecordingUnitOfWork(creators)
    storage = RecordingStorage(uow)
    watch = GetPublishedLesson(creators, creators, storage, uow)
    result = watch.execute(PublishedLessonRequest(LESSON, COURSE))
    assert result.lesson.video_url == "https://storage.example/download"
    assert storage.calls == [f"courses/{COURSE}/{asset}"]
    assert result.creator.id == OWNER
    creators.courses = [replace(creators.courses[0], owner_id=None)]
    assert watch.execute(PublishedLessonRequest(LESSON, COURSE)).creator is None
    unavailable = GetPublishedLesson(creators, creators, None, uow)
    with pytest.raises(CourseNotFound, match="Video is unavailable"):
        unavailable.execute(PublishedLessonRequest(LESSON, COURSE))


def test_finished_animation_is_public_without_an_attached_video(creators):
    from fakes.lesson_video import RecordingLessonVideo
    from fixtures.public_content import finished_course

    from app.courses.application.creators import GetPublishedAnimation

    course = finished_course()
    lesson = course.chapters[0].lessons[0]
    creators.courses = [course]
    creators.lessons = [
        StandaloneLesson(LessonOwnerId(OWNER), "Private notes", lesson, approved=True)
    ]
    page = GetCreatorPage(creators).execute(CreatorRequest(OWNER))
    assert page.lessons[0].id == str(lesson.id)
    assert page.courses[0].lessons[0].id == str(lesson.id)
    uow = RecordingUnitOfWork(creators)
    watch = GetPublishedLesson(creators, creators, None, uow)
    assert watch.execute(PublishedLessonRequest(str(lesson.id))).lesson.video_url is None
    videos = RecordingLessonVideo(uow)
    service = GetPublishedAnimation(creators, creators, videos, uow)
    for course_id in (None, str(course.id)):
        assert (
            service.execute(PublishedLessonRequest(str(lesson.id), course_id)).content
            == b"saved-video"
        )
    assert videos.animations == [lesson.animation, lesson.animation]
    creators.lessons = [replace(creators.lessons[0], content=replace(lesson, animation=None))]
    with pytest.raises(CourseNotFound):
        service.execute(PublishedLessonRequest(str(lesson.id)))


def test_discovery_returns_public_dtos_from_newest_content(creators, lesson):
    from fixtures.public_content import finished_course

    from app.courses.application.creators import DiscoveryRequest, GetDiscovery

    assert GetDiscovery(creators).execute(DiscoveryRequest()).lessons == ()
    course = finished_course()
    creators.courses = [course]
    creators.lessons = [
        StandaloneLesson(LessonOwnerId(OWNER), "private", replace(lesson, video_url=VIDEO))
    ]
    response = GetDiscovery(creators).execute(DiscoveryRequest(1))
    assert response.lessons[0].id == str(lesson.id)
    assert response.courses[0].id == str(course.id)
    assert response.courses[0].lessons[0].course_id == str(course.id)
