from app.courses.adapters.persistence.agent_sessions import AgentSessionRecord  # noqa: F401
from app.courses.adapters.persistence.creators import CreatorRecord  # noqa: F401
from app.courses.adapters.persistence.lesson_interactive import LessonInteractiveRecord  # noqa: F401
from app.courses.adapters.persistence.learning_activity import (  # noqa: F401
    LearningActivityRecord,
)
from app.courses.adapters.persistence.lesson_quiz import (  # noqa: F401
    LessonQuizRecord, LessonQuizAttemptRecord,
)
from app.courses.adapters.persistence.guide import (  # noqa: F401
    GuideThreadRecord, GuideTurnRecord, GuideMemoryRecord, OutlineVersionRecord,
)
from app.courses.adapters.persistence.spend import ModelChargeRecord  # noqa: F401
from app.credits.adapters.persistence import (  # noqa: F401
    CreditAccountRecord, CreditTransactionRecord, CreditCheckoutRecord,
)
from alembic import context
from sqlalchemy import create_engine, pool

from app.courses.adapters.persistence.models import CourseRecord  # noqa: F401
from app.courses.adapters.persistence.conversations import SyllabusConversationRecord  # noqa: F401
from app.courses.adapters.persistence.standalone import StandaloneLessonRecord  # noqa: F401
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.settings import DatabaseSettings
from app.users.adapters.persistence.models import UserRecord  # noqa: F401
from app.users.adapters.persistence.authentication import (  # noqa: F401
    AccountRecord, AccountActionRecord, AccountMailRecord, LoginSessionRecord,
)

configured_url = context.config.attributes.get("database_url")
settings = DatabaseSettings(database_url=configured_url) if configured_url else DatabaseSettings()
url = settings.database_url
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
