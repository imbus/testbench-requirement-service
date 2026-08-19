"""Tests for the legacy .conf to TOML converter."""

from unittest.mock import patch

import pytest

from testbench_requirement_service.utils import conf_converter

CONF_DATA = {
    "url": "http://jiraserver:8080/",
    "baseline": "fixVersions",
    "owner": "assignee",
}


def test_prompt_fields_cover_every_required_model_field():
    """The wizard validates its answers against the whole model, so a required field that
    is never prompted for makes the wizard fail and re-run forever."""
    required = {
        name
        for name, field in conf_converter.JiraRequirementReaderConfig.model_fields.items()
        if field.is_required()
    }
    assert required <= conf_converter.prompt_field_names()


def test_prompt_jira_auth_config_prefills_server_url_from_conf():
    """The .conf's ``url`` is offered as the default for the prompted server URL."""
    with (
        patch.object(conf_converter, "check_reader_dependencies"),
        patch.object(conf_converter, "prompt_model_fields", return_value={}) as prompt,
        patch.object(conf_converter, "store_client_secret_in_env"),
    ):
        conf_converter.prompt_jira_auth_config(CONF_DATA)

    existing = prompt.call_args.kwargs["existing_config"]
    assert existing[conf_converter.SERVER_URL_FIELD] == "http://jiraserver:8080/"
    assert conf_converter.SERVER_URL_FIELD in prompt.call_args.kwargs["allowed_fields"]


def test_generate_jira_base_toml_writes_prompted_server_url():
    """A server URL edited in the wizard wins over the one read from the .conf."""
    auth_config = {
        "server_url": "https://jira.example.com",
        "auth_type": "basic",
        "username": "user",
        "password": "secret",
    }
    toml = conf_converter.generate_jira_base_toml(
        CONF_DATA, auth_config=auth_config, credentials=("hash", "salt")
    )
    assert 'server_url = "https://jira.example.com"' in toml


def test_generate_jira_base_toml_falls_back_to_conf_server_url():
    """Without a prompted server URL the .conf's ``url`` is converted."""
    toml = conf_converter.generate_jira_base_toml(
        CONF_DATA,
        auth_config={"auth_type": "basic", "username": "user", "password": "secret"},
        credentials=("hash", "salt"),
    )
    assert 'server_url = "http://jiraserver:8080/"' in toml


AUTH_CONFIG = {"auth_type": "basic", "username": "user", "password": "secret"}
CREDENTIALS = ("hash", "salt")

JIRA_CONF_TEXT = """# legacy Jira wrapper configuration
url: http://jiraserver:8080/
baseline: fixVersions
owner: assignee
"""


def excel_properties_text(data_dir: object) -> str:
    """A minimal legacy .properties file, in the key spelling the wrappers used."""
    return (
        f"requirementsDataPath={data_dir}\n"
        "columnSeparator=;\n"
        "arrayValueSeparator=,\n"
        "baselineFileExtensions=xlsx,xls\n"
        "requirement.id=1\n"
        "requirement.version=2\n"
        "requirement.name=3\n"
    )


def write_jira_conf(tmp_path, name="jira.conf"):
    legacy_path = tmp_path / name
    legacy_path.write_text(JIRA_CONF_TEXT, encoding="utf-8")
    return legacy_path


def test_convert_legacy_config_converts_a_conf_file_as_jira(tmp_path):
    """A .conf file is the legacy Jira wrapper format, so it converts to a Jira reader."""
    legacy_path = write_jira_conf(tmp_path)

    with (
        patch.object(conf_converter, "prompt_service_credentials", return_value=CREDENTIALS),
        patch.object(conf_converter, "prompt_jira_auth_config", return_value=AUTH_CONFIG),
    ):
        toml = conf_converter.convert_legacy_config(legacy_path)

    assert conf_converter.JIRA_READER_CLASS in toml
    assert 'server_url = "http://jiraserver:8080/"' in toml


def test_convert_legacy_config_converts_a_properties_file_as_excel(tmp_path):
    """A .properties file is the legacy Excel wrapper format, so it converts to an Excel reader."""
    legacy_path = tmp_path / "genericexcel.properties"
    legacy_path.write_text(excel_properties_text(tmp_path.as_posix()), encoding="utf-8")

    with patch.object(conf_converter, "prompt_service_credentials", return_value=CREDENTIALS):
        toml = conf_converter.convert_legacy_config(legacy_path)

    assert conf_converter.EXCEL_READER_CLASS in toml
    assert 'columnSeparator = ";"' in toml


def test_convert_legacy_config_honours_an_explicit_source_type(tmp_path):
    """An unrecognised extension converts once the source type is named."""
    legacy_path = write_jira_conf(tmp_path, name="wrapper.txt")

    with (
        patch.object(conf_converter, "prompt_service_credentials", return_value=CREDENTIALS),
        patch.object(conf_converter, "prompt_jira_auth_config", return_value=AUTH_CONFIG),
    ):
        toml = conf_converter.convert_legacy_config(legacy_path, source_type="jira")

    assert conf_converter.JIRA_READER_CLASS in toml


def test_convert_legacy_config_rejects_an_undetectable_extension(tmp_path):
    """Guessing the format would silently produce the wrong reader, so it asks instead."""
    legacy_path = write_jira_conf(tmp_path, name="wrapper.txt")

    with pytest.raises(conf_converter.ConfConversionError, match="source type"):
        conf_converter.convert_legacy_config(legacy_path)
