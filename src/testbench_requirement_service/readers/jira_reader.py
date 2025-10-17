# mypy: ignore-errors
# ruff: noqa

import base64
import logging
import os
import re
from collections import OrderedDict
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from bs4 import BeautifulSoup
from jira import JIRA, Issue, JIRAError, Project
from jira.client import ResultList
from jira.resources import Field
from pydantic import BaseModel, ValidationError, model_validator

from testbench_requirement_service.models.requirement import (
    BaselineObject,
    BaselineObjectNode,
    ExtendedRequirementObject,
    RequirementKey,
    RequirementObjectNode,
    RequirementVersionObject,
    UserDefinedAttribute,
    UserDefinedAttributeResponse,
)
from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader


class JiraRequirementReaderConfig(BaseModel):
    server_url: str
    auth_type: Literal["basic", "token", "oauth"] = "basic"
    username: str | None = None
    api_token: str | None = None  # for basic auth, paired with username
    token: str | None = None  # for bearer/token-based auth, Jira Self Hosted
    access_token: str | None = None
    access_token_secret: str | None = None
    consumer_key: str | None = None
    key_cert: str | None = None

    baseline_field: str = "fixVersions"

    @model_validator(mode="after")
    def validate_config(self):
        if self.auth_type == "basic":
            self.username = self.username or os.getenv("JIRA_USERNAME")
            if not self.username:
                raise ValueError(
                    "Jira username must be provided for basic auth (via config or JIRA_USERNAME env)"
                )

            self.api_token = self.api_token or os.getenv("JIRA_API_TOKEN")
            if not self.api_token:
                raise ValueError(
                    "Jira API token must be provided for basic auth (via config or JIRA_API_TOKEN env)"
                )
        elif self.auth_type == "token":
            self.token = self.token or os.getenv("JIRA_BEARER_TOKEN")
            if not self.token:
                raise ValueError(
                    "Jira Personal Access Token must be provided for token auth (via config or JIRA_BEARER_TOKEN env)"
                )
        elif self.auth_type == "oauth":
            self.access_token = self.acces_token or os.getenv("JIRA_ACCESS_TOKEN")
            self.access_token_secret = self.access_token_secret or os.getenv(
                "JIRA_ACCESS_TOKEN_SECRET"
            )
            self.consumer_key = self.consumer_key or os.getenv("JIRA_CONSUMER_KEY")
            self.key_cert = self.key_cert or os.getenv("JIRA_KEY_CERT")
            if not self.access_token:
                raise ValueError(
                    "Jira Personal Access Token must be provided for token auth (via config or JIRA_ACCESS_TOKEN env)"
                )
            if not self.access_token_secret:
                raise ValueError(
                    "Jira Access Token Secret must be provided for token auth (via config or JIRA_ACCESS_TOKEN_SECRET env)"
                )
            if not self.consumer_key:
                raise ValueError(
                    "Jira consumer key must be provided for token auth (via config or JIRA_CONSUMER_KEY env)"
                )
            if not self.key_cert:
                raise ValueError(
                    "Jira Private Key must be provided for token auth (via config or JIRA_KEY_CERT env)"
                )

        return self


