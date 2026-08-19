from pathlib import Path
from typing import Any

import click
import tomli_w
from pydantic import BaseModel, ValidationError

from testbench_requirement_service.models.config import RequirementServiceConfig
from testbench_requirement_service.readers.excel.config import ExcelRequirementReaderConfig
from testbench_requirement_service.readers.jira.config import (
    AUTH_OAUTH2_3LO,
    JiraRequirementReaderConfig,
)
from testbench_requirement_service.readers.jira.jira_oauth import (
    has_cached_refresh_token,
    seed_oauth2_refresh_token,
)
from testbench_requirement_service.utils.auth import create_credentials
from testbench_requirement_service.utils.config import CONFIG_PREFIX
from testbench_requirement_service.utils.config_wizard import (
    merge_with_defaults,
    run_jira_oauth_wizard,
    setup_authentication,
    store_client_secret_in_env,
)
from testbench_requirement_service.utils.dependencies import check_reader_dependencies
from testbench_requirement_service.utils.wizard import (
    SCHEMA_KEYS,
    get_field_extra,
    prompt_model_fields,
)

EXCEL_READER_CLASS = "testbench_requirement_service.readers.ExcelRequirementReader"
JIRA_READER_CLASS = "testbench_requirement_service.readers.JiraRequirementReader"

#: Which legacy wrapper format each file extension stands for.
LEGACY_SOURCE_TYPES: dict[str, str] = {".conf": "jira", ".properties": "excel"}


class ConfConversionError(Exception):
    """Exception raised for errors in the configuration conversion process."""


AUTH_TYPE_FIELD = "auth_type"
SERVER_URL_FIELD = "server_url"

CONF_FIELD_KEYS: dict[str, tuple[str, ...]] = {
    SERVER_URL_FIELD: ("url",),
    "baseline": ("baseline",),
    "baseline_jql": ("baseline_jql",),
    "current_baseline_jql": ("current_baseline_jql",),
    "owner": ("owner",),
}

CONF_DEFAULT_KEYS: dict[str, tuple[str, ...]] = {
    SERVER_URL_FIELD: CONF_FIELD_KEYS[SERVER_URL_FIELD],
    "username": ("jira.username", "jira.user", "jira.login"),
}


def prompt_field_names() -> set[str]:
    """Return the server URL, ``auth_type`` and every field whose ``depends_on`` names it.

    Which of the dependent fields are actually asked for is decided by the wizard at
    runtime from the chosen ``auth_type``, so this only has to bound the prompts to the
    connection and authentication part of the model — SSL and timeout settings stay out.

    ``server_url`` belongs here even though the legacy .conf supplies it: the wizard
    validates its answers against the whole ``JiraRequirementReaderConfig``, in which it
    is the one required field. Leaving it out makes that validation fail with
    ``server_url: Field required`` and the wizard restart forever.
    """
    names = {SERVER_URL_FIELD, AUTH_TYPE_FIELD}
    for field_name, field_info in JiraRequirementReaderConfig.model_fields.items():
        dependency = get_field_extra(field_info).get(SCHEMA_KEYS["DEPENDS_ON"])
        if isinstance(dependency, dict) and AUTH_TYPE_FIELD in dependency:
            names.add(field_name)
    return names


def prompt_service_credentials() -> tuple[str, str] | None:
    """Ask for the service login and derive a fresh password hash and salt from it.

    The legacy wrappers know nothing about these credentials - they protect the requirement
    service's own HTTP API, not the requirement source behind it - so there is nothing to carry
    over from the file being converted. Asking here is what makes the generated config
    usable as written: the hash and salt are renewed from the password entered now.

    Returns:
        The ``(password_hash, salt)`` pair to write, or ``None`` when the user aborts.
    """
    click.echo("\n🔐 Service Credentials\n")
    click.echo("These log in to the requirement service itself, not to the requirement source.\n")

    username, password = setup_authentication()
    if username is None or password is None:
        return None

    return create_credentials(username, password)


def fields_from_conf(
    conf_data: dict[str, Any], key_map: dict[str, tuple[str, ...]]
) -> dict[str, Any]:
    """Collect the legacy entries named by *key_map*, keyed by model field name.

    The first key present for a field wins, and absent or empty entries are skipped so
    the model's own default applies instead of an empty string.
    """
    fields: dict[str, Any] = {}
    for field_name, conf_keys in key_map.items():
        for conf_key in conf_keys:
            value = conf_data.get(conf_key)
            if value not in (None, ""):
                fields[field_name] = value
                break
    return fields


