import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

pytestmark = pytest.mark.integration
BACKEND = Path(__file__).parents[3]
REPOSITORY = BACKEND.parent


def process_environment():
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COURSE_MAKER_", "COMPOSE_"))
    }


@pytest.mark.parametrize("use_environment_override", [False, True])
def test_migrations_share_api_dotenv_configuration(tmp_path, clean_mysql, use_environment_override):
    database_url = clean_mysql.url.render_as_string(hide_password=False)
    file_url = (
        "mysql+pymysql://unused:unused@localhost:1/unused"
        if use_environment_override
        else database_url
    )
    (tmp_path / ".env").write_text(f"COURSE_MAKER_DATABASE_URL={file_url}\n")
    environment = process_environment()
    environment["PYTHONPATH"] = str(BACKEND / "src")
    if use_environment_override:
        environment["COURSE_MAKER_DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(BACKEND / "alembic.ini"), "current"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    head = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini"))).get_current_head()
    assert f"{head} (head)" in result.stdout


def test_compose_forwards_optional_storage_and_frontend_configuration():
    expected = {
        "COURSE_MAKER_GCP_PROJECT": "configuration-test-project",
        "COURSE_MAKER_GCS_BUCKET": "configuration-test-bucket",
        "COURSE_MAKER_GCS_SIGNER_EMAIL": "signer@config-test-project.iam.gserviceaccount.com",
        "COURSE_MAKER_CORS_ORIGINS": '["https://frontend.example.com"]',
    }
    environment = {
        **process_environment(),
        **expected,
        "COURSE_MAKER_API_KEY": "configuration-test-private-key-32-characters",
    }
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            os.devnull,
            "-f",
            str(REPOSITORY / "compose.yaml"),
            "config",
            "--format",
            "json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(result.stdout)["services"]["api"]["environment"]
    assert {key: actual.get(key) for key in expected} == expected


def test_google_credentials_are_scoped_for_iam_signing(tmp_path, service_account_info):
    credentials_file = tmp_path / "service-account.json"
    credentials_file.write_text(json.dumps(service_account_info))
    environment = process_environment()
    environment.update(
        GOOGLE_APPLICATION_CREDENTIALS=str(credentials_file),
        GOOGLE_CLOUD_PROJECT="local-test",
        PYTHONPATH=str(BACKEND / "src"),
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; from app.main import load_storage_credentials; "
                "credentials, project = load_storage_credentials(); "
                "print(json.dumps({'requires_scopes': credentials.requires_scopes, "
                "'project': project}))"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {"requires_scopes": False, "project": "local-test"}


def test_accounts_are_opt_in_and_unused_provider_configuration_does_not_block_legacy_startup():
    from app.shared.infrastructure.settings import Settings

    settings = Settings(
        _env_file=None,
        database_url="mysql+pymysql://unused:unused@localhost/unused",
        api_key="test-legacy-private-service-key-of-sufficient-length",
        cors_origins=["*"],
        google_client_id="unused-client",
        smtp_starttls=False,
    )
    assert settings.auth_enabled is False


@pytest.mark.parametrize(
    "options",
    [
        {"cors_origins": ["*"]},
        {"google_client_id": "incomplete-client"},
        {"auth_public_url": "https://accounts.example.com", "smtp_starttls": False},
    ],
)
def test_enabled_accounts_retain_strict_configuration_validation(options):
    from pydantic import ValidationError

    from app.shared.infrastructure.settings import Settings

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="mysql+pymysql://unused:unused@localhost/unused",
            api_key="test-account-private-service-key-of-sufficient-length",
            auth_enabled=True,
            **options,
        )
