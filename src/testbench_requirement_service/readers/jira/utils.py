import base64
import copy
import re
from datetime import datetime
from typing import Any, Literal

from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig

try:
    from bs4 import BeautifulSoup
    from jira.resources import Field, Issue
except ImportError:
    pass
from sanic.log import logger

from testbench_requirement_service.models.requirement import (
    ExtendedRequirementObject,
    RequirementKey,
    RequirementObjectNode,
    RequirementVersionObject,
    UserDefinedAttribute,
)


def build_requirementobjectnode_from_sprint(
    sprint, key: RequirementKey | None = None, is_requirement: bool = False
):
    sprint_id = str(getattr(sprint, "id", ""))
    return RequirementObjectNode(
        name=getattr(sprint, "name", ""),
        extendedID=sprint_id,
        key=key or RequirementKey(id=sprint_id, version="1.0"),
        owner="",
        status=getattr(sprint, "state", ""),
        priority="",
        requirement=is_requirement,
        children=[],
    )


def build_userdefinedattribute_object(  # noqa: RET503
    field: dict[str, Any], field_value: Any
) -> UserDefinedAttribute:
    value_type = extract_valuetype_from_issue_field(field)
    if value_type == "STRING":
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
    if value_type == "ARRAY":
        if isinstance(field_value, list):
            string_values = []
            for item in field_value:
                if hasattr(item, "value"):
                    string_values.append(item.value)
                elif hasattr(item, "name"):
                    string_values.append(item.name)
                else:
                    string_values.append(str(item))
        else:
            string_values = None
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
    project: str, issue: Issue, config: JiraRequirementReaderConfig
) -> RequirementVersionObject:
    requirement_versions = generate_requirement_versions(project, issue, config)
    return requirement_versions[-1]


def generate_requirement_versions(
    project: str, issue: Issue, config: JiraRequirementReaderConfig
) -> list[RequirementVersionObject]:
    versions = []
    minor = 0
    major = 1

    # Add creation as the initial version
    creator = getattr(issue.fields.creator, "displayName", "Unknown")
    created_dt = datetime.strptime(issue.fields.created, "%Y-%m-%dT%H:%M:%S.%f%z")
    created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
    versions.append(
        RequirementVersionObject(
            name=f"{major}.{minor}",
            date=created_dt,
            author=creator,
            comment=f"Issue created by {creator} on {created_str}",
        )
    )

    histories = sorted(getattr(issue.changelog, "histories", []), key=lambda h: h.created)
    for history in histories:
        changed_fields = {item.field for item in getattr(history, "items", [])}

        is_major, is_minor = classify_change_scope(project, changed_fields, config)

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
                date=history.created,
                author=getattr(history.author, "displayName", "Unknown"),
                comment=get_change_comment(history),
            )
        )

    return versions


# TODO: Maybe different languages?
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
        for v in value:
            if hasattr(v, "name"):
                result.append(str(v.name))
            elif hasattr(v, "value"):
                result.append(str(v.value))
            else:
                result.append(str(v))
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


def set_issue_field(issue: Issue, field_name: str, value: Any, field) -> None:
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


def get_issue_version(  # noqa: C901
    project: str,
    issue: Issue,
    key: RequirementKey,
    config: JiraRequirementReaderConfig,
    custom_fields,
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
    issue_copy = copy.deepcopy(issue)

    histories = sorted(getattr(issue_copy.changelog, "histories", []), key=lambda h: h.created)
    major = 1
    minor = 0
    updated_fields = set()

    for history in histories:
        changed_fields = {item.field for item in getattr(history, "items", [])}

        is_major, is_minor = classify_change_scope(project, changed_fields, config)

        # If we've reached or passed the target version, revert fields to their previous values
        if (major > target_major) or (major == target_major and minor >= target_minor):
            for item in getattr(history, "items", []):
                if item.field in changed_fields and item.field not in updated_fields:
                    field_id = _get_field_id(custom_fields, item.field)
                    set_issue_field(issue_copy, field_id, item.fromString, item.field)
                    updated_fields.add(item.field)
        else:
            for item in getattr(history, "items", []):
                if item.field in changed_fields:
                    field_id = _get_field_id(custom_fields, item.field)
                    set_issue_field(issue_copy, field_id, item.toString, item.field)
                    updated_fields.add(item.field)

        if is_major:
            major += 1
            minor = 0
        elif is_minor:
            minor += 1

    if major == target_major and minor == target_minor:
        return issue

    return issue_copy


def _get_field_id(fields, field_name: str) -> str:
    for field in fields:
        if field["name"] == field_name:
            return field["id"]
    return field_name


def classify_change_scope(
    project: str, changed_fields: set[str], config: JiraRequirementReaderConfig
) -> tuple[bool, bool]:
    major_fields = set(get_config_value(config, "major_change_fields", project))
    minor_fields = set(get_config_value(config, "minor_change_fields", project))

    return (
        bool(major_fields & changed_fields),
        bool(minor_fields & changed_fields),
    )


def build_requirementobjectnode_from_issue(
    project: str,
    issue: Issue,
    owner_field_name: str,
    config: JiraRequirementReaderConfig,
    **node_options: Any,
) -> RequirementObjectNode:
    key: RequirementKey | None = node_options.get("key")
    is_requirement: bool = node_options.get("is_requirement", True)

    owner_value = getattr(issue.fields, owner_field_name, None)
    owner = getattr(owner_value, "displayName", "") if owner_value else ""
    owner = owner if owner else ""

    status_field = getattr(issue.fields, "status", None)
    status = status_field.name if status_field else ""

    priority_field = getattr(issue.fields, "priority", None)
    priority = priority_field.name if priority_field else ""

    if key is None:
        requirement_version = get_current_requirement_version(project, issue, config).name
        key = RequirementKey(id=issue.key, version=requirement_version)

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
        description=build_rich_description(issue, jira_server_url),
        documents=[issue.permalink(), *attachments],
        baseline=baseline,
    )


