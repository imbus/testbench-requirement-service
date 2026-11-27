"""Tests for the generic wizard field prompts."""

from typing import Literal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.utils.wizard import (
    dependency_matches,
    get_env_sourced_field_names,
    get_env_value,
    prompt_literal_field,
    prompt_model_fields,
    prompt_password_field,
)

_SELECT = "testbench_requirement_service.utils.wizard.questionary.select"
_TEXT = "testbench_requirement_service.utils.wizard.questionary.text"
_PASSWORD = "testbench_requirement_service.utils.wizard.questionary.password"


class _AuthModel(BaseModel):
    auth_type: Literal[
        "basic",
        "oauth2 2LO",
        "oauth2 2LO (service account)",
        "oauth2 3LO",
        "oauth2 3LO (user account)",
    ] = Field(
        "basic",
        json_schema_extra={
            "wizard_choices": [
                "basic",
                "oauth2 2LO (service account)",
                "oauth2 3LO (user account)",
            ],
        },
    )


class _PlainModel(BaseModel):
    mode: Literal["a", "b", "c"] = "a"


def _select_mock():
    select = MagicMock()
    select.return_value.ask.return_value = "basic"
    return select


def test_prompt_literal_field_uses_wizard_choices():
    field_info = _AuthModel.model_fields["auth_type"]
    field_type = field_info.annotation
    with patch(_SELECT, _select_mock()) as select:
        prompt_literal_field(field_type, "Auth type", "basic", field_info)
    choices = select.call_args.kwargs["choices"]
    assert choices == [
        "basic",
        "oauth2 2LO (service account)",
        "oauth2 3LO (user account)",
    ]


def test_prompt_literal_field_maps_short_alias_default_to_shown_choice():
    field_info = _AuthModel.model_fields["auth_type"]
    field_type = field_info.annotation
    with patch(_SELECT, _select_mock()) as select:
        prompt_literal_field(field_type, "Auth type", "oauth2 2LO", field_info)
    assert select.call_args.kwargs["default"] == "oauth2 2LO (service account)"


@pytest.mark.parametrize(
    "auth_type",
    [
        "oauth2 2LO",
        "oauth2 2LO (service account)",
        "oauth2 3LO",
        "oauth2 3LO (user account)",
    ],
)
@pytest.mark.parametrize("field_name", ["oauth2_client_id", "oauth2_client_secret"])
def test_oauth2_client_credentials_prompted_for_all_oauth2_auth_labels(field_name, auth_type):
    """The wizard must prompt for client credentials for every OAuth2 auth_type label.

    The select prompt returns the descriptive labels (e.g. "oauth2 2LO (service
    account)"), so depends_on must match those too — otherwise the credential
    prompts are skipped and config validation fails afterwards.
    """
    field_info = JiraRequirementReaderConfig.model_fields[field_name]
    assert dependency_matches(field_info, {"auth_type": auth_type})


@pytest.mark.parametrize("auth_type", ["oauth2 3LO", "oauth2 3LO (user account)"])
def test_oauth2_refresh_token_prompted_for_3lo_auth_labels(auth_type):
    field_info = JiraRequirementReaderConfig.model_fields["oauth2_refresh_token"]
    assert dependency_matches(field_info, {"auth_type": auth_type})


@pytest.mark.parametrize("field_name", ["oauth2_client_id", "oauth2_client_secret"])
def test_oauth2_client_credentials_not_prompted_for_basic_auth(field_name):
    field_info = JiraRequirementReaderConfig.model_fields[field_name]
    assert not dependency_matches(field_info, {"auth_type": "basic"})


def test_prompt_literal_field_without_wizard_choices_lists_all_literals():
    field_info = _PlainModel.model_fields["mode"]
    field_type = field_info.annotation
    with patch(_SELECT, _select_mock()) as select:
        prompt_literal_field(field_type, "Mode", "b", field_info)
    assert select.call_args.kwargs["choices"] == ["a", "b", "c"]
    assert select.call_args.kwargs["default"] == "b"


