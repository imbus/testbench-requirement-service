"""Tests for the legacy .conf to TOML converter."""

from unittest.mock import patch

import pytest
import tomllib

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


def test_conf_field_keys_name_real_model_fields():
    """A key map entry that is not a model field is silently dropped by validation, so the
    legacy value is lost and the model default is written instead."""
    unknown = set(conf_converter.CONF_FIELD_KEYS) - set(
        conf_converter.JiraRequirementReaderConfig.model_fields
    )
    assert not unknown


def test_generate_jira_base_toml_converts_baseline_and_owner_fields():
    """The legacy ``baseline`` and ``owner`` entries name the Jira fields the reader reads
    them from, so they must land in ``baseline_field`` and ``owner_field``."""
    toml = conf_converter.generate_jira_base_toml(
        {"url": "http://jiraserver:8080/", "baseline": "customfield_101", "owner": "reporter"},
        auth_config=AUTH_CONFIG,
        credentials=CREDENTIALS,
    )
    assert 'baseline_field = "customfield_101"' in toml
    assert 'owner_field = "reporter"' in toml


def rendered_fields_of(toml_text):
    """The ``rendered_fields`` the generated TOML sets on the reader."""
    return tomllib.loads(toml_text)["testbench-requirement-service"]["reader_config"][
        "rendered_fields"
    ]


def test_generate_jira_base_toml_renders_the_description_when_the_legacy_flag_is_set():
    """The legacy wrapper's one render flag named the description, and the reader expresses
    the same thing as an entry in its list of fields to render."""
    toml = conf_converter.generate_jira_base_toml(
        {**CONF_DATA, "render_description": "true"},
        auth_config=AUTH_CONFIG,
        credentials=CREDENTIALS,
    )

    assert rendered_fields_of(toml) == ["description"]


@pytest.mark.parametrize("value", ["true", "TRUE", " True ", "yes", "on", "1"])
def test_the_render_description_flag_is_read_however_the_wrapper_spelled_it(value):
    """The legacy files are hand-written, so the flag turns up in every spelling of true."""
    toml = conf_converter.generate_jira_base_toml(
        {**CONF_DATA, "render_description": value}, auth_config=AUTH_CONFIG, credentials=CREDENTIALS
    )

    assert rendered_fields_of(toml) == ["description"]


@pytest.mark.parametrize("value", ["false", "no", "off", "0", ""])
def test_an_unset_render_description_flag_renders_nothing(value):
    """Carrying the description over on an unset flag would change what TestBench is
    served, so anything but a set flag leaves the model's empty default in place."""
    toml = conf_converter.generate_jira_base_toml(
        {**CONF_DATA, "render_description": value}, auth_config=AUTH_CONFIG, credentials=CREDENTIALS
    )

    assert rendered_fields_of(toml) == []


def test_a_conf_without_the_render_description_flag_renders_nothing():
    toml = conf_converter.generate_jira_base_toml(
        CONF_DATA, auth_config=AUTH_CONFIG, credentials=CREDENTIALS
    )

    assert rendered_fields_of(toml) == []


@pytest.mark.parametrize("value", ["true", "false"])
def test_the_render_description_flag_is_never_reported_as_unsupported(value, capsys):
    """The flag is read either way - an unset one is carried over as 'nothing to render',
    not left behind."""
    conf_converter.generate_jira_base_toml(
        {**CONF_DATA, "render_description": value}, auth_config=AUTH_CONFIG, credentials=CREDENTIALS
    )

    assert "render_description" not in capsys.readouterr().out


def excel_properties(data_dir, **overrides):
    """The legacy .properties entries of a minimal Excel wrapper, as a dict."""
    properties = {
        "requirementsDataPath": str(data_dir),
        "columnSeparator": ";",
        "arrayValueSeparator": ",",
        "baselineFileExtensions": "xlsx,xls",
        "requirement.id": "1",
        "requirement.version": "2",
        "requirement.name": "3",
    }
    return {**properties, **overrides}


def test_parse_rejects_a_malformed_conf_line_with_the_file_and_line(tmp_path):
    """`not enough values to unpack` named neither the file nor the line, so the user had
    nowhere to look."""
    legacy_path = tmp_path / "jira.conf"
    legacy_path.write_text("url: http://jiraserver:8080/\nthis line has no separator\n", "utf-8")

    with pytest.raises(conf_converter.ConfConversionError) as error:
        conf_converter.convert_legacy_config(legacy_path)

    assert "jira.conf line 2" in str(error.value)
    assert "this line has no separator" in str(error.value)


def test_parse_points_at_the_excel_type_for_a_properties_file_read_as_jira(tmp_path):
    """The `=` on the offending line is the giveaway, and the fix is a different --type."""
    legacy_path = tmp_path / "wrapper.txt"
    legacy_path.write_text(excel_properties_text(tmp_path.as_posix()), encoding="utf-8")

    with pytest.raises(conf_converter.ConfConversionError, match="--type excel"):
        conf_converter.convert_legacy_config(legacy_path, source_type="jira")


