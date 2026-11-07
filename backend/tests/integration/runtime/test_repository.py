from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from app.courses.adapters.persistence.repository import MySqlCourseRepository
from app.courses.adapters.persistence.unit_of_work import CourseUnitOfWork
from app.courses.domain.course import Course
from app.courses.domain.duration import Duration
from app.courses.domain.errors import CourseConflict
from app.courses.domain.identifiers import CourseId

pytestmark = pytest.mark.integration
COURSE_ID = CourseId("course_00000000-0000-0000-0000-000000000001")


def make_course():
    return Course(COURSE_ID, "Python", "Learn Python", Duration("total", hours=10))


def test_round_trip_delete_and_literal_search(clean_mysql):
    with Session(clean_mysql) as session:
        repository = MySqlCourseRepository(session)
        original = make_course()
        repository.add(original)
        session.commit()
        assert repository.get_by_id(COURSE_ID) == original
        assert repository.list_courses("Python", "draft", 10, 0) == (original,)
        assert repository.count_courses("%", None) == 0
        assert repository.list_courses("", None, 10, 10) == ()
        repository.delete(original)
        session.commit()
        assert repository.get_by_id(COURSE_ID) is None


def test_rollback_keeps_original_state(clean_mysql):
    with Session(clean_mysql) as session:
        repository = MySqlCourseRepository(session)
        with pytest.raises(RuntimeError):
            with CourseUnitOfWork(session):
                repository.add(make_course())
                raise RuntimeError("failed operation")
    with Session(clean_mysql) as session:
        assert MySqlCourseRepository(session).get_by_id(COURSE_ID) is None


def test_concurrent_updates_return_conflict_without_lost_writes(clean_mysql):
    with Session(clean_mysql) as seed:
        MySqlCourseRepository(seed).add(make_course())
        seed.commit()
    with Session(clean_mysql) as first, Session(clean_mysql) as second:
        first_repo, second_repo = MySqlCourseRepository(first), MySqlCourseRepository(second)
        first_course = first_repo.require_by_id(COURSE_ID)
        second_course = second_repo.require_by_id(COURSE_ID)
        with CourseUnitOfWork(first) as uow:
            first_repo.save(replace(first_course, title="First update"))
            uow.commit()
        with pytest.raises(CourseConflict):
            with CourseUnitOfWork(second) as uow:
                second_repo.save(replace(second_course, title="Stale update"))
                uow.commit()
    with Session(clean_mysql) as session:
        assert MySqlCourseRepository(session).require_by_id(COURSE_ID).title == "First update"


def test_mysql_duplicate_email_is_an_application_error(clean_mysql):
    from app.users.adapters.mysql.user_repository import MySqlUserRepository
    from app.users.application.errors import EmailAlreadyRegisteredError
    from app.users.domain.user import User
    from app.users.domain.user_id import UserId

    first = User(
        UserId("user_00000000-0000-0000-0000-000000000001"), "same@example.com", "Ada", "Lovelace"
    )
    second = replace(first, id=UserId("user_00000000-0000-0000-0000-000000000002"))
    with Session(clean_mysql) as session:
        repo = MySqlUserRepository(session)
        repo.add(first)
        session.commit()
        with pytest.raises(EmailAlreadyRegisteredError):
            repo.add(second)
        session.rollback()
        assert repo.get_by_id(first.id) == first
        assert repo.get_by_id(second.id) is None


def test_mysql_primary_key_conflict_is_not_misreported_as_duplicate_email(clean_mysql):
    from sqlalchemy.exc import IntegrityError

    from app.users.adapters.mysql.user_repository import MySqlUserRepository
    from app.users.domain.user import User
    from app.users.domain.user_id import UserId

    first = User(
        UserId("user_00000000-0000-0000-0000-000000000001"), "first@example.com", "Ada", "Lovelace"
    )
    with Session(clean_mysql) as session:
        repo = MySqlUserRepository(session)
        repo.add(first)
        session.commit()
        with pytest.raises(IntegrityError):
            repo.add(replace(first, email="second@example.com"))
        session.rollback()
        assert repo.get_by_id(first.id).email == first.email
