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
from jira import JIRA, Project
from jira.client import ResultList
from jira.resources import Resource, Field
from pydantic import BaseModel, ValidationError, model_validator
from sanic.exceptions import NotFound

from testbench_requirement_service.models.requirement import (
    BaselineObject,
    BaselineObjectNode,
    ExtendedRequirementObject,
    RequirementKey,
    RequirementObjectNode,
    RequirementVersionObject,
    UserDefinedAttribute,
    RequirementUserDefinedAttributes,
)
from testbench_requirement_service.readers.abstract_file_reader import AbstractFileReader


def is_dict_like(item):
    return isinstance(item, Mapping)


class DotDict(OrderedDict):
    def __init__(self, *args, **kwds):
        args = [self._convert_nested_initial_dicts(a) for a in args]
        kwds = self._convert_nested_initial_dicts(kwds)
        OrderedDict.__init__(self, *args, **kwds)

    def _convert_nested_initial_dicts(self, value):
        items = value.items() if is_dict_like(value) else value
        return OrderedDict((key, self._convert_nested_dicts(value)) for key, value in items)

    def _convert_nested_dicts(self, value):
        if isinstance(value, DotDict):
            return value
        if is_dict_like(value):
            return DotDict(value)
        if isinstance(value, list):
            value[:] = [self._convert_nested_dicts(item) for item in value]
        return value

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(key) from e

    def __setattr__(self, key, value):
        if not key.startswith("_OrderedDict__"):
            self[key] = value
        else:
            OrderedDict.__setattr__(self, key, value)

    def __delattr__(self, key):
        try:
            self.pop(key)
        except KeyError:
            OrderedDict.__delattr__(self, key)

    def __eq__(self, other):
        return dict.__eq__(self, other)

    def __ne__(self, other):
        return not self == other

    def __str__(self):
        return "{{{}}}".format(", ".join(f"{key!r}: {self[key]!r}" for key in self))

    # Must use original dict.__repr__ to allow customising PrettyPrinter.
    __repr__ = dict.__repr__


class JiraRestReaderConfig(BaseModel):
    server_url: str
    auth_type: Literal["basic", "token", "oauth"] = "basic"
    username: str | None = None
    api_token: str | None = None  # for basic auth, paired with username
    token: str | None = None  # for bearer/token-based auth, Jira Self Hosted

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
            pass  # TODO: implement oauth
        return self