def build_rich_description(issue: Issue, jira_server_url: str) -> str:
    """
    Render Jira issue description with embedded images inside a full HTML body.
    """
    description_html = embed_jira_images(issue, jira_server_url=jira_server_url)
    return f"<html><body>{description_html}</body></html>"


def embed_jira_images(issue: Issue, jira_server_url: str, field_id: str = "description") -> str:  # noqa: C901
    """
    Embed Jira images referenced in an issue's rendered description by converting relative URLs
    and Jira attachment URLs into absolute URLs or inline base64-encoded data URIs.

    Processes <img> tags with 'src' attributes pointing to:
    - Jira's relative image paths (starting with '/images/'), prepending the Jira server URL.
    - Jira's REST API attachment URLs, embedding images as base64 after verifying MIME types and size limits.

    Ensures safety by validating URLs, whitelisting trusted MIME types (PNG, JPEG, GIF), limiting image size,
    and removing unsupported or unsafe image sources. Logs warnings on issues encountered.

    Args:
        issue (Issue): Jira issue object containing renderedFields.description and fields.attachment.

    Returns:
        str: HTML string with images embedded as absolute URLs or data URIs.
    """  # noqa: E501
    allowed_image_mime_types = {"image/png", "image/jpeg", "image/gif"}
    max_embedded_image_size = 5 * 1024 * 1024  # 5 MB limit for embedded images
    jira_attachment_url_pattern = re.compile(r"^/rest/api/\d+/attachment/content/(\d+)$")

    description = getattr(issue.renderedFields, field_id, "")
    if not description:
        logger.warning(f"Issue {issue.key} missing renderedFields.{field_id}")
        return ""

    # Build attachment dictionary mapping attachment ID to tuple (mime type, encoded data)
    attachment_dict: dict[str, tuple[str, str]] = {}
    attachments = getattr(issue.fields, "attachment", [])
    for attachment in attachments:
        try:
            mime_type = getattr(attachment, "mimeType", None)
            if not mime_type:
                logger.warning(f"Attachment {attachment.id} missing mimeType metadata")
                continue
            if mime_type not in allowed_image_mime_types:
                logger.warning(f"Attachment {attachment.id} has disallowed mimeType: {mime_type}")
                continue

            size = getattr(attachment, "size", None)
            if size and size > max_embedded_image_size:
                logger.warning(
                    f"Attachment {attachment.id} size ({size} bytes) exceeds "
                    f"maximum allowed size ({max_embedded_image_size} bytes)"
                )
                continue

            image_bytes = attachment.get()

            actual_size = len(image_bytes)
            if actual_size > max_embedded_image_size:
                logger.warning(
                    f"Attachment {attachment.id} size ({size} bytes) exceeds "
                    f"maximum allowed size ({max_embedded_image_size} bytes)"
                )
                continue

            encoded = base64.b64encode(image_bytes).decode("utf-8")
            attachment_dict[attachment.id] = (mime_type, encoded)
            logger.debug(
                f"Successfully processed attachment {attachment.id} ({len(image_bytes)} bytes)"
            )
        except Exception as e:
            logger.debug(f"Could not process attachment {attachment.id}: {e}")
            continue

    # Embed images in the issue description
    soup = BeautifulSoup(description, "html.parser")
    img_tags = soup.find_all("img")
    for img in img_tags:
        src = str(img.get("src", ""))
        if src.startswith("/images/"):
            img["src"] = f"{jira_server_url}{src}"
            continue

        match = jira_attachment_url_pattern.fullmatch(src)
        if not match:
            img.attrs.pop("src", None)
            logger.warning(f"Removed image with unsupported src: {src}")
            continue

        attachment_id = match.group(1)
        if attachment_id not in attachment_dict:
            img.attrs.pop("src", None)
            logger.warning(f"Attachment {attachment_id} not found in validated attachments")
            continue

        mime_type, encoded = attachment_dict[attachment_id]
        img["src"] = f"data:{mime_type};base64,{encoded}"

    return str(soup)


def get_config_value(
    config: JiraRequirementReaderConfig, attr: str, project: str | None = None
) -> str:
    """
    Retrieve a configuration value, optionally project-specific, falling back to global config.
    Args:
        attr (str): The attribute name to retrieve.
        project (str | None): The project name, if any.
    Returns:
        The value of the attribute, or None if not found.
    """
    if project and project in config.projects:
        project_config = config.projects[project]
        value = getattr(project_config, attr, None)
        if value is not None:
            return value  # type: ignore
    return getattr(config, attr, None)  # type: ignore
