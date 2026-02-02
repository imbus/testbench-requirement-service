import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypedDict, get_args, get_origin

import click
import questionary
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

# Constants for json_schema_extra keys
SCHEMA_KEYS = {
    "ENV_VAR": "env_var",
    "DEPENDS_ON": "depends_on",
    "SENSITIVE": "sensitive",
    "SKIP_IF_WIZARD": "skip_if_wizard",
    "PROMPT_AS_LIST": "prompt_as_list",
    "PROMPT_AS_DICT": "prompt_as_dict",
    "ITEM_LABEL": "item_label",
    "KEY_LABEL": "key_label",
    "LABEL": "label",
    "REQUIRED": "required",
}


class FieldPromptOptions(TypedDict, total=False):
    label: str
    default: Any
    skip: bool
    validate: Callable[[Any], tuple[bool, str | None]]
    required: bool


def get_field_extra(field_info: FieldInfo) -> dict[str, Any]:
    """Extract json_schema_extra dict from field info."""
    extra = field_info.json_schema_extra
    return extra if isinstance(extra, dict) else {}


def is_basemodel_subclass(cls: Any) -> bool:
    """Check if a type is a Pydantic BaseModel subclass."""
    try:
        return isinstance(cls, type) and issubclass(cls, BaseModel)
    except TypeError:
        return False


def normalize_answer(answer: Any) -> Any:
    """Convert blank string answers to None for optional fields."""
    if isinstance(answer, str) and not answer.strip():
        return None
    return answer


def dependency_matches(
    field_info: FieldInfo,
    provided_values: dict[str, Any] | None,
    fallback_values: dict[str, Any] | None = None,
) -> bool:
    """Check if a field's dependency condition is met based on provided values."""
    extra = get_field_extra(field_info)
    dependency = extra.get(SCHEMA_KEYS["DEPENDS_ON"])
    if not dependency:
        return True

    field = dependency.get("field")
    expected = dependency.get("value")
    if not field:
        return True

    actual = (provided_values or {}).get(field)
    if actual is None and fallback_values is not None:
        actual = fallback_values.get(field)

    if isinstance(expected, (list, tuple, set)):
        return bool(actual in expected)
    return bool(actual == expected)


def parse_value_from_input(value_str: str, field_type: type) -> Any:  # noqa: PLR0911
    """Parse user input string to the appropriate Python type."""
    if not value_str:
        return None

    origin = get_origin(field_type)

    # Handle Path
    if field_type is Path or (origin is type and field_type == Path):
        return Path(value_str)

    # Handle list types
    if origin is list:
        args = get_args(field_type)
        if args and args[0] is str:
            # Comma-separated string list
            return [item.strip() for item in value_str.split(",") if item.strip()]
        if args and args[0] is int:
            # Comma-separated int list
            return [int(item.strip()) for item in value_str.split(",") if item.strip()]

    # Handle bool
    if field_type is bool:
        return value_str.lower() in ("true", "yes", "1", "y")

    # Handle int
    if field_type is int:
        return int(value_str)

    # Handle Literal (should use select, but fallback to string)
    if origin is Literal:
        return value_str

    # Default to string
    return value_str


def get_actual_type(field_type: type) -> tuple[type, type | None]:
    """Extract the actual type from Optional/Union types.

    Args:
        field_type: The field type annotation

    Returns:
        Tuple of (actual_type, origin) where origin is the generic origin (list, Literal, etc.)
    """
    origin = get_origin(field_type)

    # Handle Optional types (Union[X, None] or X | None)
    args = get_args(field_type)
    if args and type(None) in args:
        # Extract the non-None type
        non_none_types = [arg for arg in args if arg is not type(None)]
        if non_none_types:
            field_type = non_none_types[0]
            origin = get_origin(field_type)

    return field_type, origin


