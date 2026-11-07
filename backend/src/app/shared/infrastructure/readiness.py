from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.shared.domain.readiness import Readiness


class InfrastructureReadinessProbe:
    def __init__(self, engine: Engine, redis: Redis, storage_configured: bool) -> None:
        self._engine, self._redis = engine, redis
        self._storage_configured = storage_configured

    def _database_ready(self) -> bool:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True

    def _cache_ready(self) -> bool:
        try:
            self._redis.ping()
        except RedisError:
            return False
        return True

    def status(self) -> Readiness:
        return Readiness(self._database_ready(), self._cache_ready(), self._storage_configured)
