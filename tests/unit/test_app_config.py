from pathlib import Path

import pytest

import testbench_requirement_service.config as service_config
from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig

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


@pytest.fixture
def jira_app_config() -> service_config.AppConfig:
    config = service_config.AppConfig.__new__(service_config.AppConfig)
    config.READER_CLASS = "testbench_requirement_service.readers.JiraRequirementReader"
    return config


@pytest.mark.parametrize("auth_type", ["oauth2 3LO", "oauth2 3LO (user account)"])
def test_startup_prompts_for_missing_jira_oauth2_refresh_token(
    jira_app_config: service_config.AppConfig, monkeypatch: pytest.MonkeyPatch, auth_type: str
) -> None:
    reader_config = {"auth_type": auth_type}
    monkeypatch.setattr(service_config, "has_cached_refresh_token", lambda: False)
    monkeypatch.setattr(
        service_config, "run_jira_oauth_wizard", lambda _reader_config: "refresh-token"
    )
    monkeypatch.setattr(service_config, "seed_oauth2_refresh_token", lambda token: None)

    jira_app_config._prompt_for_missing_jira_oauth2_refresh_token(reader_config)

    assert reader_config["oauth2_refresh_token"] == "refresh-token"


def _inline_jira_app_config(jira_app_config, reader_config: dict):
    jira_app_config.READER_CONFIG_PATH = None
    jira_app_config.CONFIG_PATH = Path("config.toml")
    jira_app_config._reader_config_inline = reader_config
    return jira_app_config


def test_start_refuses_unreadable_credential_file_naming_only_the_variable(
    jira_app_config, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
):
    monkeypatch.delenv("JIRA_PASSWORD", raising=False)
    monkeypatch.setenv("JIRA_PASSWORD_FILE", str(tmp_path / "missing"))
    monkeypatch.setattr(
        service_config, "get_reader_config_class", lambda _cls: JiraRequirementReaderConfig
    )
    app_config = _inline_jira_app_config(
        jira_app_config,
        {"server_url": "https://jira.example.com", "auth_type": "basic", "username": "u"},
    )

    with pytest.raises(SystemExit) as excinfo:
        app_config._validate_reader_config()

    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "Configuration Error: JIRA_PASSWORD_FILE points to" in out


def test_start_uses_credential_file_over_config_value(
    jira_app_config, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.delenv("JIRA_PASSWORD", raising=False)
    (tmp_path / "pw").write_text("file-secret\n")
    monkeypatch.setenv("JIRA_PASSWORD_FILE", str(tmp_path / "pw"))
    monkeypatch.setattr(
        service_config, "get_reader_config_class", lambda _cls: JiraRequirementReaderConfig
    )
    app_config = _inline_jira_app_config(
        jira_app_config,
        {
            "server_url": "https://jira.example.com",
            "auth_type": "basic",
            "username": "u",
            "password": "config-secret",
        },
    )

    reader_config = app_config._validate_reader_config()

    assert reader_config.password == "file-secret"