@pytest.fixture
def _no_jira_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("JIRA_PASSWORD", "JIRA_PASSWORD_FILE", "JIRA_USERNAME", "JIRA_USERNAME_FILE"):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.usefixtures("_no_jira_env")
def test_get_env_value_reports_file_variable_for_credential_field(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("JIRA_PASSWORD_FILE", "/run/secrets/does-not-need-to-exist")
    field_info = JiraRequirementReaderConfig.model_fields["password"]
    assert get_env_value(field_info) == (
        "JIRA_PASSWORD_FILE",
        "/run/secrets/does-not-need-to-exist",
    )


@pytest.mark.usefixtures("_no_jira_env")
def test_get_env_value_plain_variable_wins_over_file_variable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JIRA_PASSWORD", "plain")
    monkeypatch.setenv("JIRA_PASSWORD_FILE", "/run/secrets/pw")
    assert get_env_value(JiraRequirementReaderConfig.model_fields["password"]) == (
        "JIRA_PASSWORD",
        "plain",
    )


@pytest.mark.usefixtures("_no_jira_env")
def test_get_env_value_ignores_file_variable_for_non_credential_field(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("JIRA_USERNAME_FILE", "/run/secrets/user")
    assert get_env_value(JiraRequirementReaderConfig.model_fields["username"]) == (
        "JIRA_USERNAME",
        None,
    )


@pytest.mark.usefixtures("_no_jira_env")
def test_env_sourced_field_names_include_file_sourced_credentials(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("JIRA_PASSWORD_FILE", "/run/secrets/pw")
    assert "password" in get_env_sourced_field_names(JiraRequirementReaderConfig)


@pytest.mark.usefixtures("_no_jira_env")
def test_get_env_value_treats_empty_file_variable_as_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JIRA_PASSWORD_FILE", "")
    assert get_env_value(JiraRequirementReaderConfig.model_fields["password"]) == (
        "JIRA_PASSWORD",
        None,
    )


@pytest.mark.usefixtures("_no_jira_env")
def test_prompt_model_fields_completes_when_credential_comes_from_file_variable(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
):
    # The file does not exist: the wizard must never read it, only note that it is configured.
    monkeypatch.setenv("JIRA_PASSWORD_FILE", str(tmp_path / "missing"))
    text = MagicMock()
    # A second wizard round (validation failure) would exhaust the answers and raise.
    text.return_value.ask.side_effect = ["https://jira.example.com", "jira-user"]
    password = MagicMock()
    with patch(_SELECT, _select_mock()), patch(_TEXT, text), patch(_PASSWORD, password):
        result = prompt_model_fields(
            JiraRequirementReaderConfig,
            allowed_fields={"server_url", "auth_type", "username", "password"},
        )

    assert result == {
        "server_url": "https://jira.example.com",
        "auth_type": "basic",
        "username": "jira-user",
    }
    password.assert_not_called()
    out = capsys.readouterr().out
    assert "✓ Using JIRA_PASSWORD_FILE from environment for password" in out
    assert "validation failed" not in out


def _password_mock(answer):
    password = MagicMock()
    password.return_value.ask.return_value = answer
    return password


def test_prompt_password_field_keeps_existing_value_on_enter():
    password = _password_mock("")
    with patch(_PASSWORD, password):
        result = prompt_password_field("Password", "old-secret")

    assert result == "old-secret"
    assert password.call_args.args[0].endswith("(press Enter to keep the current value):")
    assert password.call_args.kwargs["default"] == ""


def test_prompt_password_field_replaces_existing_value_when_typed():
    with patch(_PASSWORD, _password_mock("new-secret")):
        assert prompt_password_field("Password", "old-secret") == "new-secret"


def test_prompt_password_field_without_default_prompts_plainly():
    password = _password_mock("x")
    with patch(_PASSWORD, password):
        result = prompt_password_field("Password", None)

    assert result == "x"
    assert password.call_args.args[0] == "Password:"
    assert password.call_args.kwargs["default"] == ""


def test_prompt_password_field_returns_none_when_cancelled():
    with patch(_PASSWORD, _password_mock(None)):
        assert prompt_password_field("Password", "old-secret") is None
