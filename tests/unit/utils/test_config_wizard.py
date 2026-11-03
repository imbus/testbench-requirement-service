"""Tests for the CLI configuration wizard helpers."""

import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import get_key

from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.utils import config_wizard

JIRA_READER_CLASS = "testbench_requirement_service.readers.JiraRequirementReader"
CREDENTIAL_ENV_VARS = [
    "JIRA_PASSWORD",
    "JIRA_BEARER_TOKEN",
    "JIRA_OAUTH2_CLIENT_SECRET",
    "JIRA_OAUTH1_ACCESS_TOKEN",
    "JIRA_OAUTH1_ACCESS_TOKEN_SECRET",
    "JIRA_OAUTH1_KEY_CERT",
]


@pytest.fixture(autouse=True)
def _clean_jira_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in CREDENTIAL_ENV_VARS:
        for name in (var, f"{var}_FILE"):
            # setenv first so monkeypatch records the original state and restores it on teardown
            monkeypatch.setenv(name, "")
            monkeypatch.delenv(name)


def test_configure_reader_passes_reader_config_to_oauth_wizard():
    """The 3LO OAuth wizard needs server_url and client credentials for the DC code exchange."""
    reader_config = {
        "server_url": "https://jira.example.com",
        "auth_type": "oauth2 3LO (user account)",
        "oauth2_client_id": "client-id",
        "oauth2_client_secret": "client-secret",
    }
    with (
        patch.object(config_wizard, "check_reader_dependencies"),
        patch.object(
            config_wizard, "get_reader_config_class", return_value=JiraRequirementReaderConfig
        ),
        patch.object(config_wizard, "prompt_model_fields", return_value=dict(reader_config)),
        patch.object(
            config_wizard, "run_jira_oauth_wizard", return_value="refresh-token"
        ) as oauth_wizard,
        patch.object(config_wizard, "seed_oauth2_refresh_token") as seed_token,
        patch.object(config_wizard, "store_credentials_in_env"),
        patch.object(config_wizard, "merge_with_defaults", side_effect=lambda config, _: config),
    ):
        config_wizard.configure_reader("jira", JIRA_READER_CLASS)

    oauth_wizard.assert_called_once()
    passed_config = oauth_wizard.call_args.args[0]
    assert passed_config["server_url"] == "https://jira.example.com"
    assert passed_config["oauth2_client_id"] == "client-id"
    seed_token.assert_called_once_with("refresh-token")


def test_store_credentials_in_env_writes_every_credential_and_strips_config(tmp_path: Path):
    dotenv_path = tmp_path / ".env"
    config = {
        "auth_type": "oauth1",
        "oauth1_consumer_key": "key",
        "oauth1_access_token": "at",
        "oauth1_access_token_secret": "ats",
        "oauth1_key_cert": "-----BEGIN-----\nx\n-----END-----\n",
    }
    stored = config_wizard.store_credentials_in_env(
        config, JiraRequirementReaderConfig, dotenv_path
    )
    assert stored == [
        "JIRA_OAUTH1_ACCESS_TOKEN",
        "JIRA_OAUTH1_ACCESS_TOKEN_SECRET",
        "JIRA_OAUTH1_KEY_CERT",
    ]
    assert config == {"auth_type": "oauth1", "oauth1_consumer_key": "key"}
    assert get_key(str(dotenv_path), "JIRA_OAUTH1_ACCESS_TOKEN_SECRET") == "ats"
    assert (
        get_key(str(dotenv_path), "JIRA_OAUTH1_KEY_CERT") == "-----BEGIN-----\nx\n-----END-----\n"
    )


def test_store_credentials_in_env_exports_to_process_environment(tmp_path: Path):
    config = {"auth_type": "basic", "password": "s3cret"}
    config_wizard.store_credentials_in_env(config, JiraRequirementReaderConfig, tmp_path / ".env")
    assert os.environ["JIRA_PASSWORD"] == "s3cret"


