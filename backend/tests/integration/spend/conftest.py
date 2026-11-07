import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
from testcontainers.community.postgres import PostgresContainer

from app.courses.adapters.persistence.models import CourseRecord
from app.courses.adapters.persistence.spend import GenerationStepRecord, SqlSpendRepository
from app.courses.adapters.persistence.standalone import StandaloneLessonRecord
from app.shared.infrastructure.database import Base


@pytest.fixture(scope="session")
def spend_engine():
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        engine = create_engine(container.get_connection_url())
        Base.metadata.create_all(
            engine,
            tables=[
                CourseRecord.__table__,
                StandaloneLessonRecord.__table__,
                GenerationStepRecord.__table__,
            ],
        )
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def spend_repository(spend_engine):
    sessions = sessionmaker(spend_engine)
    with sessions() as session, session.begin():
        session.add(CourseRecord(id="course_test", title="Test", status="draft", payload={}))
    try:
        yield SqlSpendRepository(sessions)
    finally:
        with spend_engine.begin() as connection:
            connection.execute(delete(GenerationStepRecord))
            connection.execute(delete(CourseRecord))
