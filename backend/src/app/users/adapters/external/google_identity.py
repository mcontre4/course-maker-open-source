import base64
import hashlib
import hmac
from typing import Protocol
from urllib.parse import urlencode

import httpx
import jwt
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.users.application.auth_errors import AuthenticationError, AuthenticationUnavailableError
from app.users.ports.authentication import GoogleFlow, GoogleIdentity


class SigningKeys(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK: ...


class GoogleClaims(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    sub: str = Field(min_length=1, max_length=255)
    email: EmailStr
    email_verified: bool
    nonce: str
    given_name: str = Field(default="Google", max_length=100)
    family_name: str = Field(default="User", max_length=100)
    azp: str | None = None


class GoogleOpenId:
    def __init__(
        self,
        client: httpx.Client,
        keys: SigningKeys,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self._client, self._keys = client, keys
        self._client_id, self._client_secret = client_id, client_secret
        self._redirect_uri = redirect_uri

    def authorization_url(self, state: str, flow: GoogleFlow) -> str:
        if not self._client_id or not self._client_secret:
            raise AuthenticationUnavailableError()
        challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(flow.verifier.encode()).digest(),
            )
            .rstrip(b"=")
            .decode()
        )
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": flow.nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )

    def exchange(self, code: str, flow: GoogleFlow) -> GoogleIdentity:
        try:
            response = self._client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": self._redirect_uri,
                    "code": code,
                    "grant_type": "authorization_code",
                    "code_verifier": flow.verifier,
                },
            )
            response.raise_for_status()
            token = response.json()["id_token"]
            key = self._keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=["https://accounts.google.com", "accounts.google.com"],
                options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
            )
            identity = GoogleClaims.model_validate(claims)
            if (
                not identity.email_verified
                or not hmac.compare_digest(identity.nonce.encode(), flow.nonce.encode())
                or identity.azp not in {None, self._client_id}
                or (
                    isinstance(claims.get("aud"), list)
                    and len(claims["aud"]) > 1
                    and identity.azp != self._client_id
                )
            ):
                raise AuthenticationError()
            return GoogleIdentity(
                identity.sub, str(identity.email), identity.given_name, identity.family_name
            )
        except httpx.RequestError as exc:
            raise AuthenticationUnavailableError() from exc
        except (httpx.HTTPStatusError, jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
            raise AuthenticationError() from exc
