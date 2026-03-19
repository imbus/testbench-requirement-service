import copy
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Literal

from dateutil.parser import isoparse
from dateutil.parser import parse as dateutil_parse
from jira.resources import Field, Issue, Resource

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
    field: dict[str, Any] | Field, field_value: Any
) -> UserDefinedAttribute:
    name = field.get("name", "") if isinstance(field, dict) else getattr(field, "name", "")
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
            name=name,
            valueType="ARRAY",
            stringValues=string_values,
        )
    if value_type == "BOOLEAN":
        return UserDefinedAttribute(
            name=name,
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
        name=name,
        valueType="STRING",
        stringValue=string_value,
    )


def build_userdefinedattribute_objects_for_issue(
    issue: Issue,
    uda_fields: list[Field],
    project: str,
    config: JiraRequirementReaderConfig,
) -> list[UserDefinedAttribute]:
    """Build UserDefinedAttribute objects for a single issue from the given field descriptors."""
    rendered_fields_config = set(get_config_value(config, "rendered_fields", project) or [])
    issue_fields = getattr(issue, "fields", None)
    if not issue_fields:
        logger.warning(f"Issue {issue.key} has no fields; skipping UDA extraction.")
        return []
    rendered_fields_obj = getattr(issue, "renderedFields", None)

    udas = []
    for field in uda_fields:
        field_id = get_field_id(field)
        if not hasattr(issue_fields, field_id):
            continue
        if (
            rendered_fields_obj is not None
            and hasattr(rendered_fields_obj, field_id)
            and getattr(field, "name", None) in rendered_fields_config
        ):
            field_value = build_rendered_field_html(
                issue,
                field_id=field_id,
                jira_server_url=config.server_url,
                include_head=True,
            )
        else:
            field_value = getattr(issue_fields, field_id)
        udas.append(build_userdefinedattribute_object(field, field_value))
    return udas


def extract_valuetype_from_issue_field(
    field: dict[str, Any] | Field,
) -> Literal["STRING", "ARRAY", "BOOLEAN"]:
    if isinstance(field, dict):
        schema = field.get("schema", {})
        field_type = schema.get("type")
    else:
        schema = getattr(field, "schema", None)
        field_type = getattr(schema, "type", None)
    if field_type == "array":
        return "ARRAY"
    if field_type == "boolean":
        return "BOOLEAN"
    return "STRING"


def get_field_id(field: Field) -> str:
    for attr in ("id", "key", "fieldId"):
        if hasattr(field, attr):
            return str(getattr(field, attr))
    field_name = getattr(field, "name", repr(field))
    logger.warning(f"Field {field_name} has no id, key, or fieldId.")
    return field_name


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
    creator = getattr(getattr(issue.fields, "creator", None), "displayName", "Unknown")
    created_dt = parse_jira_datetime(getattr(issue.fields, "created", None))
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
        key=lambda h: parse_jira_datetime(getattr(h, "created", None)),
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
                date=parse_jira_datetime(getattr(history, "created", None)),
                author=getattr(getattr(history, "author", None), "displayName", "Unknown"),
                comment=get_change_comment(history),
            )
        )

    return versions


def extract_changed_fields(history) -> set[str]:
    """Extract the set of changed field names from a Jira issue history entry."""
    return {
        field
        for item in getattr(history, "items", [])
        if (field := getattr(item, "field", None)) is not None
    }


def get_change_comment(history) -> str:
    changes = []
    for item in getattr(history, "items", []):
        from_val = getattr(item, "fromString", "")
        to_val = getattr(item, "toString", "")
        changes.append(f"{getattr(item, 'field', '?')}: '{from_val}' → '{to_val}'")
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


def _wrap_as_resource(value: str) -> SimpleNamespace:
    return SimpleNamespace(name=value, displayName=value, value=value)