class JiraRestReader(AbstractFileReader):
    def __init__(self, config_path: str):
        self.logger = logging.getLogger(__name__)
        self.logger.level = logging.DEBUG

        self.config = self._load_and_validate_config_from_path(Path(config_path))
        self.jira = self._connect()

        # key: project name (format: "{project.name} ({project.key})"), value: Project Resource
        self._projects: dict[str, Project] = {}
        # key: project name (format: "{project.name} ({project.key})"), value: list of project baselines as str
        self._baselines: dict[str, list[str]] = {}

        self._issues: dict[str, Any] = {}
        self._udfs: dict[str, UserDefinedAttribute] = {}

        self.baseline_field = "fixVersions"
        self.jql_query = "project = {project} AND fixVersion = {baseline}"
        self.jql_query_current = "project = {project}"
        self.uses_new_issuetypes_endpoint = (not self.jira._is_cloud) and (
            self.jira._version >= (8, 4, 0)
        )

    @property
    def projects(self) -> dict[str, Project]:
        if not self._projects:
            self._load_projects()
        return self._projects

    def project_exists(self, project: str) -> bool:
        if project in self.projects:
            return True
        # Cache miss: load projects and check again
        self._load_projects()
        return project in self.projects

    def baseline_exists(self, project: str, baseline: str) -> bool:
        if project not in self._baselines:
            # Cache miss: load baselines
            self._load_baselines_for_project(project)
        return baseline in self._baselines[project]

    def get_projects(self) -> list[str]:
        return list(self.projects.keys())

    def get_baselines(self, project: str) -> list[BaselineObject]:
        if project not in self._baselines:
            self._load_baselines_for_project(project)
        baselines = sorted(self._baselines.get(project, []))
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

    # TODO: Refactor
    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        issues = []
        next_page_token = None
        # jql_query = f"project = {self.projects[project]} AND fixVersion = {baseline}"
        if baseline == "Current Baseline":
            jql_query = self.jql_query_current.format(project=self.projects[project])
        else:
            jql_query = self.jql_query.format(project=self.projects[project], baseline=baseline)
        # fields = "summary,status,priority,parent,assignee"
        # udfs = ", ".join([fields, *self._udfs.keys()])
        udfs = "*all"
        if self.uses_new_issuetypes_endpoint:
            while True:
                issues_chunk: ResultList = self.jira.search_issues(
                    jql_str=jql_query,
                    startAt=len(issues),
                    maxResults=1000,
                    fields=udfs,
                )
                print(len(issues_chunk))
                issues.extend(list(issues_chunk))
                if len(issues_chunk) == 0:
                    break
        else:
            while True:
                issues_chunk: ResultList = self.jira.enhanced_search_issues(
                    jql_str=jql_query,
                    nextPageToken=next_page_token,
                    maxResults=1000,
                    fields=udfs,
                )
                print(len(issues_chunk))
                issues.extend(list(issues_chunk))
                next_page_token = issues_chunk.nextPageToken
                if not issues_chunk.nextPageToken:
                    break
        if not issues:
            raise NotFound(f"No issues found for project {project} and baseline {baseline}")
        issues.sort(key=self.sort_by_issue_key)
        requirement_nodes: dict[str, RequirementObjectNode] = {}
        for issue in issues:
            req_node = RequirementObjectNode(
                name=issue.fields.summary,
                extendedID=issue.key,
                key=RequirementKey(id=issue.key, version="1.0"),
                owner=issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
                status=issue.fields.status.name,
                priority=getattr(issue.fields.priority, "name", ""),
                requirement=True,
                children=[],
            )
            self._issues[issue.key] = issue
            requirement_nodes[issue.key] = req_node
        requirement_tree: dict[str, RequirementObjectNode] = {}
        try:
            for issue in issues:
                if hasattr(issue.fields, "parent") and issue.fields.parent:
                    parent_key = issue.fields.parent.key
                    if parent_key not in requirement_nodes:
                        parent_issue = self.jira.issue(parent_key)
                        print(parent_issue.key)
                        parent = RequirementObjectNode(
                            name=parent_issue.fields.summary,
                            extendedID=parent_key,
                            key=RequirementKey(id=parent_key, version="1.0"),
                            owner=parent_issue.fields.assignee.displayName
                            if parent_issue.fields.assignee
                            else "Unassigned",
                            status=parent_issue.fields.status.name,
                            priority=parent_issue.fields.priority.name,
                            requirement=False,
                            children=[],
                        )
                        requirement_nodes[parent_key] = parent
                    else:
                        parent = requirement_nodes[parent_key]
                    if parent.children is None:
                        parent.children = [requirement_nodes[issue.key]]
                    else:
                        parent.children.append(requirement_nodes[issue.key])
                    if parent_key not in requirement_tree:
                        requirement_tree[parent_key] = parent
                else:
                    requirement_tree[issue.key] = requirement_nodes[issue.key]
        except Exception as e:
            self.logger.error(f"Error building requirement tree: {e}")
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
                valueType="ARRAY" if field.get("schema", {}).get("type") == "array" else "STRING",
            )
            for field in self.jira.fields()
            if field.get("id", "").startswith("customfield_")
        ]

    # TODO: Refactor
    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributeResponse]:
        fields = {
            field.get("name"): {
                "id": field["id"],
                "typ": "ARRAY" if field.get("schema", {}).get("type") == "array" else "STRING",
            }
            for field in self.jira.fields()
        }
        user_defined_attributes = []
        for req_key in requirement_keys:
            udas = []
            for field_name in attribute_names:
                name = field_name
                field = fields.get(field_name)
                if field is None:
                    self.logger.warning(f"Field {field_name} not found in Jira fields")
                    continue
                value_type = field.get("typ", "STRING")
                if value_type == "STRING":
                    value = getattr(self._issues[req_key.id].fields, fields[field_name]["id"], None)
                    if value is not None:
                        udas.append(
                            UserDefinedAttribute(
                                name=name,
                                valueType=value_type,
                                stringValue=str(value),
                            )
                        )
                elif value_type == "ARRAY":
                    values = getattr(
                        self._issues[req_key.id].fields, fields[field_name]["id"], None
                    )
                    if values is not None:
                        udas.append(
                            UserDefinedAttribute(
                                name=name,
                                valueType=value_type,
                                stringValues=[str(value) for value in values]
                                if isinstance(values, list)
                                else [str(values)],
                            )
                        )
            udas.append(
                UserDefinedAttribute(
                    name="# finds",
                    valueType="STRING",
                    stringValue="<html><body>Voll <b>Fett</b></body></html>",
                )
            )
            user_defined_attributes.append(
                UserDefinedAttributeResponse(key=req_key, userDefinedAttributes=udas)
            )
        return user_defined_attributes
        # yield UserDefinedAttributes(
        #     key=req_key,
        #     userDefinedAttributes=[
        #         UserDefinedAttribute(
        #             name=field_name,
        #             valueType=fields[field_name]["typ"],
        #             stringValue=str(getattr(
        #                 self._issues[req_key.id].fields, fields[field_name]["id"], None
        #             ))
        #             if fields[field_name]["typ"] == "STRING"
        #             else None,
        #             stringValues=getattr(
        #                 self._issues[req_key.id].fields, fields[field_name]["id"], None
        #             )
        #             if fields[field_name]["typ"] == "ARRAY"
        #             else None,
        #         )
        #         for field_name in attribute_names
        #     ],
        # )

    # TODO: Refactor
    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        issue = self.jira.issue(
            key.id,
            fields="summary,assignee,status,priority,parent,description",
            expand="renderedFields",
        )
        if not issue:
            raise NotFound(f"Issue {key.id} not found")
        description = issue.renderedFields.description or ""
        rich_description = f"<html><body>{self.embed_jira_images(description)}</body></html>"
        Path("desc.html").write_text(rich_description, encoding="utf-8")

        return ExtendedRequirementObject(
            name=issue.fields.summary,
            extendedID=issue.key,
            key=key,
            owner=issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned",
            status=issue.fields.status.name or "",
            priority=getattr(issue.fields.priority, "name", ""),
            requirement=True,
            children=[],
            description=rich_description,
            baseline=baseline,
            documents=[issue.permalink()],
        )

    # TODO: Implement
    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        pass

    @staticmethod
    def sort_by_issue_key(issue):
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

    def _load_and_validate_config_from_path(self, config_path: Path) -> JiraRestReaderConfig:
        config_dict = self._load_config_dict_from_path(config_path)

        config_prefix = "jira"
        if config_prefix not in config_dict:
            raise ValueError(f"TOML section [{config_prefix}] not found in reader config file.")

        try:
            return JiraRestReaderConfig(**config_dict[config_prefix])
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
            raise NotImplementedError("TO BE IMPLEMENTED")  # TODO: implement oauth
        else:
            raise NotImplementedError(f"Unsupported auth_type {self.config.auth_type}")

    def _load_projects(self):
        self._projects = {
            f"{project.name} ({project.key})": project for project in self.jira.projects()
        }

    def _load_baselines_for_project(self, project: str) -> list[str]:
        project_key = self.projects[project].key
        issue_fields = self._get_issue_fields(project_key)
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
            if self.baseline_field in (field.name, field_id):
                self._baselines[project] = self._extract_baselines_from_issue_field(field)
                return self._baselines[project]
        self.logger.warning(f"Field {self.baseline_field} not found in project {project}")
        return []

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

    def _get_issue_fields(self, project_key: str) -> list[Field]:
        issue_fields: dict[str, Field] = {}

        try:
            if self.uses_new_issuetypes_endpoint:
                self.logger.debug("_get_issue_fields: Use new issuetypes endpoint")
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
                self.logger.debug("_get_issue_fields: Use old createmeta endpoint")
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