class JiraRequirementReader(AbstractRequirementReader):
    def __init__(self, config_path: str):
        self.logger = logging.getLogger(__name__)
        self.logger.level = logging.DEBUG

        self.config = self._load_and_validate_config_from_path(Path(config_path))

        self.jira = self._connect()
        self.uses_new_issuetypes_endpoint = (not self.jira._is_cloud) and (
            self.jira._version >= (8, 4, 0)
        )
        self.uses_manual_pagination = not self.jira._is_cloud and self.jira._version < (8, 4, 0)

        # key: project name (format: "{project.name} ({project.key})"), value: Project Resource
        self._projects: dict[str, Project] = {}
        # key: project name (format: "{project.name} ({project.key})"), value: list of project baselines as str
        self._baselines: dict[str, list[str]] = {}

    @property
    def projects(self) -> dict[str, Project]:
        if not self._projects:
            self._fetch_projects()
        return self._projects

    def project_exists(self, project: str) -> bool:
        if project in self.projects:
            return True
        # Cache miss: fetch projects and check again
        self._fetch_projects()
        return project in self.projects

    def baseline_exists(self, project: str, baseline: str) -> bool:
        return baseline == "Current Baseline" or baseline in self._get_baselines_for_project(
            project
        )

    def get_projects(self) -> list[str]:
        return list(self.projects.keys())

    def get_baselines(self, project: str) -> list[BaselineObject]:
        baselines = sorted(self._get_baselines_for_project(project))
        return [
            BaselineObject(
                name="Current Baseline",
                date=datetime.now(timezone.utc),
                type="CURRENT",
            ),
            *[
                BaselineObject(
                    name=baseline,
                    date=datetime.now(timezone.utc),
                    type="UNLOCKED",
                )
                for baseline in baselines
            ],
        ]

    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        issues = self._fetch_issues(project, baseline)
        if not issues:
            self.logger.debug(f"No issues found for project '{project}' and baseline '{baseline}'")

        issues.sort(key=self.sort_by_issue_key)
        requirement_nodes = self._build_requirement_nodes(issues)
        requirement_tree = self._build_requirement_tree(issues, requirement_nodes)

        return BaselineObjectNode(
            name=baseline,
            date=datetime.now(timezone.utc),
            type="CURRENT",
            children=sorted(
                requirement_tree.values(), key=lambda x: int(x.extendedID.split("-")[-1])
            ),
        )

    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        all_fields = self.jira.fields()
        custom_fields = [
            field for field in all_fields if field.get("id", "").startswith("customfield_")
        ]
        return [
            UserDefinedAttribute(
                name=field["name"],
                valueType=self._extract_valuetype_from_issue_field(field),
            )
            for field in custom_fields
        ]

    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributeResponse]:
        if not requirement_keys:
            return []

        fields = [field for field in self.jira.fields() if field["name"] in attribute_names]
        field_ids = [field["id"] for field in fields]
        user_defined_attributes: list[UserDefinedAttributeResponse] = []

        for req_key in requirement_keys:
            try:
                issue = self.jira.issue(req_key.id, fields=",".join(field_ids))
            except JIRAError:
                continue
            udas = []
            for field in fields:
                if not hasattr(issue.fields, field["id"]):
                    continue
                field_value = getattr(issue.fields, field["id"])
                udas.append(self._build_userdefinedattribute_object(field, field_value))
            user_defined_attributes.append(
                UserDefinedAttributeResponse(key=req_key, userDefinedAttributes=udas)
            )

        return user_defined_attributes

    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        issue = self._fetch_issue(
            key.id,
            fields="summary,assignee,status,priority,parent,description",
            expand="renderedFields",
        )

        return ExtendedRequirementObject(
            name=issue.fields.summary,
            extendedID=issue.key,
            key=key,
            owner=issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
            status=issue.fields.status.name if issue.fields.status else "",
            priority=issue.fields.priority.name if issue.fields.priority else "",
            requirement=True,
            description=self._build_rich_description(issue),
            documents=[issue.permalink()],
            baseline=baseline,
        )

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        issue = self.jira.issue(key.id, fields="summary,created,creator", expand="changelog")

        versions = []

        # Add creation as the initial version
        versions.append(
            RequirementVersionObject(
                name=issue.fields.summary,
                date=issue.fields.created,
                author=issue.fields.creator.displayName,
                comment="Initial version",  # TODO: maybe use a more meaningful comment
            )
        )

        current_summary = issue.fields.summary
        relevant_fields = {"summary", "description", "fixVersions", "affectsVersions", "status"}

        # Add newer versions from issue changelog if there are relevant changes
        histories = sorted(issue.changelog.histories, key=lambda h: h.created)
        for history in histories:
            summary = current_summary
            changed_fields = []
            for item in history.items:
                if item.field == "summary":
                    summary = item.toString or current_summary
                changed_fields.append(item.field)

            relevant_change = any(field in relevant_fields for field in changed_fields)
            if relevant_change:
                versions.append(
                    RequirementVersionObject(
                        name=summary,
                        date=history.created,
                        author=history.author.displayName,
                        comment=self._get_change_comment(history),
                    )
                )

        return versions

    # TODO: Maybe extract a comment that is more meaningful; Different Languages ?
    def _get_change_comment(self, history) -> str:
        changed_fields = [item.field for item in history.items]
        if "summary" in changed_fields and "description" in changed_fields:
            return "Summary and Description updated"
        elif "summary" in changed_fields:
            return "Summary updated"
        elif "description" in changed_fields:
            return "Description updated"
        else:
            return f"Fields updated: {', '.join(changed_fields)}"

    @staticmethod
    def sort_by_issue_key(issue: Issue):
        try:
            return int(issue.key.split("-")[-1])
        except (AttributeError, ValueError, IndexError):
            return float("inf")  # Push invalid/malformed keys to the end

    def _load_config_dict_from_path(self, config_path: Path) -> dict[str, str]:
        if not config_path.exists():
            raise FileNotFoundError(f"Reader config file not found at: '{config_path.resolve()}'")

        try:
            with config_path.open("rb") as config_file:
                config_dict = tomllib.load(config_file)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Failed to parse TOML in reader config file: {e}") from e

        return config_dict

    def _load_and_validate_config_from_path(self, config_path: Path) -> JiraRequirementReaderConfig:
        config_dict = self._load_config_dict_from_path(config_path)

        config_prefix = "jira"
        if config_prefix not in config_dict:
            raise ValueError(f"TOML section [{config_prefix}] not found in reader config file.")

        try:
            return JiraRequirementReaderConfig(**config_dict[config_prefix])
        except ValidationError as e:
            error_message = "; ".join([err["msg"] for err in e.errors()])
            raise ValueError(f"Invalid reader config: {error_message}") from e

    def _connect(self) -> JIRA:
        if self.config.auth_type == "basic":
            return JIRA(
                server=self.config.server_url,
                basic_auth=(self.config.username, self.config.api_token),
            )
        elif self.config.auth_type == "token":
            return JIRA(server=self.config.server_url, token_auth=self.config.token)
        elif self.config.auth_type == "oauth":
            return JIRA(
                oauth={
                    "access_token": self.config.access_token,
                    "access_token_secret": self.config.access_token_secret,
                    "consumer_key": self.config.consumer_key,
                    "key_cert": self.config.key_cert,
                }
            )
        else:
            raise NotImplementedError(f"Unsupported auth_type {self.config.auth_type}")

    def _fetch_projects(self):
        self._projects = {
            f"{project.name} ({project.key})": project for project in self.jira.projects()
        }

    def _fetch_baselines_for_project(self, project: str) -> list[str]:
        project_key = self.projects[project].key
        issue_fields = self._fetch_project_issue_fields(project_key)
        for field in issue_fields:
            if hasattr(field, "key"):
                field_id = field.key
            elif hasattr(field, "fieldId"):
                field_id = field.fieldId
            else:
                field_id = field.name
                logging.warning(
                    f"Field {field.name} has no key or fieldId.\n"
                    f"  dir: {dir(field)}\n"
                    f"  type: {type(field)}"
                )
            if self.config.baseline_field in (field.name, field_id):
                self._baselines[project] = self._extract_baselines_from_issue_field(field)
                return self._baselines[project]
        self.logger.warning(f"Field {self.config.baseline_field} not found in project {project}")
        return []

    def _get_baselines_for_project(self, project: str) -> list[str]:
        if not self._baselines or project not in self._baselines:
            # Cache miss: fetch baselines
            self._fetch_baselines_for_project(project)
        return self._baselines.get(project, [])

    def _extract_baselines_from_issue_field(self, field: Field) -> list[str]:
        baselines = []
        for value in field.allowedValues:
            if hasattr(value, "name"):
                baselines.append(value.name)
            elif hasattr(value, "value"):
                baselines.append(value.value)
            else:
                self.logger.debug(f"Unknown allowed value format: {value} {type(value)}")
        return baselines

    def _fetch_project_issue_fields(self, project_key: str) -> list[Field]:
        issue_fields: dict[str, Field] = {}

        try:
            if self.uses_new_issuetypes_endpoint:
                self.logger.debug("_fetch_project_issue_fields: Use new issuetypes endpoint")
                issue_types = self.jira.project_issue_types(project_key, maxResults=100)
                for issue_type in issue_types:
                    try:
                        issue_fields = self.jira.project_issue_fields(
                            project_key, issue_type=issue_type.id, maxResults=100
                        )
                        for field in issue_fields:
                            issue_fields[field.id] = field
                    except Exception as e:
                        self.logger.warning(
                            f"Error fetching issue fields for issue type {issue_type.id}"
                        )
                        self.logger.debug(e)
            else:
                self.logger.debug("_fetch_project_issue_fields: Use old createmeta endpoint")
                createmeta = self.jira.createmeta(project_key, expand="projects.issuetypes.fields")
                issue_types = createmeta["projects"][0]["issuetypes"]
                for issue_type in issue_types:
                    for field_id, field_data in issue_type["fields"].items():
                        issue_fields[field_id] = Field(
                            {}, session=self.jira._session, raw=field_data
                        )
        except Exception as e:
            self.logger.error(f"Error fetching issue fields for project {project_key}")
            raise e

        return list(issue_fields.values())

    def _embed_jira_images(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        img_tags = soup.find_all("img")
        for img in img_tags:
            src = img.get("src", "")
            if src.startswith("/images/"):
                img["src"] = f"{self.jira.server_url}{src}"
                continue
            match = re.search(r"/rest/api/\d+/attachment/content/(\d+)", src)
            if not match:
                continue
            attachment_id = match.group(1)
            try:
                attachment = self.jira.attachment(attachment_id)
                mime_type = attachment.mimeType
                image_bytes = attachment.get()
                encoded = base64.b64encode(image_bytes).decode("utf-8")
                img["src"] = f"data:{mime_type};base64,{encoded}"
            except Exception as e:
                print(f"Warning: Could not embed attachment {attachment_id} - {e}")
                continue
        return str(soup)

    def _fetch_issue(
        self,
        issue_id: str,
        fields: str | None = None,
        expand: str | None = None,
        properties: str | None = None,
    ):
        """Fetch an issue from Jira."""
        return self.jira.issue(issue_id, fields=fields, expand=expand, properties=properties)

    def _normalize_field_for_jql(self, field_name: str) -> str:
        """
        Normalize Jira field names to their canonical JQL equivalents.

        Currently handles known special cases like converting 'fixVersions' to 'fixVersion'.

        Args:
            field_name (str): The field name to normalize.

        Returns:
            str: The normalized field name for JQL queries.
        """
        if field_name.lower() == "fixversions":
            return "fixVersion"
        return field_name

    def _fetch_issues(self, project: str, baseline: str) -> list[Issue]:
        """Fetch issues from Jira depending on API mode."""

        project_key = self.projects[project].key
        baseline_field = self._normalize_field_for_jql(self.config.baseline_field)

        if baseline == "Current Baseline":
            jql_query = f'project = "{project_key}"'
        else:
            jql_query = f'project = "{project_key}" AND {baseline_field} = "{baseline}"'

        fields = "*all"

        if not self.uses_manual_pagination:
            return list(self.jira.search_issues(jql_query, maxResults=False, fields=fields))

        # Manual pagination for older Jira Server versions
        issues: list[Issue] = []
        start_at = 0
        maxResults = 1000
        while True:
            chunk: ResultList[Issue] = self.jira.search_issues(
                jql_query,
                startAt=start_at,
                maxResults=maxResults,
                fields=fields,
            )
            issues.extend(chunk)
            if len(chunk) < maxResults:
                # No more pages
                break
            start_at += maxResults
        return issues

    def _extract_valuetype_from_issue_field(
        self,
        field: dict[str, Any],
    ) -> Literal["STRING", "ARRAY", "BOOLEAN"]:
        schema = field.get("schema", {})
        field_type = schema.get("type")
        if field_type == "array":
            return "ARRAY"
        elif field_type == "boolean":
            return "BOOLEAN"
        else:
            return "STRING"

    def _build_userdefinedattribute_object(
        self, field: dict[str, Any], field_value: Any
    ) -> UserDefinedAttribute:
        value_type = self._extract_valuetype_from_issue_field(field)
        if value_type == "STRING":
            if hasattr(field_value, "value"):
                string_value = field_value.value
            elif hasattr(field_value, "name"):
                string_value = field_value.name
            else:
                string_value = str(field_value)
            return UserDefinedAttribute(
                name=field["name"],
                valueType="STRING",
                stringValue=string_value,
            )
        elif value_type == "ARRAY":
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
        elif value_type == "BOOLEAN":
            return UserDefinedAttribute(
                name=field["name"],
                valueType="BOOLEAN",
                booleanValue=bool(field_value),
            )

    def _build_requirementobject_from_issue(
        self, issue: Issue, requirement: bool = True
    ) -> RequirementObjectNode:
        return RequirementObjectNode(
            name=issue.fields.summary,
            extendedID=issue.key,
            key=RequirementKey(id=issue.key, version="1.0"),
            owner=issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
            status=issue.fields.status.name,
            priority=getattr(issue.fields.priority, "name", ""),
            requirement=requirement,
            children=[],
        )

    def _build_requirement_nodes(self, issues: list[Issue]) -> dict[str, RequirementObjectNode]:
        """Convert issues into requirement nodes."""
        requirement_nodes = {}
        for issue in issues:
            req_node = self._build_requirementobject_from_issue(issue)
            requirement_nodes[issue.key] = req_node
        return requirement_nodes

    def _build_requirement_tree(
        self, issues: list[Issue], requirement_nodes: dict[str, RequirementObjectNode]
    ) -> dict[str, RequirementObjectNode]:
        """Link requirement nodes into a tree structure."""
        requirement_tree = {}
        try:
            for issue in issues:
                parent_key = getattr(issue.fields, "parent", None)
                if not parent_key:
                    requirement_tree[issue.key] = requirement_nodes[issue.key]
                    continue

                parent_key = parent_key.key
                if parent_key not in requirement_nodes:
                    parent_issue = self.jira.issue(parent_key)
                    parent = self._build_requirementobject_from_issue(
                        parent_issue, requirement=False
                    )
                    requirement_nodes[parent_key] = parent

                parent = requirement_nodes[parent_key]
                parent.children.append(requirement_nodes[issue.key])

                if parent_key not in requirement_tree:
                    requirement_tree[parent_key] = parent
        except Exception as e:
            self.logger.error(f"Error building requirement tree: {e}")

        return requirement_tree

    def _build_rich_description(self, issue) -> str:
        """Render Jira description into an HTML body."""
        description = getattr(issue.renderedFields, "description", "") or ""
        html = f"<html><body>{self._embed_jira_images(description)}</body></html>"

        return html
