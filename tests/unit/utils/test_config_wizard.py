"""Tests for the CLI configuration wizard helpers."""

from unittest.mock import patch

from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.utils import config_wizard

JIRA_READER_CLASS = "testbench_requirement_service.readers.JiraRequirementReader"


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
        patch.object(config_wizard, "store_client_secret_in_env"),
        patch.object(config_wizard, "merge_with_defaults", side_effect=lambda config, _: config),
    ):
        config_wizard.configure_reader("jira", JIRA_READER_CLASS)

    oauth_wizard.assert_called_once()
    passed_config = oauth_wizard.call_args.args[0]
    assert passed_config["server_url"] == "https://jira.example.com"
    assert passed_config["oauth2_client_id"] == "client-id"
    seed_token.assert_called_once_with("refresh-token")
