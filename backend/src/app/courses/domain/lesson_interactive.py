"""Versioned lesson activities, independent of the legacy plan-bound interactive."""

from dataclasses import dataclass, replace
from typing import Literal

from app.courses.domain.errors import CourseConflict, CourseError, CourseNotFound
from app.courses.domain.generation import GenerationMode
from app.courses.domain.identifiers import LessonId
from app.courses.domain.syllabus import Lesson
from app.shared.domain.prefixed_uuid import PrefixedUuid

MAX_INTERACTIVES = 10
MAX_HTML_BYTES = 512 * 1024
BUILD_LEASE_SECONDS = 15 * 60
BuildStage = Literal["reading_lesson", "designing", "building", "checking"]


def interactive_text(value: str, limit: int, label: str, *, required: bool = True) -> str:
    value = value.strip()
    if required and not value:
        raise CourseError(f"{label} cannot be empty.")
    if len(value) > limit:
        raise CourseError(f"Keep {label.lower()} under {limit} characters.")
    return value


class InteractiveId(PrefixedUuid):
    prefix = "interactive_"


@dataclass(frozen=True)
class InteractiveDetails:
    title: str
    goal: str = ""
    prompts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", interactive_text(self.title, 80, "Title"))
        object.__setattr__(self, "goal", interactive_text(self.goal, 200, "Goal", required=False))
        if len(self.prompts) > 6:
            raise CourseError("Use up to 6 things to try.")
        object.__setattr__(
            self, "prompts", tuple(interactive_text(p, 160, "Things to try") for p in self.prompts)
        )


@dataclass(frozen=True)
class InteractivePage:
    html: str
    details: InteractiveDetails | None = None
    session_id: str | None = None

    def __post_init__(self) -> None:
        if len(self.html.encode("utf-8")) > MAX_HTML_BYTES:
            raise CourseError(
                "The generated page exceeds the 512 KiB limit. Try a simpler request."
            )
        page = self.html.strip().lower()
        if not all(
            part in page for part in ("<!doctype html>", "<html", "<head", "<body", "</html>")
        ):
            raise CourseError("The builder did not return a complete HTML page. Please try again.")


@dataclass(frozen=True)
class InteractiveVersion:
    number: int
    request: str
    created_at: str
    html: str
    session_id: str | None = None


@dataclass(frozen=True)
class InteractiveBuild:
    token: str
    request: str
    started_at: str
    expires_at: float
    stage: BuildStage = "reading_lesson"


@dataclass(frozen=True)
class InteractiveFailure:
    request: str
    message: str


@dataclass(frozen=True)
class InteractiveLesson:
    content: Lesson
    owner_id: str | None
    description: str
    audience: str
    course_id: str | None = None

    def require_owner(self, owner_id: str) -> None:
        if self.owner_id != owner_id:
            raise CourseNotFound("Lesson not found")


@dataclass(frozen=True)
class LessonInteractive:
    id: InteractiveId
    lesson_id: LessonId
    brief: str
    details: InteractiveDetails
    created_at: str
    updated_at: str
    revision: int = 1
    versions: tuple[InteractiveVersion, ...] = ()
    current_version: int | None = None
    published_version: int | None = None
    build: InteractiveBuild | None = None
    failure: InteractiveFailure | None = None
    generation_mode: GenerationMode = GenerationMode.BALANCED
    details_customized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "brief", interactive_text(self.brief, 2000, "Description"))
        if self.revision < 1:
            raise CourseError("Invalid interactive revision.")
        numbers = tuple(v.number for v in self.versions)
        if numbers != tuple(sorted(set(numbers))) or any(n < 1 for n in numbers):
            raise CourseError("Interactive versions must have unique increasing numbers.")
        for selected in (self.current_version, self.published_version):
            if selected is not None and selected not in numbers:
                raise CourseError("Choose an existing interactive version.")
        if self.build and self.failure:
            raise CourseError("A running build cannot also be failed.")

    def version(self, number: int | None) -> InteractiveVersion | None:
        if number is None:
            return None
        for version in self.versions:
            if version.number == number:
                return version
        raise CourseNotFound("Interactive version not found")

    def require_revision(self, revision: int) -> None:
        if revision != self.revision:
            raise CourseConflict("This interactive changed. Reload before continuing.")

    def require_idle(self) -> None:
        if self.build:
            raise CourseConflict(
                "An interactive build is already running. Wait or cancel it first."
            )

    def start_build(
        self, request: str, token: str, now: str, timestamp: float
    ) -> "LessonInteractive":
        self.require_idle()
        return replace(
            self,
            build=InteractiveBuild(token, request, now, timestamp + BUILD_LEASE_SECONDS),
            failure=None,
            revision=self.revision + 1,
            updated_at=now,
        )

    def expire_build(self, now: str, timestamp: float) -> "LessonInteractive":
        if self.build and timestamp >= self.build.expires_at:
            return self.fail_build(
                "The build stopped before it finished. Please retry the build.", now
            )
        return self

    def fail_build(self, message: str, now: str) -> "LessonInteractive":
        if self.build is None:
            return self
        return replace(
            self,
            build=None,
            failure=InteractiveFailure(self.build.request, message),
            revision=self.revision + 1,
            updated_at=now,
        )

    def complete_build(self, page: InteractivePage, now: str) -> "LessonInteractive":
        if self.build is None:
            raise CourseConflict("The interactive build is no longer running.")
        first = not self.versions
        if first and (page.details is None or not 2 <= len(page.details.prompts) <= 4):
            raise CourseError("The builder omitted the title, goal or things to try. Please retry.")
        if first and page.details is not None and not page.details.goal:
            raise CourseError("The builder omitted the learning goal. Please retry.")
        number = max((v.number for v in self.versions), default=0) + 1
        return replace(
            self,
            details=page.details
            if first and not self.details_customized and page.details is not None
            else self.details,
            versions=(
                *self.versions,
                InteractiveVersion(number, self.build.request, now, page.html, page.session_id),
            ),
            current_version=number,
            build=None,
            failure=None,
            revision=self.revision + 1,
            updated_at=now,
        )

    def save_details(self, details: InteractiveDetails, now: str) -> "LessonInteractive":
        return replace(
            self,
            details=details,
            details_customized=True,
            revision=self.revision + 1,
            updated_at=now,
        )

    def restore(self, number: int, now: str) -> "LessonInteractive":
        self.require_idle()
        self.version(number)
        return replace(
            self,
            current_version=number,
            failure=None,
            revision=self.revision + 1,
            updated_at=now,
        )

    def publish(self, number: int | None, now: str) -> "LessonInteractive":
        self.version(number)
        return replace(self, published_version=number, revision=self.revision + 1, updated_at=now)

    def copy(
        self, identifier: InteractiveId, lesson_id: LessonId, *, include_drafts: bool
    ) -> "LessonInteractive | None":
        if include_drafts:
            failure = self.failure
            if self.build:
                failure = InteractiveFailure(
                    self.build.request,
                    "This lesson was copied before the build finished. Retry to build this copy.",
                )
            return replace(
                self,
                id=identifier,
                lesson_id=lesson_id,
                revision=1,
                build=None,
                failure=failure,
                versions=tuple(replace(v, session_id=None) for v in self.versions),
            )
        published = self.version(self.published_version)
        if published is None:
            return None
        # A learner copying a lesson gets only the page already shared with them.
        return replace(
            self,
            id=identifier,
            lesson_id=lesson_id,
            brief=self.details.title,
            revision=1,
            versions=(replace(published, number=1, request=self.details.title, session_id=None),),
            current_version=1,
            published_version=1,
            build=None,
            failure=None,
        )