def test_store_credentials_in_env_ignores_runtime_tokens_and_missing_values(tmp_path: Path, capsys):
    config = {"auth_type": "oauth2 3LO", "oauth2_refresh_token": "rt", "oauth2_client_secret": ""}
    assert (
        config_wizard.store_credentials_in_env(
            config, JiraRequirementReaderConfig, tmp_path / ".env"
        )
        == []
    )
    assert config["oauth2_refresh_token"] == "rt"
    assert not (tmp_path / ".env").exists()
    assert capsys.readouterr().out == ""


def test_store_credentials_in_env_prints_names_not_values(tmp_path: Path, capsys):
    config_wizard.store_credentials_in_env(
        {"password": "s3cret"}, JiraRequirementReaderConfig, tmp_path / ".env"
    )
    out = capsys.readouterr().out
    assert f"✓ Stored JIRA_PASSWORD in {tmp_path / '.env'}" in out
    assert "Keep this file out of version control" in out
    assert "s3cret" not in out


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file permissions")
def test_store_credentials_in_env_creates_owner_only_dotenv(tmp_path: Path):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("OTHER=1\n")
    dotenv_path.chmod(0o644)
    config_wizard.store_credentials_in_env(
        {"password": "s3cret"}, JiraRequirementReaderConfig, dotenv_path
    )
    assert stat.S_IMODE(dotenv_path.stat().st_mode) == 0o600
    assert get_key(str(dotenv_path), "OTHER") == "1"


def test_configure_reader_stores_credentials_in_env_not_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    dotenv_path = tmp_path / ".env"
    monkeypatch.setattr(config_wizard, "DEFAULT_DOTENV_PATH", dotenv_path)
    answers = {
        "server_url": "https://jira.example.com",
        "auth_type": "basic",
        "username": "u",
        "password": "s3cret",
    }
    with (
        patch.object(config_wizard, "check_reader_dependencies"),
        patch.object(
            config_wizard, "get_reader_config_class", return_value=JiraRequirementReaderConfig
        ),
        patch.object(config_wizard, "prompt_model_fields", return_value=dict(answers)),
    ):
        result = config_wizard.configure_reader("jira", JIRA_READER_CLASS)

    assert "password" not in result
    assert result["username"] == "u"
    assert get_key(str(dotenv_path), "JIRA_PASSWORD") == "s3cret"


def test_configure_reader_moves_existing_credentials_and_reports_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    dotenv_path = tmp_path / ".env"
    monkeypatch.setattr(config_wizard, "DEFAULT_DOTENV_PATH", dotenv_path)
    existing = {
        "server_url": "https://jira.example.com",
        "auth_type": "token",
        "token": "old-pat",
    }
    with (
        patch.object(config_wizard, "check_reader_dependencies"),
        patch.object(
            config_wizard, "get_reader_config_class", return_value=JiraRequirementReaderConfig
        ),
        patch.object(config_wizard, "get_reader_config", return_value=dict(existing)),
        patch.object(config_wizard, "prompt_model_fields", return_value=dict(existing)),
    ):
        result = config_wizard.configure_reader("jira", JIRA_READER_CLASS, service_config=object())

    out = capsys.readouterr().out
    assert "token" not in result
    assert get_key(str(dotenv_path), "JIRA_BEARER_TOKEN") == "old-pat"
    assert (
        f"✓ Moved 'token' out of the configuration file into {dotenv_path} (JIRA_BEARER_TOKEN)"
        in out
    )
    assert "old-pat" not in out


def test_merge_with_defaults_succeeds_with_file_sourced_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("JIRA_PASSWORD_FILE", str(tmp_path / "missing"))
    result = config_wizard.merge_with_defaults(
        {"server_url": "https://jira.example.com", "auth_type": "basic", "username": "jira-user"},
        JiraRequirementReaderConfig,
    )
    assert result["server_url"] == "https://jira.example.com"
    assert "password" not in result
