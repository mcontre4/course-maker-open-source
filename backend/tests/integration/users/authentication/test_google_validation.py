import base64
import hashlib
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.users.adapters.external.google_identity import GoogleOpenId
from app.users.application.auth_errors import AuthenticationError, AuthenticationUnavailableError
from app.users.ports.authentication import GoogleFlow

pytestmark = pytest.mark.integration


class FixedSigningKeys:
    def __init__(self, public_key):
        self.key = jwt.PyJWK.from_json(jwt.algorithms.RSAAlgorithm.to_jwk(public_key))

    def get_signing_key_from_jwt(self, token):
        return self.key


@pytest.fixture
def google_keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key, FixedSigningKeys(key.public_key())


def provider(google_keys, overrides=None, invalid_signature=False):
    private, keys = google_keys
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "client-id",
        "sub": "stable-subject",
        "email": "ada@example.com",
        "email_verified": True,
        "nonce": "expected-nonce",
        "iat": now,
        "exp": now + 600,
        "given_name": "Ada",
        "family_name": "Lovelace",
    }
    claims.update(overrides or {})
    if invalid_signature:
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims, private, algorithm="RS256")

    def exchange(request):
        assert str(request.url) == "https://oauth2.googleapis.com/token"
        data = parse_qs(request.content.decode())
        assert data["code_verifier"] == ["test-verifier"]
        assert data["redirect_uri"] == ["https://app.example.com/api/v1/auth/google/callback"]
        return httpx.Response(200, json={"id_token": token})

    client = httpx.Client(transport=httpx.MockTransport(exchange))
    return GoogleOpenId(
        client, keys, "client-id", "secret", "https://app.example.com/api/v1/auth/google/callback"
    )


def test_google_authorization_code_pkce_and_verified_signature(google_keys):
    google = provider(google_keys)
    flow = GoogleFlow("expected-nonce", "test-verifier")
    query = parse_qs(urlsplit(google.authorization_url("state", flow)).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [
        base64.urlsafe_b64encode(hashlib.sha256(flow.verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    ]
    assert query["scope"] == ["openid email profile"]
    identity = google.exchange("valid-code", flow)
    assert identity.subject == "stable-subject" and identity.email == "ada@example.com"


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://evil.example"},
        {"aud": "other-client"},
        {"exp": 1},
        {"nonce": "wrong"},
        {"email_verified": False},
        {"email_verified": "true"},
        {"azp": "other-client"},
        {"sub": ""},
        {"email": "invalid"},
        {"aud": ["client-id", "other-client"]},
    ],
)
def test_google_rejects_invalid_claims(google_keys, claims):
    with pytest.raises(AuthenticationError):
        provider(google_keys, claims).exchange(
            "code", GoogleFlow("expected-nonce", "test-verifier")
        )


def test_google_rejects_invalid_signature(google_keys):
    with pytest.raises(AuthenticationError):
        provider(google_keys, invalid_signature=True).exchange(
            "code", GoogleFlow("expected-nonce", "test-verifier")
        )


def test_google_is_disabled_without_both_credentials(google_keys):
    _, keys = google_keys
    google = GoogleOpenId(httpx.Client(), keys, "", "", "https://app.example.com/callback")
    with pytest.raises(AuthenticationUnavailableError):
        google.authorization_url("state", GoogleFlow("nonce", "verifier"))