def set_issue_field(issue: Issue, field_name: str, value: str | None):
    """
    Set a field value on the issue, replacing the entire field with ``value``.

    ``value`` is always the plain ``fromString`` string from a Jira changelog item.
    If the current field holds a resource object (i.e. not a plain string or None),
    the value is stored in a SimpleNamespace so that downstream attribute accesses
    like ``.name``, ``.displayName``, ``.value``, and ``.content`` keep working.
    Plain string fields (e.g. summary, description) are set directly.
    """
    if value is None:
        setattr(issue.fields, field_name, None)
        return

    rendered_fields_obj = getattr(issue, "renderedFields", None)
    if rendered_fields_obj is not None and hasattr(rendered_fields_obj, field_name):
        rendered_value = format_description(value) if field_name == "description" else value
        setattr(rendered_fields_obj, field_name, rendered_value)

    current = getattr(issue.fields, field_name, None)

    if isinstance(current, list):
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            setattr(issue.fields, field_name, [])
        elif current and isinstance(current[0], str):
            # plain string list (labels)
            setattr(issue.fields, field_name, values)
        else:
            # resource list (fixVersions, components)
            setattr(issue.fields, field_name, [_wrap_as_resource(v) for v in values])
    elif isinstance(current, (Resource, SimpleNamespace)):
        # Field holds a resource object — wrap to preserve dot-access
        setattr(issue.fields, field_name, _wrap_as_resource(value))
    elif isinstance(current, (int, float)):
        try:
            setattr(issue.fields, field_name, float(value))
        except (ValueError, TypeError):
            setattr(issue.fields, field_name, value)
    else:
        setattr(issue.fields, field_name, value)


def get_issue_version(
    project: str,
    issue: Issue,
    key: RequirementKey,
    config: JiraRequirementReaderConfig,
    fields: list[dict[str, Any]],
) -> Issue:
    """
    Reconstructs the issue's fields to reflect their state at the specified version.
    Returns a deep copy of the issue with fields set to the target version state.
    The original issue object is not modified.

    Args:
        project (str): The project name.
        issue (Issue): The Jira issue object.
        key (RequirementKey): The requirement key containing the target version.
        config (JiraRequirementReaderConfig): The Jira requirement reader configuration.
        fields (list[dict[str, Any]]): The list of Jira fields.

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
        key=lambda h: parse_jira_datetime(getattr(h, "created", None)),
    )
    major = 1
    minor = 0
    major_fields = set(get_config_value(config, "major_change_fields", project) or [])
    minor_fields = set(get_config_value(config, "minor_change_fields", project) or [])
    reverted_fields: set[str] = set()

    for history in histories:
        changed_fields = extract_changed_fields(history)
        is_major, is_minor = classify_change_scope(changed_fields, major_fields, minor_fields)

        # Once we've reached the target version, revert all subsequent changes.
        if (major > target_major) or (major == target_major and minor >= target_minor):
            for item in getattr(history, "items", []):
                item_field = getattr(item, "field", None)
                if item_field is None or item_field in reverted_fields:
                    continue
                field_id = getattr(item, "fieldId", None) or _get_field_id(fields, item_field)
                previous_value: str | None = getattr(item, "fromString", None)
                set_issue_field(issue_copy, field_id, previous_value)
                reverted_fields.add(item_field)

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
        if field.get("name") == field_name:
            field_id = field.get("id")
            if field_id:
                return str(field_id)
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

    owner_field_name = get_config_value(config, "owner_field", project)
    owner_field = getattr(issue.fields, owner_field_name, None)
    if not owner_field:
        owner = ""
    elif isinstance(owner_field, str):
        owner = owner_field
    else:
        owner = (
            getattr(owner_field, "displayName", None) or getattr(owner_field, "name", None) or ""
        )

    status_field = getattr(issue.fields, "status", None)
    status = getattr(status_field, "name", "") if status_field else ""

    priority_field = getattr(issue.fields, "priority", None)
    priority = getattr(priority_field, "name", "") if priority_field else ""

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
    if isinstance(attachments_field, list):
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