def conf_defaults(conf_data: dict[str, Any]) -> dict[str, Any]:
    """Translate legacy .conf entries into prompt defaults keyed by model field name."""
    return fields_from_conf(conf_data, CONF_DEFAULT_KEYS)


def prompt_jira_auth_config(conf_data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Ask how to authenticate against Jira and collect the credentials that implies.

    Delegates the prompting to the config wizard's ``prompt_model_fields`` restricted
    to the authentication fields of ``JiraRequirementReaderConfig``, so the auth types
    offered, the dependent credentials, masked input, environment-variable handling
    and validation all behave exactly as in ``testbench-requirement-service configure``.
    The Jira server URL is part of the prompts because the credentials are validated
    against it; it is pre-filled from the legacy .conf.

    Args:
        conf_data (dict | None): Parsed legacy .conf data used for prompt defaults.

    Returns:
        The collected connection and auth fields, or ``None`` when the user aborts or
        the jira extra is not installed.
    """
    conf_data = conf_data or {}

    try:
        check_reader_dependencies("jira", raise_on_missing=True)
    except ImportError as e:
        click.echo(f"\n{e}\n")
        return None

    auth_config = prompt_model_fields(
        JiraRequirementReaderConfig,
        existing_config=conf_defaults(conf_data),
        section_label="Jira Authentication",
        allowed_fields=prompt_field_names(),
    )
    if auth_config is None:
        return None

    finalize_jira_oauth2(auth_config)
    return auth_config


def finalize_jira_oauth2(auth_config: dict[str, Any]) -> None:
    """Apply the config wizard's post-prompt OAuth2 handling to *auth_config*.

    For the 3LO flow the refresh token is seeded into the token cache (obtaining one
    through the OAuth wizard when neither the prompt nor the cache provided it), and
    the OAuth2 client secret is moved into ``.env`` instead of the generated TOML.
    Mutates *auth_config* in place.
    """
    if str(auth_config.get(AUTH_TYPE_FIELD) or "").startswith(AUTH_OAUTH2_3LO):
        # The model declares oauth2_refresh_token as exclude=True: it belongs in the
        # token cache, not in a config file.
        refresh_token = auth_config.pop("oauth2_refresh_token", None)
        if not (isinstance(refresh_token, str) and refresh_token) and (
            not has_cached_refresh_token()
        ):
            refresh_token = run_jira_oauth_wizard(auth_config)
        if isinstance(refresh_token, str) and refresh_token:
            seed_oauth2_refresh_token(refresh_token)

    store_client_secret_in_env(auth_config)


def parse_conf_file(file_path: Path) -> dict[str, Any]:
    """
    Parses a configuration file and returns its contents as a dictionary.

    Args:
        file_path (Path): The path to the configuration file.
    """
    config: dict[str, Any] = {}

    try:
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        with file_path.open("r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split(":", 1)
                    config[key.strip()] = value.strip().removeprefix('"').removesuffix('"')
    except Exception as e:
        raise ConfConversionError(f"Failed to parse configuration file: {e}") from e

    return config


def _describe_validation_errors(error: ValidationError) -> str:
    """Render a ValidationError as a single ``field: message`` line per problem."""
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or '<config>'}: {item['msg']}"
        for item in error.errors()
    )


def build_reader_config(
    config_class: type[BaseModel], legacy_config: dict[str, Any], source: str
) -> dict[str, Any]:
    """Validate *legacy_config* against *config_class* and return it as a TOML-ready dict.

    The reader config models read the legacy key names themselves - through the
    ``AliasChoices`` on each field and, for Excel, the ``mode="before"`` normalization that
    reassembles control fields, transitions and UDFs. Validating here is therefore the whole
    conversion: values arrive typed instead of as property strings, unset options fall back to
    the model's documented defaults via ``merge_with_defaults`` rather than to a second set of
    defaults kept in this module, and anything the reader would reject at startup is reported
    now, while the .conf file being converted is still on screen.
    """
    try:
        return merge_with_defaults(legacy_config, config_class)
    except ValidationError as e:
        raise ConfConversionError(
            f"Cannot convert {source}: {_describe_validation_errors(e)}"
        ) from e


def build_service_toml(
    reader_class: str, reader_config: dict[str, Any], credentials: tuple[str, str]
) -> str:
    """Wrap a validated reader config in a ``RequirementServiceConfig`` and dump it as TOML.

    Host, port, logging and server settings come from the service model's defaults, so the
    generated file matches what ``testbench-requirement-service configure`` would write. The
    service credentials are asked for unless a ``(password_hash, salt)`` pair is supplied.

    Raises:
        ConfConversionError: When the interactive credentials setup is cancelled.
    """

    password_hash, salt = credentials
    service_config = RequirementServiceConfig(
        reader_class=reader_class,
        reader_config=reader_config,
        password_hash=password_hash,
        salt=salt,
    )
    return tomli_w.dumps({CONFIG_PREFIX: service_config.model_dump(mode="json", exclude_none=True)})


def parse_properties_file(file_path: Path) -> dict[str, Any]:
    """
    Parses a .properties configuration file and returns its contents as a dictionary.

    Args:
        file_path (Path): The path to the .properties configuration file.
    """
    config: dict[str, Any] = {}

    try:
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        with file_path.open("r", encoding="utf-8") as file:
            for line in file:
                raw_line = line.strip()
                if raw_line and not raw_line.startswith(("#", "!")):
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
    except Exception as e:
        raise ConfConversionError(f"Failed to parse configuration file: {e}") from e

    return config


def generate_jira_base_toml(
    conf_data: dict[str, Any],
    auth_config: dict[str, Any] | None = None,
    credentials: tuple[str, str] | None = None,
) -> str:
    """
    Generates a TOML string for the Jira base configuration.

    Args:
        conf_data (dict): The configuration data.
        auth_config (dict | None): Authentication fields to write; a ``server_url``
            in it takes precedence over the one from the .conf. When omitted, the
            authentication type and the credentials it needs are asked for interactively.
        credentials (tuple | None): The service ``(password_hash, salt)`` to write. When
            omitted, the service login is asked for and the pair is generated from it.

    Raises:
        ConfConversionError: When the interactive authentication or credentials setup is
            cancelled, or when the result is not a valid ``JiraRequirementReaderConfig``.
    """
    if credentials is None:
        credentials = prompt_service_credentials()
        if credentials is None:
            raise ConfConversionError("Service credentials setup was cancelled")

    if auth_config is None:
        auth_config = prompt_jira_auth_config(conf_data)
        if auth_config is None:
            raise ConfConversionError("Jira authentication setup was cancelled")

    reader_config = build_reader_config(
        JiraRequirementReaderConfig,
        {**fields_from_conf(conf_data, CONF_FIELD_KEYS), **auth_config},
        "the Jira .conf file",
    )
    return build_service_toml(JIRA_READER_CLASS, reader_config, credentials)


def generate_excel_base_toml(
    properties: dict[str, Any], credentials: tuple[str, str] | None = None
) -> str:
    """
    Generates a TOML string for the Excel base configuration.

    Args:
        properties (dict): The parsed legacy `.properties` data, in its own key spelling.
        credentials (tuple | None): The service ``(password_hash, salt)`` to write. When
            omitted, the service login is asked for and the pair is generated from it.

    Raises:
        ConfConversionError: When the interactive credentials setup is cancelled, or when the
            result is not a valid ``ExcelRequirementReaderConfig``.
    """
    if credentials is None:
        credentials = prompt_service_credentials()
        if credentials is None:
            raise ConfConversionError("Service credentials setup was cancelled")

    reader_config = build_reader_config(
        ExcelRequirementReaderConfig, properties, "the Excel .properties file"
    )
    return build_service_toml(EXCEL_READER_CLASS, reader_config, credentials)


def detect_source_type(legacy_path: Path) -> str | None:
    """Return the legacy wrapper format implied by *legacy_path*'s extension, if any."""
    return LEGACY_SOURCE_TYPES.get(legacy_path.suffix.lower())


def convert_legacy_config(legacy_path: Path, source_type: str | None = None) -> str:
    """Convert a legacy wrapper configuration file into a service TOML document.

    Pairs each legacy format with the parser that reads its key spelling and the generator
    that validates it against the matching reader model, so callers only supply the file.

    Args:
        legacy_path (Path): The legacy ``.conf`` or ``.properties`` file to convert.
        source_type (str | None): ``"jira"`` or ``"excel"``. Detected from the file
            extension when omitted.

    Raises:
        ConfConversionError: When the format cannot be detected, when the file cannot be
            parsed, when an interactive setup step is cancelled, or when the result is not
            a valid reader configuration.
    """
    source_type = source_type or detect_source_type(legacy_path)

    if source_type == "jira":
        return generate_jira_base_toml(parse_conf_file(legacy_path))
    if source_type == "excel":
        return generate_excel_base_toml(parse_properties_file(legacy_path))

    known = ", ".join(sorted(set(LEGACY_SOURCE_TYPES.values())))
    raise ConfConversionError(
        f"Cannot tell the legacy format of '{legacy_path.name}' from its extension. "
        f"Name the source type explicitly ({known})."
    )
