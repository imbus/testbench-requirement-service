# mypy: ignore-errors
# ruff: noqa

import base64
import copy
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Literal

from sanic import NotFound

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from bs4 import BeautifulSoup
from jira import JIRA, Issue, JIRAError, Project
from jira.resources import Field
from pydantic import BaseModel, ValidationError, model_validator
from pydantic.fields import Field as ModelField

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

MINOR_CHANGE_FIELDS = {"summary", "description", "affectsVersions", "status"}
MAJOR_CHANGE_FIELDS = {"fixVersions"}


class JiraProjectConfig(BaseModel):
    requirement_types: list[str] | None = None
    requirement_group_types: list[str] | None = None


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
    requirement_types: list[str] = ["Story", "Task"]
    requirement_group_types: list[str] = ["Epic"]

    projects: dict[str, JiraProjectConfig] = ModelField(default_factory=dict)

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
            self.access_token = self.access_token or os.getenv("JIRA_ACCESS_TOKEN")
            self.access_token_secret = self.access_token_secret or os.getenv(
                "JIRA_ACCESS_TOKEN_SECRET"
            )
            self.consumer_key = self.consumer_key or os.getenv("JIRA_CONSUMER_KEY")
            self.key_cert = self.key_cert or os.getenv("JIRA_KEY_CERT")
            if not self.access_token:
                raise ValueError(
                    "Jira Access Token must be provided for OAuth (via config or JIRA_ACCESS_TOKEN env)"
                )
            if not self.access_token_secret:
                raise ValueError(
                    "Jira Access Token Secret must be provided for OAuth (via config or JIRA_ACCESS_TOKEN_SECRET env)"
                )
            if not self.consumer_key:
                raise ValueError(
                    "Jira consumer key must be provided for OAuth (via config or JIRA_CONSUMER_KEY env)"
                )
            if not self.key_cert:
                raise ValueError(
                    "Jira Private Key must be provided for OAuth (via config or JIRA_KEY_CERT env)"
                )

        return self