def prompt_with_validation(  # noqa: PLR0913
    prompt_text: str,
    default: str,
    field_type: type,
    field_name: str,
    is_required: bool,
    max_retries: int = 3,
) -> tuple[Any | None, bool]:
    """Prompt for input with validation and retry logic.

    Args:
        prompt_text: The prompt text to display
        default: Default value to show
        field_type: Expected Python type for validation
        field_name: Name of the field (for error messages)
        is_required: Whether the field is required
        max_retries: Maximum number of retry attempts

    Returns:
        Tuple of (parsed value or None, cancelled flag)
    """
    for attempt in range(max_retries):
        answer = questionary.text(prompt_text, default=default).ask()

        if answer is None:  # User cancelled
            return None, True

        if not answer and not is_required:
            return None, False

        if not answer and is_required:
            click.echo("❌ This field is required")
            continue

        # Try to parse the value
        try:
            parsed_value = parse_value_from_input(answer, field_type)
            return parsed_value, False
        except (ValueError, TypeError) as e:
            remaining = max_retries - attempt - 1
            if remaining > 0:
                click.echo(f"❌ Invalid value: {e}. {remaining} attempt(s) remaining.")
            else:
                click.echo(f"❌ Invalid value: {e}. Maximum retries reached.")

    return None, False


def is_sensitive_field(field_name: str, field_info: FieldInfo) -> bool:
    """Check if a field contains sensitive data like passwords or tokens."""
    sensitive_keywords = {"password", "token", "secret", "key_cert", "api_token"}
    if any(keyword in field_name.lower() for keyword in sensitive_keywords):
        return True
    schema_extra = get_field_extra(field_info)
    return bool(schema_extra.get(SCHEMA_KEYS["SENSITIVE"], False))


def get_field_default_value(field_info: FieldInfo, existing_value: Any = None) -> Any:
    """Get default value for a field, preferring existing config value."""
    if existing_value is not None:
        return existing_value
    if field_info.default is not None and field_info.default is not PydanticUndefined:
        return field_info.default
    if field_info.default_factory is not None and callable(field_info.default_factory):
        factory_result = field_info.default_factory()  # type: ignore[call-arg]
        if isinstance(factory_result, (list, dict)):
            return None
        return factory_result
    return None


def should_skip_field(  # noqa: PLR0913
    field_name: str,
    field_info: FieldInfo,
    config_dict: dict[str, Any],
    existing: dict[str, Any],
    allowed_fields: set[str] | None,
    skip_fields: set[str],
    field_overrides: dict[str, FieldPromptOptions],
) -> bool:
    """Check if a field should be skipped in the wizard."""
    if allowed_fields and field_name not in allowed_fields:
        return True
    if field_name in skip_fields:
        return True

    overrides = field_overrides.get(field_name, {})
    schema_extra = get_field_extra(field_info)

    if overrides.get("skip") or schema_extra.get(SCHEMA_KEYS["SKIP_IF_WIZARD"]):
        return True

    return bool(not dependency_matches(field_info, config_dict, existing))


def get_field_description(
    field_name: str, field_info: FieldInfo, field_overrides: dict[str, FieldPromptOptions]
) -> str:
    """Get the display description for a field."""
    overrides = field_overrides.get(field_name, {})
    schema_extra = get_field_extra(field_info)

    return (
        overrides.get("label")
        or schema_extra.get(SCHEMA_KEYS["LABEL"])
        or field_info.description
        or field_name.replace("_", " ").title()
    )


def get_existing_value(field_name: str, field_info: FieldInfo, existing: dict[str, Any]) -> Any:
    """Get existing value for a field, checking both field name and alias."""
    existing_value = existing.get(field_name)
    if existing_value is None and field_info.alias:
        existing_value = existing.get(field_info.alias)
    return existing_value


def get_env_value(field_info: FieldInfo) -> tuple[str | None, Any]:
    """Get environment variable name and value if configured."""
    schema_extra = get_field_extra(field_info)
    env_var = schema_extra.get(SCHEMA_KEYS["ENV_VAR"])
    if env_var:
        env_value = os.getenv(env_var) or None
        return env_var, env_value
    return None, None


def get_default_value(
    field_info: FieldInfo,
    existing_value: Any,
    env_value: Any,
    field_overrides: dict[str, FieldPromptOptions],
    field_name: str,
) -> Any:
    """Determine the default value for a field from multiple sources."""
    default_value = existing_value
    if default_value is None and env_value:
        default_value = env_value
    if default_value is None and "default" in field_overrides.get(field_name, {}):
        default_value = field_overrides[field_name]["default"]
    if default_value is None:
        default_value = get_field_default_value(field_info, existing_value)
    return default_value


def format_default_display(default_value: Any) -> str:
    """Format default value for display in prompts."""
    if default_value is None or default_value is PydanticUndefined:
        return ""
    if isinstance(default_value, Path):
        return str(default_value)
    if isinstance(default_value, list) and all(isinstance(x, str) for x in default_value):
        return ",".join(default_value)
    if isinstance(default_value, bool):
        return str(default_value).lower()
    return str(default_value)


