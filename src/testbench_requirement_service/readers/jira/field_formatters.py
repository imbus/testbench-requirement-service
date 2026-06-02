"""
Field formatters for Jira field values.

Generic conversion is handled by `to_str()`, which covers the vast majority of
Jira resource types (options, statuses, priorities, users, versions, …).

Field-specific formatters are only needed for fields whose structure cannot be
reduced to a single readable attribute — the canonical example being
``issuelinks``, where the relationship and the remote key must be composed.

To add a custom formatter for a field:

    from testbench_requirement_service.readers.jira.field_formatters import register

    @register("customfield_10001")
    def format_my_field(field_value: Any, issue: Issue) -> str | list[str]:
        return f"My value: {field_value}"
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from jira.resources import Issue

from testbench_requirement_service.log import logger

FieldFormatter = Callable[[Any, Issue], "str | list[str]"]

_FORMATTERS: dict[str, FieldFormatter] = {}


def register(field_id_or_name: str) -> Callable[[FieldFormatter], FieldFormatter]:
    """Decorator — register a formatter for a Jira field ID or display name.

    For **built-in system fields** (``issuelinks``, ``fixVersions``, ``attachment``,
    ``subtasks``, …) the field ID is stable across all Jira instances, so
    register by ID::

        @register("issuelinks")
        def format_issuelinks(value, issue): ...

    For **custom fields** the numeric part of ``customfield_XXXXX`` is
    instance-specific — ``customfield_10020`` is Sprint on Atlassian Cloud but
    may be something else on a self-hosted instance.  Register by the field's
    **display name** instead, which is consistent across instances::

        @register("Sprint")
        def format_sprint(value, issue): ...

    At lookup time :func:`format_value` tries the field ID first, then the
    display name, so both styles work transparently.
    """

    def decorator(func: FieldFormatter) -> FieldFormatter:
        _FORMATTERS[field_id_or_name] = func
        return func

    return decorator


def to_str(value: Any) -> str:
    """Convert a single Jira field value to a readable string.

    Resolution order for common Jira resource types:
    - ``displayName``  — User / Person objects (preferred over ``name``, which
                         is the login/account-id rather than the full name)
    - ``value``        — Option / custom-select fields
    - ``name``         — Status, Priority, IssueType, Version, Component, …
    - ``str()``        — final fallback
    """
    if hasattr(value, "displayName"):
        return value.displayName  # type: ignore[no-any-return]
    if hasattr(value, "value"):
        return value.value  # type: ignore[no-any-return]
    if hasattr(value, "name"):
        return value.name  # type: ignore[no-any-return]
    return str(value)


def format_value(
    field_id: str, field_name: str, field_value: Any, issue: Issue
) -> str | list[str] | None:
    """Apply the registered formatter for this field, or return ``None``.

    Lookup order: **field ID** first (e.g. ``"issuelinks"``), then **field
    display name** (e.g. ``"Sprint"``).  The name fallback makes formatters
    registered by display name work regardless of the ``customfield_XXXXX`` ID
    assigned by each Jira instance.

    Returns ``None`` when no formatter is registered, signalling the caller to
    fall back to generic :func:`to_str` handling.  Formatter exceptions are
    caught and logged so a single bad field never breaks the whole attribute
    list.
    """
    formatter = _FORMATTERS.get(field_id) or _FORMATTERS.get(field_name)
    if formatter is None:
        return None
    try:
        return formatter(field_value, issue)
    except Exception as e:
        logger.warning(
            "Formatter for '%s' (%s) failed: %s. Falling back to generic.",
            field_name,
            field_id,
            e,
            exc_info=True,
        )
        return None


@register("issuelinks")
def _format_issuelinks(field_value: Any, issue: Issue) -> list[str]:
    """Format issue links as ``"<issue.key> <relation> <other.key>"``.

    Example output::

        ["APP-123 blocks OTHER-456", "APP-123 is related to OTHER-789"]
    """
    if not isinstance(field_value, list):
        return [to_str(field_value)]

    issue_key = getattr(issue, "key", "UNKNOWN")
    result: list[str] = []

    for link in field_value:
        if hasattr(link, "inwardIssue"):
            relation = getattr(getattr(link, "type", None), "inward", "related to")
            other_key = getattr(link.inwardIssue, "key", "UNKNOWN")
        elif hasattr(link, "outwardIssue"):
            relation = getattr(getattr(link, "type", None), "outward", "related to")
            other_key = getattr(link.outwardIssue, "key", "UNKNOWN")
        else:
            logger.debug("Issue link for %s has no inward/outward issue: %s", issue_key, link)
            continue

        result.append(f"{issue_key} {relation} {other_key}")

    return result
