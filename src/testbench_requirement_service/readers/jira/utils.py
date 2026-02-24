import copy
from datetime import datetime, timezone
from typing import Any, Literal

try:  # noqa: SIM105
    from jira.resources import Field, Issue
except ImportError:  # pragma: no cover
    pass
from dateutil.parser import isoparse
from dateutil.parser import parse as dateutil_parse

from testbench_requirement_service.log import logger
from testbench_requirement_service.models.requirement import (
    ExtendedRequirementObject,
    RequirementKey,
    RequirementObjectNode,
    RequirementVersionObject,
    UserDefinedAttribute,
)
from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.readers.jira.render_utils import build_rendered_field_html

UNSET_DATETIME = datetime.min.replace(tzinfo=timezone.utc)


def escape_jql_value(value: str) -> str:
    """Escape special characters in a JQL string value to prevent injection.

    Jira JQL uses backslash as an escape character inside quoted strings.
    This ensures user-supplied values (e.g. baseline names) cannot break out
    of the quoted context and inject arbitrary JQL operators.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def parse_jira_datetime(dt: str | float | datetime | None) -> datetime:
    """
    Parse a Jira API datetime value (string or datetime) to a timezone-aware datetime.

    Handles:
    - datetime objects (returned as-is, with UTC fallback for naive ones)
    - ISO 8601 strings from Jira Cloud and Server/DC (with or without colon in
      UTC offset, with or without milliseconds)
    - Unix epoch milliseconds (int or numeric string), commonly returned by
      the Agile API (sprints) and raw changelog endpoints via ``dict2resource``

    Always returns a timezone-aware datetime.  Naive datetime inputs are assumed
    to be UTC and normalised accordingly so that downstream code never mixes
    aware and naive objects.
    """
    if dt is None:
        logger.debug("No datetime provided; falling back to epoch")
        return UNSET_DATETIME

    if isinstance(dt, datetime):
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    if isinstance(dt, (int, float)):
        return datetime.fromtimestamp(dt / 1000, tz=timezone.utc)

    dt_str = str(dt).strip()

    # Numeric string (epoch ms)
    try:
        return datetime.fromtimestamp(float(dt_str) / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        pass

    # ISO 8601 (strict first, lenient fallback)
    try:
        parsed = isoparse(dt_str)
    except ValueError:
        try:
            parsed = dateutil_parse(dt_str)
        except (ValueError, OverflowError, TypeError):
            logger.debug(f"Could not parse Jira datetime: {dt!r}; falling back to epoch")
            return UNSET_DATETIME

    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def build_userdefinedattribute_object(
    field: dict[str, Any], field_value: Any
) -> UserDefinedAttribute:
    value_type = extract_valuetype_from_issue_field(field)
    if value_type == "ARRAY":
        string_values: list[str] | None = None
        if isinstance(field_value, list):
            string_values = []
            for item in field_value:
                if hasattr(item, "value"):
                    string_values.append(item.value)
                elif hasattr(item, "name"):
                    string_values.append(item.name)
                else:
                    string_values.append(str(item))
        return UserDefinedAttribute(
            name=field["name"],
            valueType="ARRAY",
            stringValues=string_values,
        )
    if value_type == "BOOLEAN":
        return UserDefinedAttribute(
            name=field["name"],
            valueType="BOOLEAN",
            booleanValue=bool(field_value),
        )
    # Default to STRING type
    if hasattr(field_value, "value"):
        string_value = field_value.value
    elif hasattr(field_value, "name"):
        string_value = field_value.name
    else:
        string_value = str(field_value) if field_value else None
    return UserDefinedAttribute(
        name=field["name"],
        valueType="STRING",
        stringValue=string_value,
    )


def extract_valuetype_from_issue_field(
    field: dict[str, Any],
) -> Literal["STRING", "ARRAY", "BOOLEAN"]:
    schema = field.get("schema", {})
    field_type = schema.get("type")
    if field_type == "array":
        return "ARRAY"
    if field_type == "boolean":
        return "BOOLEAN"
    return "STRING"


def get_field_id(field: Field) -> str:
    for attr in ("id", "key", "fieldId"):
        if hasattr(field, attr):
            return str(getattr(field, attr))
    logger.warning(f"Field {field.name} has no id, key, or fieldId.")
    return str(field.name)


def is_version_type_field(field: Field) -> bool:
    schema_type = getattr(field.schema, "type", None)
    items_type = getattr(field.schema, "items", None)
    return schema_type == "version" or (schema_type == "array" and items_type == "version")


def get_current_requirement_version(
    project: str,
    issue: Issue,
    config: JiraRequirementReaderConfig,
) -> RequirementVersionObject:
    requirement_versions = generate_requirement_versions(project, issue, config)
    return requirement_versions[-1]


def generate_requirement_versions(
    project: str,
    issue: Issue,
    config: JiraRequirementReaderConfig,
) -> list[RequirementVersionObject]:
    versions: list[RequirementVersionObject] = []
    minor = 0
    major = 1

    # Add creation as the initial version
    creator = getattr(issue.fields.creator, "displayName", "Unknown")
    created_dt = parse_jira_datetime(issue.fields.created)
    created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
    versions.append(
        RequirementVersionObject(
            name=f"{major}.{minor}",
            date=created_dt,
            author=creator,
            comment=f"Issue created by {creator} on {created_str}",
        )
    )

    major_fields = set(get_config_value(config, "major_change_fields", project) or [])
    minor_fields = set(get_config_value(config, "minor_change_fields", project) or [])

    histories = sorted(
        getattr(issue.changelog, "histories", []),
        key=lambda h: parse_jira_datetime(h.created),
    )
    for history in histories:
        changed_fields = extract_changed_fields(history)
        is_major, is_minor = classify_change_scope(changed_fields, major_fields, minor_fields)
        if not is_major and not is_minor:
            continue

        if is_major:
            major += 1
            minor = 0
        elif is_minor:
            minor += 1

        versions.append(
            RequirementVersionObject(
                name=f"{major}.{minor}",
                date=parse_jira_datetime(history.created),
                author=getattr(history.author, "displayName", "Unknown"),
                comment=get_change_comment(history),
            )
        )

    return versions


def extract_changed_fields(history) -> set[str]:
    """Extract the set of changed field names from a Jira issue history entry."""
    return {item.field for item in getattr(history, "items", [])}


def get_change_comment(history) -> str:
    changes = []
    for item in getattr(history, "items", []):
        from_val = getattr(item, "fromString", "")
        to_val = getattr(item, "toString", "")
        changes.append(f"{item.field}: '{from_val}' → '{to_val}'")
    return "; ".join(changes) if changes else "Fields updated"


def extract_baselines_from_issue(issue: Issue, baseline_field: str) -> list[str]:
    value = getattr(issue.fields, baseline_field, None)
    if value is None:
        return []
    if isinstance(value, list):
        result = []
        for entry in value:
            if hasattr(entry, "name"):
                result.append(str(entry.name))
            elif hasattr(entry, "value"):
                result.append(str(entry.value))
            else:
                result.append(str(entry))
        return result
    if hasattr(value, "name"):
        return [str(value.name)]
    if hasattr(value, "value"):
        return [str(value.value)]
    return [str(value)]


def format_description(description: str) -> str:
    if not isinstance(description, str) or not description:
        return ""
    return "<p>" + description.replace("\n\n", "</p><p>") + "</p>"


def set_issue_field(issue: Issue, field_name: str, value: Any) -> None:
    """
    Helper to set a field value on the issue.fields object, handling nested attributes.
    """
    if hasattr(issue.renderedFields, field_name):
        if field_name == "description":
            value = format_description(value)
        setattr(issue.renderedFields, field_name, value)

    if hasattr(issue.fields, field_name):
        attr = getattr(issue.fields, field_name)
        if hasattr(attr, "name"):
            attr.name = value
        elif hasattr(attr, "displayName"):
            attr.displayName = value
        else:
            setattr(issue.fields, field_name, value)
    else:
        setattr(issue.fields, field_name, value)


def get_issue_version(
    project: str,
    issue: Issue,
    key: RequirementKey,
    config: JiraRequirementReaderConfig,
    custom_fields: list[dict[str, Any]],
) -> Issue:
    """
    Reconstructs the issue's fields to reflect their state at the specified version.
    Modifies the issue object in-place.

    Args:
        issue (Issue): The Jira issue object.
        key (RequirementKey): The requirement key containing the target version.

    Returns:
        Issue: The issue object with fields set to the specified version.
    """
    try:
        target_major, target_minor = map(int, key.version.split("."))
    except Exception as e:
        logger.error(f"Invalid version format '{key.version}' for requirement key '{key.id}': {e}")
        raise ValueError(
            f"Invalid version format '{key.version}' for requirement key '{key.id}'. "
            "Expected format 'major.minor'."
        ) from e

    issue_copy = copy.deepcopy(issue, memo={id(issue._session): issue._session})
    histories = sorted(
        getattr(issue_copy.changelog, "histories", []),
        key=lambda h: parse_jira_datetime(h.created),
    )
    major = 1
    minor = 0
    major_fields = set(get_config_value(config, "major_change_fields", project) or [])
    minor_fields = set(get_config_value(config, "minor_change_fields", project) or [])
    updated_fields: set[str] = set()

    for history in histories:
        changed_fields = extract_changed_fields(history)
        is_major, is_minor = classify_change_scope(changed_fields, major_fields, minor_fields)

        # If we've reached or passed the target version, revert fields to their previous values
        if (major > target_major) or (major == target_major and minor >= target_minor):
            for item in getattr(history, "items", []):
                if item.field not in updated_fields:
                    field_id = _get_field_id(custom_fields, item.field)
                    set_issue_field(issue_copy, field_id, item.fromString)
                    updated_fields.add(item.field)
        else:
            for item in getattr(history, "items", []):
                field_id = _get_field_id(custom_fields, item.field)
                set_issue_field(issue_copy, field_id, item.toString)
                updated_fields.add(item.field)

        if is_major:
            major += 1
            minor = 0
        elif is_minor:
            minor += 1

    if major == target_major and minor == target_minor:
        return issue

    return issue_copy


def _get_field_id(fields: list[dict[str, Any]], field_name: str) -> str:
    """Helper to get the field ID from the field name, using the list of Jira fields."""
    for field in fields:
        if field["name"] == field_name:
            return str(field["id"])
    return field_name


def classify_change_scope(
    changed_fields: set[str],
    major_fields: set[str],
    minor_fields: set[str],
) -> tuple[bool, bool]:
    """Determine if changed fields intersect with major or minor field sets.
    Returns a tuple of (is_major_change, is_minor_change).
    """
    changed_fields_lower = {f.lower() for f in changed_fields}
    major_fields_lower = {f.lower() for f in major_fields}
    minor_fields_lower = {f.lower() for f in minor_fields}
    is_major_change = bool(major_fields_lower & changed_fields_lower)
    is_minor_change = bool(minor_fields_lower & changed_fields_lower)
    return is_major_change, is_minor_change


def build_requirementobjectnode_from_issue(
    issue: Issue,
    project: str,
    config: JiraRequirementReaderConfig,
    key: RequirementKey | None = None,
    is_requirement: bool = True,
) -> RequirementObjectNode:
    if key is None:
        requirement_version = get_current_requirement_version(project, issue, config).name
        key = RequirementKey(id=issue.key, version=requirement_version)

    owner_field_name = get_config_value(config, "owner", project)
    owner_field = getattr(issue.fields, owner_field_name, None)
    owner = getattr(owner_field, "displayName", "") if owner_field else ""

    status_field = getattr(issue.fields, "status", None)
    status = status_field.name if status_field else ""

    priority_field = getattr(issue.fields, "priority", None)
    priority = priority_field.name if priority_field else ""

    return RequirementObjectNode(
        name=getattr(issue.fields, "summary", ""),
        extendedID=issue.key,
        key=key,
        owner=owner,
        status=status,
        priority=priority,
        requirement=is_requirement,
        children=[],
    )


def build_extendedrequirementobject_from_issue(
    issue: Issue,
    baseline: str,
    requirement_object: RequirementObjectNode,
    jira_server_url: str,
) -> ExtendedRequirementObject:
    attachments_field = getattr(issue.fields, "attachment", None)
    if attachments_field:
        attachments = [attachment.content for attachment in attachments_field if attachment.content]
    else:
        attachments = []

    return ExtendedRequirementObject(
        **requirement_object.model_dump(),
        description=build_rendered_field_html(
            issue, field_id="description", jira_server_url=jira_server_url
        ),
        documents=[issue.permalink(), *attachments],
        baseline=baseline,
    )


def get_config_value(
    config: JiraRequirementReaderConfig, attr: str, project: str | None = None
) -> Any:
    """Retrieve a configuration value, with optional project-specific override.

    Looks up *attr* on the project-specific config first (if *project* is given
    and has an override entry).  Falls back to the global config.

    Args:
        config: The reader configuration object.
        attr: The attribute name to retrieve.
        project: The project name, if any.

    Returns:
        The value of the attribute, or ``None`` if not found.
    """
    if project and project in config.projects:
        project_config = config.projects[project]
        value = getattr(project_config, attr, None)
        if value is not None:
            return value
    return getattr(config, attr, None)