def is_field_required(
    field_info: FieldInfo, field_overrides: dict[str, FieldPromptOptions], field_name: str
) -> bool:
    """Determine if a field is required."""
    overrides = field_overrides.get(field_name, {})
    schema_extra = get_field_extra(field_info)

    if "required" in overrides:
        return bool(overrides["required"])
    if SCHEMA_KEYS["REQUIRED"] in schema_extra:
        return bool(schema_extra[SCHEMA_KEYS["REQUIRED"]])
    return field_info.is_required()


def prompt_list_of_models(
    field_name: str,
    item_class: type[BaseModel],
    item_label: str,
    existing_items: list[dict] | None = None,
) -> list[dict] | None:
    """Prompt user to configure a list of BaseModel items.

    Args:
        field_name: Name of the field being configured
        item_class: BaseModel class for list items
        item_label: Display label for items (e.g., "User Defined Attribute")
        existing_items: Existing list of items from config

    Returns:
        List of dictionaries representing configured items, or None if cancelled
    """
    default_count = str(len(existing_items)) if existing_items else "0"
    count_prompt = f"How many {item_label}s do you want to configure?"
    count_str = questionary.text(count_prompt, default=default_count).ask()

    if count_str is None:
        click.echo("\n❌ Configuration cancelled by user")
        return None

    try:
        count = int(count_str)
    except ValueError:
        click.echo(f"❌ Invalid number: {count_str}")
        return None

    if count < 0:
        click.echo("❌ Number must be non-negative")
        return None

    items = []
    for i in range(count):
        click.echo(f"\n--- {item_label} {i + 1} of {count} ---")
        existing_item = existing_items[i] if existing_items and i < len(existing_items) else None
        item_config = prompt_model_fields(
            item_class, existing_config=existing_item, section_label=None
        )
        if item_config is None:
            return None
        items.append(item_config)

    return items


def prompt_dict_of_models(  # noqa: PLR0911
    field_name: str,
    value_class: type[BaseModel],
    item_label: str,
    key_label: str = "Key",
    existing_dict: dict[str, dict] | None = None,
) -> dict[str, dict] | None:
    """Prompt user to configure a dictionary of BaseModel items.

    Args:
        field_name: Name of the field being configured
        value_class: BaseModel class for dict values
        item_label: Display label for items (e.g., "Project Configuration")
        key_label: Display label for keys (e.g., "Project Name")
        existing_dict: Existing dictionary from config

    Returns:
        Dictionary mapping keys to configured items, or None if cancelled
    """
    default_count = str(len(existing_dict)) if existing_dict else "0"
    count_prompt = f"How many {item_label}s do you want to configure?"
    count_str = questionary.text(count_prompt, default=default_count).ask()

    if count_str is None:
        click.echo("\n❌ Configuration cancelled by user")
        return None

    try:
        count = int(count_str)
    except ValueError:
        click.echo(f"❌ Invalid number: {count_str}")
        return None

    if count < 0:
        click.echo("❌ Number must be non-negative")
        return None

    result_dict = {}
    existing_keys = list(existing_dict.keys()) if existing_dict else []

    for i in range(count):
        # Prompt for key
        default_key = existing_keys[i] if i < len(existing_keys) else ""
        key = questionary.text(f"\n{key_label} {i + 1}:", default=default_key).ask()

        if key is None:
            click.echo("\n❌ Configuration cancelled by user")
            return None

        if not key.strip():
            click.echo("❌ Key cannot be empty")
            return None

        key = key.strip()

        if key in result_dict:
            click.echo(f"❌ Duplicate key '{key}' - skipping")
            continue

        # Prompt for value
        click.echo(f"--- Configure {item_label} for '{key}' ---")
        existing_value = existing_dict.get(key) if existing_dict else None
        value_config = prompt_model_fields(
            value_class, existing_config=existing_value, section_label=None
        )

        if value_config is None:
            return None

        result_dict[key] = value_config

    return result_dict


def is_list_of_models(
    field_info: FieldInfo,
    field_type: type,
    origin: type | None,
) -> bool:
    """Check if field is a list[BaseModel] with prompt_as_list metadata."""
    schema_extra = get_field_extra(field_info)
    if origin is not list or not schema_extra.get(SCHEMA_KEYS["PROMPT_AS_LIST"]):
        return False

    args = get_args(field_type)
    return bool(args and is_basemodel_subclass(args[0]))