def test_parse_points_at_the_jira_type_for_a_conf_file_read_as_excel(tmp_path):
    legacy_path = write_jira_conf(tmp_path, name="wrapper.txt")

    with pytest.raises(conf_converter.ConfConversionError, match="--type jira"):
        conf_converter.convert_legacy_config(legacy_path, source_type="excel")


def test_parse_rejects_a_key_set_twice_to_different_values(tmp_path):
    """Silently keeping the last one migrates a setting the user never chose."""
    legacy_path = tmp_path / "jira.conf"
    legacy_path.write_text("url: http://one:8080/\nurl: http://two:8080/\n", encoding="utf-8")

    with pytest.raises(conf_converter.ConfConversionError) as error:
        conf_converter.convert_legacy_config(legacy_path)

    message = str(error.value)
    assert "url" in message
    assert "http://one:8080/" in message
    assert "http://two:8080/" in message


def test_parse_accepts_a_key_repeated_with_the_same_value(tmp_path):
    """A duplicate that says the same thing twice is not a conflict."""
    legacy_path = tmp_path / "jira.conf"
    legacy_path.write_text(f"{JIRA_CONF_TEXT}baseline: fixVersions\n", encoding="utf-8")

    with (
        patch.object(conf_converter, "prompt_service_credentials", return_value=CREDENTIALS),
        patch.object(conf_converter, "prompt_jira_auth_config", return_value=AUTH_CONFIG),
    ):
        toml = conf_converter.convert_legacy_config(legacy_path)

    assert 'baseline_field = "fixVersions"' in toml


def test_generate_jira_base_toml_names_the_entries_it_could_not_carry_over(capsys):
    """`JiraRequirementReaderConfig` ignores what it does not know, so a legacy setting
    with no equivalent disappears into a migration that reports success."""
    conf_data = {**CONF_DATA, "password": "secret", "wrapper.class": "com.example.Old"}

    conf_converter.generate_jira_base_toml(
        conf_data, auth_config=AUTH_CONFIG, credentials=CREDENTIALS
    )

    output = capsys.readouterr().out
    assert "password" in output
    assert "wrapper.class" in output


def test_generate_excel_base_toml_reports_an_unsupported_entry_and_still_converts(tmp_path, capsys):
    properties = excel_properties(tmp_path, **{"wrapper.someRetiredFlag": "true"})

    toml = conf_converter.generate_excel_base_toml(properties, CREDENTIALS)

    assert "wrapper.someRetiredFlag" in capsys.readouterr().out
    assert conf_converter.EXCEL_READER_CLASS in toml


def test_a_fully_supported_legacy_file_reports_nothing(tmp_path, capsys):
    """The composite `.properties` keys are read by the model's own `mode="before"`
    validators rather than by an alias, so a naive alias comparison would report every one
    of them as lost."""
    properties = excel_properties(
        tmp_path,
        **{
            "requirement.description.1": "4",
            "udf.count": "1",
            "udf.attr1.name": "risk",
            "udf.attr1.type": "STRING",
            "udf.attr1.column": "5",
        },
    )

    conf_converter.generate_excel_base_toml(properties, CREDENTIALS)

    assert "carried over" not in capsys.readouterr().out


def test_the_conf_keys_that_only_prefill_a_prompt_are_not_reported(capsys):
    """`jira.username` becomes the default of the username prompt, so it is carried over
    even though no model field reads it directly."""
    conf_converter.generate_jira_base_toml(
        {**CONF_DATA, "jira.username": "someone"},
        auth_config=AUTH_CONFIG,
        credentials=CREDENTIALS,
    )

    assert "jira.username" not in capsys.readouterr().out


def test_every_unsupported_key_is_listed_on_its_own_line(capsys):
    """A comma-separated run of keys is what makes a long list unreadable."""
    conf_data = {**CONF_DATA, "wrapper.retiredOne": "1", "wrapper.retiredTwo": "2"}

    conf_converter.generate_jira_base_toml(
        conf_data, auth_config=AUTH_CONFIG, credentials=CREDENTIALS
    )

    lines = capsys.readouterr().out.splitlines()
    assert [line for line in lines if "wrapper.retiredOne" in line] == ["  • wrapper.retiredOne"]
    assert [line for line in lines if "wrapper.retiredTwo" in line] == ["  • wrapper.retiredTwo"]


def test_the_unsupported_report_is_framed_so_it_stands_out(capsys):
    conf_converter.generate_jira_base_toml(
        {**CONF_DATA, "wrapper.retired": "1"}, auth_config=AUTH_CONFIG, credentials=CREDENTIALS
    )

    assert "═" * 60 in capsys.readouterr().out
