import json

from redis import Redis
from redis.exceptions import RedisError

TOPICS = ("Computer science", "AI & data science", "Engineering", "Mathematics")


class RedisCatalog:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def topics(self) -> tuple[str, ...]:
        try:
            cached = self._redis.get("course-maker:catalog:v1")
            if isinstance(cached, (str, bytes)):
                values = json.loads(cached)
                if isinstance(values, list) and all(isinstance(v, str) for v in values):
                    return tuple(values)
            self._redis.setex("course-maker:catalog:v1", 3600, json.dumps(TOPICS))
        except (RedisError, ValueError, TypeError):
            pass
        return TOPICS
