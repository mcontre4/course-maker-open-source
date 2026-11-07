import hashlib
import json

from redis import Redis
from redis.exceptions import RedisError

from app.users.application.auth_errors import AuthenticationUnavailableError
from app.users.ports.authentication import GoogleFlow


class RedisGoogleFlows:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _key(self, state: str) -> str:
        return "auth:google:" + hashlib.sha256(state.encode()).hexdigest()

    def put(self, state: str, flow: GoogleFlow) -> None:
        try:
            self._redis.set(
                self._key(state),
                json.dumps(
                    {
                        "nonce": flow.nonce,
                        "verifier": flow.verifier,
                    }
                ),
                ex=600,
            )
        except RedisError as exc:
            raise AuthenticationUnavailableError() from exc

    def consume(self, state: str) -> GoogleFlow | None:
        try:
            raw = self._redis.getdel(self._key(state))
        except RedisError as exc:
            raise AuthenticationUnavailableError() from exc
        if not raw:
            return None
        if not isinstance(raw, (str, bytes, bytearray)):
            raise AuthenticationUnavailableError()
        data = json.loads(raw)
        return GoogleFlow(data["nonce"], data["verifier"])


class RedisAuthLimiter:
    # Atomic increment + expiry: multiple workers share the same limits.
    _SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def allow(self, key: str, limit: int, seconds: int = 900) -> bool:
        key = "auth:rate:" + hashlib.sha256(key.encode()).hexdigest()
        try:
            count = self._redis.eval(self._SCRIPT, 1, key, seconds)
            return int(count) <= limit  # type: ignore[arg-type]
        except RedisError as exc:
            raise AuthenticationUnavailableError() from exc
