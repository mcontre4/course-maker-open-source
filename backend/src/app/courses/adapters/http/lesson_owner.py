"""Signed browser identity until account authentication is introduced.

Never accept ownership from a body or an unsigned client header. A future login
adapter can replace this dependency with the authenticated user's stable ID.
"""

import hashlib
import hmac

from fastapi import Request, Response

from app.shared.domain.id_generator import IdGenerator

COOKIE = "course_maker_owner"


class SignedLessonOwner:
    def __init__(self, secret: bytes, ids: IdGenerator) -> None:
        self._secret, self._ids = secret, ids

    def resolve(self, request: Request, response: Response) -> str:
        cookie = request.cookies.get(COOKIE, "")
        owner, separator, signature = cookie.rpartition(".")
        expected = hmac.new(self._secret, owner.encode(), hashlib.sha256).hexdigest()
        if separator and owner.startswith("user_") and hmac.compare_digest(signature, expected):
            return owner
        owner = "user_" + str(self._ids.new_uuid())
        signature = hmac.new(self._secret, owner.encode(), hashlib.sha256).hexdigest()
        response.set_cookie(
            COOKIE,
            owner + "." + signature,
            max_age=31536000,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
        )
        return owner
