from decimal import Decimal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COURSE_MAKER_", env_file=".env", extra="ignore")

    database_url: str

    @field_validator("database_url")
    @classmethod
    def supported_database(cls, value: str) -> str:
        if make_url(value).drivername not in {"mysql+pymysql", "postgresql+psycopg"}:
            raise ValueError("Use a mysql+pymysql or postgresql+psycopg database URL")
        return value


class Settings(DatabaseSettings):
    auth_enabled: bool = False
    stripe_secret_key: SecretStr = SecretStr("")
    stripe_webhook_secret: SecretStr = SecretStr("")
    credit_create_cost: int = Field(default=1, ge=1)
    credit_generate_cost: int = Field(default=5, ge=1)
    credit_media_cost: int = Field(default=10, ge=1)
    credit_automatic_cost: int = Field(default=25, ge=1)

    @model_validator(mode="after")
    def _stripe_config(self) -> "Settings":
        if bool(self.stripe_secret_key.get_secret_value()) != bool(
            self.stripe_webhook_secret.get_secret_value()
        ):
            raise ValueError("Configure both Stripe secret key and webhook secret")
        return self

    auth_public_url: str = "http://localhost:5173"
    auth_session_seconds: int = Field(default=28800, ge=300, le=604800)
    auth_idle_seconds: int = Field(default=1800, ge=60, le=86400)
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_starttls: bool = True
    mail_from: str = "accounts@localhost"

    @field_validator("auth_public_url")
    @classmethod
    def _auth_public_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or not parsed.hostname
            or parsed.scheme not in {"https", "http"}
            or (
                parsed.scheme == "http"
                and parsed.hostname
                not in {
                    "localhost",
                    "127.0.0.1",
                    "::1",
                }
            )
        ):
            raise ValueError("AUTH_PUBLIC_URL must be an HTTPS origin (HTTP only on loopback)")
        return value.rstrip("/")

    @model_validator(mode="after")
    def _authentication_config(self) -> "Settings":
        if not self.auth_enabled:
            return self
        if "*" in self.cors_origins:
            raise ValueError("Account credentials require explicit CORS origins")
        if bool(self.google_client_id) != bool(self.google_client_secret.get_secret_value()):
            raise ValueError("Configure both Google client ID and secret")
        if self.auth_public_url.startswith("https://") and not self.smtp_starttls:
            raise ValueError("Production account email requires SMTP TLS")
        return self

    elevenlabs_usd_per_credit: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)

    @field_validator("elevenlabs_usd_per_credit", mode="before")
    @classmethod
    def _optional_credit_rate(cls, value: str | Decimal | None) -> str | Decimal | None:
        return None if value == "" else value

    redis_url: str = "redis://localhost:6379/0"
    api_key: SecretStr = Field(min_length=32)
    internal_tools_key: SecretStr = SecretStr("")

    @field_validator("internal_tools_key")
    @classmethod
    def _internal_key_length(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value() and len(value.get_secret_value()) < 32:
            raise ValueError("Internal tools key must have at least 32 characters")
        return value

    cors_origins: list[str] = ["http://localhost:5173"]
    gcs_bucket: str | None = None
    gcp_project: str | None = None
    gcs_signer_email: str | None = None
    openrouter_api_key: SecretStr = SecretStr("")
    thumbnail_model: str = Field(default="openai/gpt-6.1-sol", min_length=1)
    tavily_api_key: SecretStr = SecretStr("")

    animator_tools_directory: str = "../tools/animator"
    animation_local_directory: str = ".artifacts/animation"
    lesson_video_image: str = "course-maker-renderer:canvas-v1"
    animator_image: str = "course-maker-animator:canvas-v1"
    animator_timeout_sec: int = Field(default=1800, ge=60, le=1800)
    animator_max_attempts: int = Field(default=2, ge=1, le=3)

    elevenlabs_api_key: SecretStr = SecretStr("")
    elevenlabs_voice_id: str = "6WwXjDDEMyNmFG95zycZ"
    speech_storage_backend: str = Field(default="local", pattern="^(local|gcs)$")
    speech_local_directory: str = ".artifacts/speech"
    speech_stability: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    speech_similarity: float = Field(default=0.75, ge=0, le=1, allow_inf_nan=False)
    speech_clone_strength: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    speech_silence_between_scenes_sec: float = Field(default=0.0, ge=0, le=5, allow_inf_nan=False)