class JiraRequirementReader(AbstractRequirementReader):
    def __init__(self, config_path: str):
        self.logger = logging.getLogger(__name__)
        self.logger.level = logging.DEBUG

        self.config = self._load_and_validate_config_from_path(Path(config_path))

        self.jira = self._connect()
        # The following flags determine which Jira API endpoints to use
        self.use_new_issuetypes_endpoint = (not self.jira._is_cloud) and (
            self.jira._version >= (8, 4, 0)
        )
        self.use_manual_pagination = not self.jira._is_cloud and self.jira._version < (8, 4, 0)

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
        now = datetime.now(timezone.utc)
        return [
            BaselineObject(
                name="Current Baseline",
                date=now,
                type="CURRENT",
            ),
            *[
                BaselineObject(
                    name=baseline,
                    date=now,
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
        requirement_nodes = self._build_requirement_nodes(issues, project)
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
        return [
            UserDefinedAttribute(
                name=field["name"],
                valueType=self._extract_valuetype_from_issue_field(field),
            )
            for field in self._fetch_all_custom_fields()
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

        custom_fields = self._fetch_all_custom_fields()
        fields = [field for field in custom_fields if field["name"] in attribute_names]
        field_ids = [field["id"] for field in fields]

        issue_keys = [req_key.id for req_key in requirement_keys]
        extra_jql = f"issuekey IN ({','.join(issue_keys)})"

        issues = self._fetch_issues(
            project,
            baseline,
            fields=["key"] + field_ids,
            extra_jql=extra_jql,
        )
        issue_map = {issue.key: issue for issue in issues}

        user_defined_attributes: list[UserDefinedAttributeResponse] = []
        for req_key in requirement_keys:
            issue = issue_map.get(req_key.id)
            if not issue:
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
        fields = "summary,creator,assignee,status,priority,description,issuetype,attachment"
        issue = self._fetch_issue(
            key.id,
            project=project,
            baseline=baseline,
            fields=fields,
            expand="renderedFields,changelog",
        )
        return self._build_extendedrequirementobject_from_issue(issue, key, baseline)

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        issue = self._fetch_issue(
            key.id,
            project=project,
            baseline=baseline,
            fields="summary,created,creator",
            expand="changelog",
        )

        return self._generate_requirement_versions(issue)

    def _generate_requirement_versions(self, issue:Issue):
        versions = []
        minor = 0
        major = 1 
        # Add creation as the initial version
        versions.append(
            RequirementVersionObject(
                name=f"{major}.{minor}",
                date=issue.fields.created,
                author=getattr(issue.fields.creator, "displayName", "Unknown"),
                comment="Initial version",  # TODO: maybe use a more meaningful comment
            )
        )

        histories = sorted(issue.changelog.histories, key=lambda h: h.created)
        for history in histories:
            changed_fields = {item.field for item in getattr(history, "items", [])}

            is_major = bool(MAJOR_CHANGE_FIELDS & changed_fields)
            is_minor = bool(MINOR_CHANGE_FIELDS & changed_fields)

            if is_major:
                major += 1
                minor = 0
                versions.append(
                    RequirementVersionObject(
                    name=f"{major}.{minor}",
                    date=history.created,
                    author=getattr(history.author, "displayName", "Unknown"),
                    comment=self._get_change_comment(history),
                    )
                )
            elif is_minor:
                minor += 1
                versions.append(
                    RequirementVersionObject(
                    name=f"{major}.{minor}",
                    date=history.created,
                    author=getattr(history.author, "displayName", "Unknown"),
                    comment=self._get_change_comment(history),
                    )
                )
        return versions
            

    # TODO: Maybe different languages?
    def _get_change_comment(self, history) -> str:
        changes = []
        for item in history.items:
            from_val = item.fromString if hasattr(item, "fromString") else ""
            to_val = item.toString if hasattr(item, "toString") else ""
            changes.append(f"{item.field}: '{from_val}' → '{to_val}'")
        comment = "; ".join(changes) if changes else "Fields updated"
        return comment

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

        project_configs = config_dict["projects"] if "projects" in config_dict else {}

        try:
            return JiraRequirementReaderConfig(
                **config_dict[config_prefix], projects=project_configs
            )
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

    def _fetch_projects(self) -> list:
        self._projects = {
            f"{project.name} ({project.key})": project for project in self.jira.projects()
        }

    def _fetch_project_issue_fields(self, project_key: str) -> list[Field]:
        fields_dict: dict[str, Field] = {}

        try:
            if self.use_new_issuetypes_endpoint:
                self.logger.debug("_fetch_project_issue_fields: Use new issuetypes endpoint")
                issue_types = self.jira.project_issue_types(project_key, maxResults=100)
                for issue_type in issue_types:
                    try:
                        fields_list = self.jira.project_issue_fields(
                            project_key, issue_type=issue_type.id, maxResults=100
                        )
                        for field in fields_list:
                            fields_dict[field.id] = field
                    except Exception as e:
                        self.logger.warning(
                            f"Error fetching issue fields for issue type {issue_type.id}: {e}"
                        )
            else:
                self.logger.debug("_fetch_project_issue_fields: Use old createmeta endpoint")
                createmeta = self.jira.createmeta(project_key, expand="projects.issuetypes.fields")
                issue_types = createmeta["projects"][0]["issuetypes"]
                for issue_type in issue_types:
                    for field_id, field_data in issue_type["fields"].items():
                        fields_dict[field_id] = Field(
                            options=self.jira._options, session=self.jira._session, raw=field_data
                        )
        except Exception as e:
            self.logger.error(f"Error fetching issue fields for project {project_key}: {e}")
            raise

        return list(fields_dict.values())

    def _get_field_id(self, field):
        for attr in ("id", "key", "fieldId"):
            if hasattr(field, attr):
                return getattr(field, attr)
        self.logger.warning(f"Field {field.name} has no id, key, or fieldId.")
        return field.name

    def _is_version_type_field(self, field: Field) -> bool:
        schema_type = getattr(field.schema, "type", None)
        items_type = getattr(field.schema, "items", None)
        return schema_type == "version" or (schema_type == "array" and items_type == "version")

    def _fetch_baseline_field(self, project_key: str) -> Field | None:
        issue_fields = self._fetch_project_issue_fields(project_key)
        for field in issue_fields:
            field_id = self._get_field_id(field)
            if self.config.baseline_field in (field_id, field.name):
                return field
        self.logger.warning(
            f"Configured baseline_field '{self.config.baseline_field}' not found in project {project_key}"
        )
        return None

    def _fetch_project_versions(self, project_key: str) -> list[str]:
        try:
            versions = self.jira.project_versions(project_key)
            if not versions:
                return []
            return [version.name for version in versions if version.name]
        except Exception as e:
            self.logger.error(f"Error fetching project versions for {project_key}: {e}")
            return []

    def _fetch_baselines_for_project(self, project: str) -> list[str]:
        project_key = self.projects[project].key
        baselines = self._fetch_project_versions(project_key)
        self._baselines[project] = baselines
        return baselines

    def _get_baselines_for_project(self, project: str) -> list[str]:
        if not self._baselines or project not in self._baselines:
            # Cache miss: fetch baselines
            self._fetch_baselines_for_project(project)
        return self._baselines.get(project, [])

    def _fetch_all_custom_fields(self) -> list[dict[str, Any]]:
        return [
            field for field in self.jira.fields() if field.get("id", "").startswith("customfield_")
        ]

    def _embed_jira_images(self, issue: Issue) -> str:
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
        """
        allowed_image_mime_types = {"image/png", "image/jpeg", "image/gif"}
        max_embedded_image_size = 5 * 1024 * 1024  # 5 MB limit for embedded images
        jira_attachment_url_pattern = re.compile(r"^/rest/api/\d+/attachment/content/(\d+)$")

        description = getattr(issue.renderedFields, "description", "")
        if not description:
            self.logger.warning(f"Issue {issue.key} missing renderedFields.description")
            return ""

        # Build attachment dictionary mapping attachment ID to tuple (mime type, encoded data)
        attachment_dict: dict[str, tuple[str, str]] = {}
        attachments = getattr(issue.fields, "attachment", [])
        for attachment in attachments:
            try:
                mime_type = getattr(attachment, "mimeType", None)
                if not mime_type:
                    self.logger.warning(f"Attachment {attachment.id} missing mimeType metadata")
                    continue
                if mime_type not in allowed_image_mime_types:
                    self.logger.warning(
                        f"Attachment {attachment.id} has disallowed mimeType: {mime_type}"
                    )
                    continue

                size = getattr(attachment, "size", None)
                if size and size > max_embedded_image_size:
                    self.logger.warning(
                        f"Attachment {attachment.id} size ({size} bytes) exceeds "
                        f"maximum allowed size ({max_embedded_image_size} bytes)"
                    )
                    continue

                image_bytes = attachment.get()

                actual_size = len(image_bytes)
                if actual_size > max_embedded_image_size:
                    self.logger.warning(
                        f"Attachment {attachment.id} size ({size} bytes) exceeds "
                        f"maximum allowed size ({max_embedded_image_size} bytes)"
                    )
                    continue

                encoded = base64.b64encode(image_bytes).decode("utf-8")
                attachment_dict[attachment.id] = (mime_type, encoded)
                self.logger.debug(
                    f"Successfully processed attachment {attachment_id} ({len(image_bytes)} bytes)"
                )
            except Exception as e:
                self.logger.debug(f"Could not process attachment {attachment.id}: {e}")
                continue

        # Embed images in the issue description
        soup = BeautifulSoup(description, "html.parser")
        img_tags = soup.find_all("img")
        for img in img_tags:
            src = img.get("src", "")
            if src.startswith("/images/"):
                img["src"] = f"{self.jira.server_url}{src}"
                continue

            match = jira_attachment_url_pattern.fullmatch(src)
            if not match:
                img.attrs.pop("src", None)
                self.logger.warning(f"Removed image with unsupported src: {src}")
                continue

            attachment_id = match.group(1)
            if attachment_id not in attachment_dict:
                img.attrs.pop("src", None)
                self.logger.warning(
                    f"Attachment {attachment_id} not found in validated attachments"
                )
                continue

            mime_type, encoded = attachment_dict[attachment_id]
            img["src"] = f"data:{mime_type};base64,{encoded}"

        # TODO: Sanitize HTML to prevent XSS if necessary
        return str(soup)

    def _fetch_issue(
        self,
        issue_id: str,
        project: str | None = None,
        baseline: str | None = None,
        fields: str | None = None,
        expand: str | None = None,
        properties: str | None = None,
    ) -> Issue:
        """
        Fetch an issue from Jira.

        Args:
            issue_id (str): The Jira issue key or ID to fetch.
            project (str | None, optional): The project name as used in self.projects; if provided, verifies the issue belongs to this project.
            baseline (str | None, optional): The baseline name; if provided, verifies the issue is part of this baseline.
            fields (str | None, optional): Comma-separated list of fields to fetch for the issue.
            expand (str | None, optional): Comma-separated list of fields to expand in the response.
            properties (str | None, optional): Comma-separated list of properties to fetch for the issue.

        Returns:
            Issue: The Jira issue object.

        Raises:
            NotFound: If the issue does not exist, or does not belong to the specified project/baseline, or is not a requirement type.
        """
        try:
            if fields and fields != "*all":
                if project:
                    fields += ",project"
                if baseline:
                    fields += f",{self.config.baseline_field}"
                fields += ",issuetype"
                fields = ",".join(list(set(field.strip() for field in fields.split(","))))
            issue = self.jira.issue(issue_id, fields=fields, expand=expand, properties=properties)
        except JIRAError as e:
            self.logger.debug(f"Error fetching issue {issue_id}: {e}")
            raise NotFound("Requirement not found") from e

        # If project is specified, check if the issue belongs to the specified project
        if project:
            project_key = self.projects[project].key
            if issue.fields.project.key != project_key:
                raise NotFound("Requirement not found")

        # If baseline is specified, check if the issue belongs to the specified baseline
        if baseline:
            issue_baselines = self._extract_baselines_from_issue(issue)
            if baseline != "Current Baseline" and baseline not in issue_baselines:
                raise NotFound("Requirement not found")

        # Check if the issue is a requirement type or requirement group type
        is_requirement = self._is_requirement_issue(issue, project)
        is_requirement_group = self._is_requirement_group_issue(issue, project)
        if not is_requirement and not is_requirement_group:
            raise NotFound("Requirement not found")

        return issue

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

    def _fetch_issues(
        self,
        project: str,
        baseline: str,
        extra_jql: str | None = None,
        fields: str | None = "*all",
        expand: str | None = None,
        properties: str | None = None,
    ) -> list[Issue]:
        """Fetch issues from Jira depending on API mode."""

        project_key = self.projects[project].key
        baseline_field = self._normalize_field_for_jql(self.config.baseline_field)

        if baseline == "Current Baseline":
            jql_query = f'project = "{project_key}"'
        else:
            jql_query = f'project = "{project_key}" AND {baseline_field} = "{baseline}"'

        requirement_types = self._get_requirement_types(project)
        requirement_group_types = self._get_requirement_group_types(project)
        issuetypes = requirement_types + requirement_group_types
        issuetype_str = ",".join(f'"{issuetype}"' for issuetype in issuetypes)
        jql_query += f" AND issuetype IN ({issuetype_str})"

        if extra_jql:
            jql_query += f" AND {extra_jql}"

        try:
            if not self.use_manual_pagination:
                return list(
                    self.jira.search_issues(
                        jql_query,
                        maxResults=1000,
                        fields=fields,
                        expand=expand,
                        properties=properties,
                    )
                )
            # Manual pagination for older Jira Server versions
            start_at = 0
            maxResults = 1000
            issues: list[Issue] = []
            while True:
                chunk = self.jira.search_issues(
                    jql_query,
                    startAt=start_at,
                    maxResults=maxResults,
                    fields=fields,
                    expand=expand,
                    properties=properties,
                )
                issues.extend(chunk)
                if len(chunk) < maxResults:
                    # No more pages
                    break
                start_at += maxResults
            return issues
        except JIRAError as e:
            self.logger.error(f"Error fetching issues: {e}")
            return []

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
                string_value = str(field_value) if field_value else None
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
        
    def _get_issue_version(self, issue: Issue, key: RequirementKey) -> Issue:
        """
        Reconstructs the issue's fields to reflect their state at the specified version.
        Modifies the issue object in-place.

        Args:
            issue (Issue): The Jira issue object.
            key (RequirementKey): The requirement key containing the target version.

        Returns:
            Issue: The issue object with fields set to the specified version.
        """
        if key is None or key.version == "current":
            return issue

        try:
            target_major, target_minor = map(int, key.version.split("."))
        except Exception as e:
            self.logger.error(f"Invalid version format '{key.version}' for requirement key '{key.id}': {e}")
            raise ValueError(f"Invalid version format '{key.version}' for requirement key '{key.id}'. Expected format 'major.minor'.") from e

        issue_copy = copy.deepcopy(issue)

        histories = sorted(getattr(issue_copy.changelog, "histories", []), key=lambda h: h.created)
        major = 1
        minor = 0
        updated_fields = set()

        for history in histories:
            changed_fields = {item.field for item in getattr(history, "items", [])}

            is_major = bool(MAJOR_CHANGE_FIELDS & changed_fields)
            is_minor = bool(MINOR_CHANGE_FIELDS & changed_fields)

            # If we've reached or passed the target version, revert fields to their previous values
            if (major > target_major) or (major == target_major and minor >= target_minor):
                for item in getattr(history, "items", []):
                    if item.field in changed_fields and item.field not in updated_fields:
                        self._set_issue_field(issue_copy, item.field, item.fromString)
                        updated_fields.add(item.field)
            else:
                for item in getattr(history, "items", []):
                    if item.field in changed_fields:
                        self._set_issue_field(issue_copy, item.field, item.toString)
                        updated_fields.add(item.field)

            if is_major:
                major += 1
                minor = 0
            elif is_minor:
                minor += 1
        
        if major ==  target_major and minor == target_minor:
            return issue

        return issue_copy

    def _set_issue_field(self, issue: Issue, field_name: str, value: Any) -> None:
        """
        Helper to set a field value on the issue.fields object, handling nested attributes.
        """
        if hasattr(issue.renderedFields, field_name):
            if (field_name == "description"):
                value = self._format_description(value)
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

    def _build_requirementobjectnode_from_issue(
        self, issue: Issue, key: RequirementKey | None = None, is_requirement: bool = True
    ) -> RequirementObjectNode:
        assignee = getattr(issue.fields, "assignee", None)
        creator = getattr(issue.fields, "creator", None)
        owner = ""
        if assignee and getattr(assignee, "displayName", None) != None:
            owner = assignee.displayName
        elif creator and getattr(creator, "displayName", None) != None:
            owner = creator.displayName
            

        status_field = getattr(issue.fields, "status", None)
        status = status_field.name if status_field else ""

        priority_field = getattr(issue.fields, "priority", None)
        priority = priority_field.name if priority_field else ""

        return RequirementObjectNode(
            name=getattr(issue.fields, "summary", ""),
            extendedID=issue.key,
            key=key or RequirementKey(id=issue.key, version="current"),
            owner=owner,
            status=status,
            priority=priority,
            requirement=is_requirement,
            children=[],
        )

    def _build_requirement_nodes(
        self, issues: list[Issue], project: str
    ) -> dict[str, RequirementObjectNode]:
        """Convert issues into requirement nodes."""
        requirement_nodes = {}
        for issue in issues:
            is_requirement = self._is_requirement_issue(issue, project)
            req_node = self._build_requirementobjectnode_from_issue(
                issue, is_requirement=is_requirement
            )
            requirement_nodes[issue.key] = req_node
        return requirement_nodes

    def _build_requirement_tree(
        self, issues: list[Issue], requirement_nodes: dict[str, RequirementObjectNode]
    ) -> dict[str, RequirementObjectNode]:
        """Link requirement nodes into a tree structure."""
        requirement_tree = {}

        try:
            for issue in issues:
                parent_obj = getattr(issue.fields, "parent", None)
                if not parent_obj:
                    requirement_tree[issue.key] = requirement_nodes[issue.key]
                    continue

                parent_key = parent_obj.key
                if parent_key not in requirement_nodes:
                    self.logger.warning(
                        f"Parent issue {parent_key} of issue {issue.key} not found among fetched issues"
                    )
                    continue

                parent = requirement_nodes[parent_key]
                parent.children = parent.children or []
                parent.children.append(requirement_nodes[issue.key])
        except Exception as e:
            self.logger.error(f"Error building requirement tree: {e}")
            return {}

        return requirement_tree

    def _build_rich_description(self, issue: Issue) -> str:
        """
        Render Jira issue description with embedded images inside a full HTML body.
        """
        description_html = self._embed_jira_images(issue)
        return f"<html><body>{description_html}</body></html>"

    def _build_extendedrequirementobject_from_issue(
        self, issue: Issue, key: RequirementKey, baseline: str
    ) -> ExtendedRequirementObject:
        issue = self._get_issue_version(issue, key)
        requirement_object = self._build_requirementobjectnode_from_issue(
            issue, key
        )  # TODO: set is_requirement properly

        attachments_field = getattr(issue.fields, "attachment", None)
        if attachments_field:
            attachments = [
                attachment.content for attachment in attachments_field if attachment.content
            ]
        else:
            attachments = []

        return ExtendedRequirementObject(
            **requirement_object.model_dump(),
            description=self._build_rich_description(issue),
            documents=[issue.permalink(), *attachments],
            baseline=baseline,
        )

    def _extract_baselines_from_issue(self, issue) -> list[str]:
        value = getattr(issue.fields, self.config.baseline_field, None)
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

    def _get_requirement_types(self, project: str | None = None) -> list[str]:
        if project and project in self.config.projects:
            project_config = self.config.projects[project]
            if project_config.requirement_types is not None:
                return project_config.requirement_types
        return self.config.requirement_types

    def _get_requirement_group_types(self, project: str | None = None) -> list[str]:
        if project and project in self.config.projects:
            project_config = self.config.projects[project]
            if project_config.requirement_group_types is not None:
                return project_config.requirement_group_types
        return self.config.requirement_group_types

    def _is_requirement_issue(self, issue: Issue, project: str | None = None) -> bool:
        return issue.fields.issuetype.name in self._get_requirement_types(project)

    def _is_requirement_group_issue(self, issue: Issue, project: str | None = None) -> bool:
        return issue.fields.issuetype.name in self._get_requirement_group_types(project)

    def _format_description(self, description: str) -> str:
        return "<p>" + description.replace('\n\n', '</p><p>')+ "</p>"