def is_dict_of_models(
    field_info: FieldInfo,
    field_type: type,
    origin: type | None,
) -> bool:
    """Check if field is a dict[str, BaseModel] with prompt_as_dict metadata."""
    schema_extra = get_field_extra(field_info)
    if origin is not dict or not schema_extra.get(SCHEMA_KEYS["PROMPT_AS_DICT"]):
        return False

    args = get_args(field_type)
    return len(args) == 2 and args[0] is str and is_basemodel_subclass(args[1])  # noqa: PLR2004


def handle_list_of_models(
    field_name: str,
    field_info: FieldInfo,
    field_type: type,
    existing_value: Any,
) -> list[dict] | None:
    """Handle list[BaseModel] fields with prompt_as_list metadata.

    Returns:
        The configured list, or None if cancelled
    """
    schema_extra = get_field_extra(field_info)
    args = get_args(field_type)
    item_class = args[0]
    item_label = schema_extra.get(SCHEMA_KEYS["ITEM_LABEL"], item_class.__name__)
    return prompt_list_of_models(field_name, item_class, item_label, existing_value)


def handle_dict_of_models(
    field_name: str,
    field_info: FieldInfo,
    field_type: type,
    existing_value: Any,
) -> dict[str, dict] | None:
    """Handle dict[str, BaseModel] fields with prompt_as_dict metadata.

    Returns:
        The configured dict, or None if cancelled
    """
    schema_extra = get_field_extra(field_info)
    args = get_args(field_type)
    value_class = args[1]
    item_label = schema_extra.get(SCHEMA_KEYS["ITEM_LABEL"], value_class.__name__)
    key_label = schema_extra.get(SCHEMA_KEYS["KEY_LABEL"], "Key")
    return prompt_dict_of_models(field_name, value_class, item_label, key_label, existing_value)


def prompt_single_field(  # noqa: C901, PLR0912, PLR0913, PLR0915
    field_name: str,
    field_info: FieldInfo,
    description: str,
    default_display: str,
    is_required: bool,
    field_type: type,
    origin: type | None,
    validator: Callable[[Any], tuple[bool, str | None]] | None,
    config_class: type[BaseModel],
    config_dict: dict[str, Any],
) -> Any | None:
    """Prompt for a single field value with validation."""
    while True:
        try:
            raw_answer: Any
            cancelled = False

            if origin is Literal:
                choices = list(get_args(field_type))
                default_val = default_display if default_display in choices else choices[0]
                raw_answer = questionary.select(
                    f"{description}:", choices=choices, default=default_val
                ).ask()
                cancelled = raw_answer is None
            elif field_type is bool:
                default_bool = bool(default_display) if default_display else False
                raw_answer = questionary.confirm(f"{description}:", default=default_bool).ask()
                cancelled = raw_answer is None
            elif field_type is Path:
                raw_answer = questionary.path(
                    f"{description}:", default=default_display, only_directories=True
                ).ask()
                cancelled = raw_answer is None
                if raw_answer:
                    raw_answer = Path(raw_answer)
            elif is_sensitive_field(field_name, field_info):
                raw_answer = questionary.password(
                    f"{description}:", default=default_display if default_display else ""
                ).ask()
                cancelled = raw_answer is None
            else:
                prompt_text = f"{description}:"
                if not is_required:
                    prompt_text += " (optional)"
                raw_answer, cancelled = prompt_with_validation(
                    prompt_text, default_display, field_type, field_name, is_required
                )

            if cancelled:
                click.echo("\n❌ Configuration cancelled by user")
                return None

            answer = normalize_answer(raw_answer)

            if answer is None:
                if is_required:
                    click.echo("❌ This field is required")
                    continue
                return None  # Optional field with no value

            # Run custom validator if provided
            if validator:
                is_valid, error_message = validator(answer)
                if not is_valid:
                    click.echo(f"❌ {error_message}" if error_message else "❌ Invalid value")
                    continue

            # Run Pydantic field validator
            is_valid, error_message = validate_field_value(
                config_class, field_name, answer, config_dict
            )
            if not is_valid:
                click.echo(f"❌ {error_message}" if error_message else "❌ Invalid value")
                continue

            return answer

        except (ValueError, TypeError, KeyError) as e:
            error_msg = str(e)
            if is_sensitive_field(field_name, field_info):
                click.echo(
                    f"❌ Error processing sensitive field '{field_name}': Invalid value provided"
                )
            else:
                click.echo(f"❌ Error processing field '{field_name}': {error_msg}")
            return None
        except KeyboardInterrupt:
            click.echo("\n❌ Configuration cancelled by user")
            return None


