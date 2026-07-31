"""Tests for the generic wizard field prompts."""

from typing import Literal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.utils.wizard import dependency_matches, prompt_literal_field

_SELECT = "testbench_requirement_service.utils.wizard.questionary.select"


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
