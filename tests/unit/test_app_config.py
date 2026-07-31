import pytest

import testbench_requirement_service.config as service_config


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