def validate_field_value(
    config_class: type[BaseModel],
    field_name: str,
    field_value: Any,
    partial_config: dict[str, Any],
) -> tuple[bool, str | None]:
    """Validate a single field value using Pydantic's field validators.

    Args:
        config_class: The Pydantic model class
        field_name: Name of the field to validate
        field_value: Value to validate
        partial_config: Dictionary of previously validated fields (using field names, not aliases)

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        config_class.model_validate({**partial_config, field_name: field_value})
        return True, None
    except ValidationError as e:
        for error in e.errors():
            error_loc = error.get("loc", ())
            error_msg = error.get("msg", "Invalid value")
            if error_loc and error_loc[0] == field_name:
                return False, error_msg
        return True, None
    except Exception as e:
        return False, str(e)


def prompt_model_fields(  # noqa: C901, PLR0912, PLR0913
    config_class: type[BaseModel],
    *,
    existing_config: dict[str, Any] | None = None,
    section_label: str | None = None,
    skip_fields: set[str] | None = None,
    field_overrides: dict[str, FieldPromptOptions] | None = None,
    allowed_fields: set[str] | None = None,
) -> dict[str, Any] | None:
    """Interactively collect configuration values based on a Pydantic model."""

    existing = existing_config or {}
    skip_fields = skip_fields or set()
    field_overrides = field_overrides or {}

    if section_label:
        click.echo(f"📋 {section_label}")
        click.echo(f"Configure fields for {config_class.__name__}\n")

    config_dict: dict[str, Any] = {}

    for field_name, field_info in config_class.model_fields.items():
        if should_skip_field(
            field_name,
            field_info,
            config_dict,
            existing,
            allowed_fields,
            skip_fields,
            field_overrides,
        ):
            continue

        description = get_field_description(field_name, field_info, field_overrides)

        existing_value = get_existing_value(field_name, field_info, existing)

        env_var, env_value = get_env_value(field_info)
        if env_value is not None:
            config_dict[field_name] = env_value
            click.echo(f"✓ Using {env_var} from environment for {description}")
            continue

        default_value = get_default_value(
            field_info, existing_value, env_value, field_overrides, field_name
        )
        default_display = format_default_display(default_value)

        is_required = is_field_required(field_info, field_overrides, field_name)

        if field_info.annotation is None:
            continue
        field_type, origin = get_actual_type(field_info.annotation)
        validator = field_overrides.get(field_name, {}).get("validate")

        if is_list_of_models(field_info, field_type, origin):
            result = handle_list_of_models(field_name, field_info, field_type, existing_value)
            if result is None:
                return None
            config_dict[field_name] = result

        elif is_dict_of_models(field_info, field_type, origin):
            dict_result: dict[str, dict] | None = handle_dict_of_models(
                field_name, field_info, field_type, existing_value
            )
            if dict_result is None:
                return None
            config_dict[field_name] = dict_result

        else:
            answer = prompt_single_field(
                field_name,
                field_info,
                description,
                default_display,
                is_required,
                field_type,
                origin,
                validator,
                config_class,
                config_dict,
            )

            if answer is None and is_required:
                return None

            if answer is not None:
                config_dict[field_name] = answer

    try:
        config_class.model_validate(config_dict)
    except ValidationError as e:
        click.echo("\n❌ Configuration validation failed:")
        for error in e.errors():
            error_loc = error.get("loc", ())
            error_msg = error.get("msg", "Invalid value")
            if error_loc:
                click.echo(f"  • {error_loc[0]}: {error_msg}")
            else:
                click.echo(f"  • {error_msg}")

        # TODO: Re-enable fix prompt if saving invalid config does not raise errors
        # fix_issues = questionary.confirm(
        #     "\nDo you want to fix these validation issues?", default=True
        # ).ask()

        # if fix_issues is None or not fix_issues:
        #     click.echo("⚠️  Returning configuration with validation errors.")
        #     return config_dict

        click.echo("\n🔄 Re-running configuration wizard...\n")
        return prompt_model_fields(
            config_class,
            existing_config=config_dict,
            section_label=section_label,
            skip_fields=skip_fields,
            field_overrides=field_overrides,
            allowed_fields=allowed_fields,
        )

    return config_dict
