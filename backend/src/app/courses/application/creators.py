from dataclasses import dataclass

from app.courses.application.lesson_video import LessonVideoResponse
from app.courses.domain.creator import CreatorProfile
from app.courses.domain.errors import CourseNotFound
from app.courses.domain.identifiers import CourseId, LessonId
from app.courses.domain.standalone import LessonOwnerId
from app.courses.domain.syllabus import Lesson
from app.courses.ports.course_repository import CourseRepository
from app.courses.ports.creators import Creators
from app.courses.ports.lesson_video import LessonVideo
from app.courses.ports.storage import Storage
from app.shared.application.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CreatorRequest:
    creator_id: str


@dataclass(frozen=True)
class SaveCreatorRequest:
    creator_id: str
    name: str
    picture: str | None = None


@dataclass(frozen=True)
class CreatorResponse:
    id: str
    name: str
    picture: str | None


@dataclass(frozen=True)
class PublishedLessonResponse:
    id: str
    title: str
    minutes: int
    image: str
    video_url: str | None
    course_id: str | None = None


@dataclass(frozen=True)
class PublishedCourseResponse:
    id: str
    title: str
    description: str
    image: str
    lessons: tuple[PublishedLessonResponse, ...]


@dataclass(frozen=True)
class CreatorPageResponse:
    creator: CreatorResponse
    lessons: tuple[PublishedLessonResponse, ...]
    courses: tuple[PublishedCourseResponse, ...]


def _profile(profile: CreatorProfile) -> CreatorResponse:
    return CreatorResponse(str(profile.id), profile.name, profile.picture)


def _published(lesson: Lesson, course_id: str | None = None) -> PublishedLessonResponse:
    return PublishedLessonResponse(
        str(lesson.id), lesson.title, lesson.minutes, lesson.image, lesson.video_url, course_id
    )


class GetOwnCreator:
    def __init__(self, creators: Creators, uow: UnitOfWork) -> None:
        self._creators, self._uow = creators, uow

    def execute(self, request: CreatorRequest) -> CreatorResponse:
        identifier = LessonOwnerId(request.creator_id)
        with self._uow:
            profile = self._creators.get_by_id(identifier)
            if profile is None:
                profile = CreatorProfile(identifier)
                self._creators.add(profile)
                profile = self._creators.get_by_id(identifier) or profile
                self._uow.commit()
        return _profile(profile)


class SaveCreator:
    def __init__(self, creators: Creators, uow: UnitOfWork) -> None:
        self._creators, self._uow = creators, uow

    def execute(self, request: SaveCreatorRequest) -> CreatorResponse:
        profile = CreatorProfile(
            LessonOwnerId(request.creator_id), request.name.strip(), request.picture
        )
        with self._uow:
            self._creators.save(profile)
            self._uow.commit()
        return _profile(profile)


class GetCreatorPage:
    def __init__(self, creators: Creators) -> None:
        self._creators = creators

    def execute(self, request: CreatorRequest) -> CreatorPageResponse:
        identifier = LessonOwnerId(request.creator_id)
        profile = self._creators.get_by_id(identifier)
        standalone = self._creators.lessons_by_creator(identifier)
        courses = self._creators.courses_by_creator(identifier)
        if profile is None and not standalone and not courses:
            raise CourseNotFound("Creator not found")
        return CreatorPageResponse(
            _profile(profile or CreatorProfile(identifier)),
            tuple(_published(item.content) for item in standalone if item.content.is_published),
            tuple(
                PublishedCourseResponse(
                    str(course.id),
                    course.title,
                    course.description,
                    course.image,
                    tuple(
                        _published(item, str(course.id))
                        for chapter in course.chapters
                        for item in chapter.lessons
                        if item.is_published
                    ),
                )
                for course in courses
                if any(item.is_published for chapter in course.chapters for item in chapter.lessons)
            ),
        )


@dataclass(frozen=True)
class PublishedLessonRequest:
    lesson_id: str
    course_id: str | None = None


@dataclass(frozen=True)
class WatchLessonResponse:
    creator: CreatorResponse | None
    lesson: PublishedLessonResponse


class GetPublishedLesson:
    def __init__(
        self,
        creators: Creators,
        courses: CourseRepository,
        storage: Storage | None,
        uow: UnitOfWork,
    ) -> None:
        self._creators, self._courses, self._storage, self._uow = creators, courses, storage, uow

    def _load(self, request: PublishedLessonRequest) -> tuple[Lesson, str | None]:
        if request.course_id:
            course = self._courses.require_by_id(CourseId(request.course_id))
            return course.lesson(str(LessonId(request.lesson_id))), course.owner_id
        standalone = self._creators.get_lesson(LessonId(request.lesson_id))
        if standalone is None:
            raise CourseNotFound("Lesson not found")
        return standalone.content, str(standalone.owner_id)

    def execute(self, request: PublishedLessonRequest) -> WatchLessonResponse:
        with self._uow:
            lesson, owner = self._load(request)
            if not lesson.is_published:
                raise CourseNotFound("Lesson not found")
            creator = None
            if owner:
                identifier = LessonOwnerId(owner)
                creator = _profile(
                    self._creators.get_by_id(identifier) or CreatorProfile(identifier)
                )
        video_url = lesson.video_url
        if not video_url and lesson.video_asset_id and self._storage:
            scope = f"courses/{request.course_id}" if request.course_id else f"lessons/{lesson.id}"
            video_url = self._storage.download_url(f"{scope}/{lesson.video_asset_id}")
        if not video_url and lesson.animation is None:
            raise CourseNotFound("Video is unavailable")
        published = PublishedLessonResponse(
            str(lesson.id), lesson.title, lesson.minutes, lesson.image, video_url, request.course_id
        )
        return WatchLessonResponse(creator, published)


@dataclass(frozen=True)
class DiscoveryRequest:
    limit: int = 12
    query: str = ""


@dataclass(frozen=True)
class DiscoveryResponse:
    lessons: tuple[PublishedLessonResponse, ...]
    courses: tuple[PublishedCourseResponse, ...]


class GetDiscovery:
    def __init__(self, creators: Creators) -> None:
        self._creators = creators

    def execute(self, request: DiscoveryRequest) -> DiscoveryResponse:
        return DiscoveryResponse(
            tuple(
                _published(item.content)
                for item in self._creators.latest_lessons(request.limit, request.query)
            ),
            tuple(
                PublishedCourseResponse(
                    str(course.id),
                    course.title,
                    course.description,
                    course.image,
                    tuple(
                        _published(item, str(course.id))
                        for chapter in course.chapters
                        for item in chapter.lessons
                        if item.is_published
                    ),
                )
                for course in self._creators.latest_courses(request.limit, request.query)
            ),
        )


class GetPublishedAnimation:
    def __init__(
        self, creators: Creators, courses: CourseRepository, videos: LessonVideo, uow: UnitOfWork
    ) -> None:
        self._creators, self._courses, self._videos, self._uow = creators, courses, videos, uow

    def execute(self, request: PublishedLessonRequest) -> LessonVideoResponse:
        with self._uow:
            if request.course_id:
                lesson = self._courses.require_by_id(CourseId(request.course_id)).lesson(
                    str(LessonId(request.lesson_id))
                )
            else:
                standalone = self._creators.get_lesson(LessonId(request.lesson_id))
                if standalone is None:
                    raise CourseNotFound("Lesson not found")
                lesson = standalone.content
            animation = lesson.animation
            if animation is None:
                raise CourseNotFound("Video is unavailable")
        return LessonVideoResponse(self._videos.read(animation))
