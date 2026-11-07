from dataclasses import dataclass

from app.courses.application import use_cases as uc
from app.courses.application.assets import CreateAssetUpload, GetAssetDownload
from app.courses.application.catalog import GetCatalog


@dataclass(frozen=True)
class CourseServices:
    create: uc.CreateCourse
    list: uc.ListCourses
    get: uc.GetCourse
    update: uc.UpdateCourse
    delete: uc.DeleteCourse
    syllabus: uc.ReplaceSyllabus
    topic: uc.EditSyllabusTopic
    approve: uc.ApproveSyllabus
    lesson: uc.GetLesson
    review: uc.ReviewLesson
    submit: uc.SubmitQuiz
    progress: uc.GetProgress
    content: uc.UpdateLessonContent
    attempts: uc.GetQuizAttempts


@dataclass(frozen=True)
class AssetServices:
    upload: CreateAssetUpload
    download: GetAssetDownload


@dataclass(frozen=True)
class CatalogServices:
    get: GetCatalog
