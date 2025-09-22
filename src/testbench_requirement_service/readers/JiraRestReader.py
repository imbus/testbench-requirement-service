# mypy: ignore-errors
# ruff: noqa

import base64
import logging
import re
from collections import OrderedDict
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from jira import JIRA
from jira.client import ResultList
from jira.resources import Resource
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
from testbench_requirement_service.utils.helpers import import_module_from_file_path


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


class JiraRestReader(AbstractFileReader):
    def __init__(self, config_path: str):
        self.logger = logging.getLogger(__name__)
        self.logger.level = logging.DEBUG

        self.config = self._load_and_validate_config_from_path(Path(config_path))
        self.config = Path(config_path).read_text("utf-8")
        # self.jira = JIRA(
        #     server="https://testbenchcs.atlassian.net/",
        #     basic_auth=(
        #         "rener@imbus.de",
        #         "ATATT3xFfGF0EgLzDyb57FWbSa0zHyvBoRIKEIY50WVSsfYmaQVMQ0OEQlZcjryPWtUML7PkhJIAjVpN0aUXy23C0Rpab3yCOUoNPBr5C57fMvuRXoT5l4zhJSnV2oJHYz5gNJu2aKydPbiwbe1xf6rZPjCQ7KkP4kPAAob9mdyJEb--O31orLY=A68F303A",
        #     ),
        # )
        # self.jira = JIRA(
        #     server="https://jira.imbus.de/",
        #     token_auth="ODk4MzI3NDU3MDMwOi1ZatfWO2cV7OQxJO8I7C5jSlu1",
        #     timeout=30,
        # )
        self.jira = JIRA(
            server="https://jira-test.imbus.de/",
            token_auth="MjkxNDMxMTk5MTg0Ok4CvSdsCsFdwKv2lJsb+tr5pavf",
        )
        self._projects: dict[str, str] = {}
        self._issues: dict[str, Any] = {}
        self._udfs: dict[str, UserDefinedAttribute] = {}
        self.baselines = {}
        self.baseline_field = "fixVersions"
        self.jql_query = "project = {project} AND fixVersion = {baseline}"
        self.jql_query_current = "project = {project}"
        self.is_new_api = not (self.jira._is_cloud or self.jira._version < (8, 4, 0))

    def project_exists(self, project: str) -> bool:
        return project in self.projects or project in self.get_projects()

    def baseline_exists(self, project: str, baseline: str) -> bool:
        return baseline in self.baselines.get(project, []) or baseline in self.get_baselines(
            project
        )

    @property
    def projects(self) -> dict[str, str]:
        if not self._projects:
            self._projects = {}
            for project in self.jira.projects():
                permissions = self.jira.my_permissions(
                    project.key, permissions="CREATE_ISSUES,BROWSE_PROJECTS"
                ).get("permissions")
                if not permissions:
                    self.logger.debug(f"Permissions not found for project {project.key}")
                    continue
                if not (
                    permissions.get("CREATE_ISSUES").get("havePermission")
                    and permissions.get("BROWSE_PROJECTS").get("havePermission")
                ):
                    self.logger.debug(
                        f"No CREATE_ISSUES or BROWSE_PROJECTS permission for project {project.key}"
                    )
                    continue
                self._projects[f"{project.name} ({project.key})"] = project.key
        return self._projects

    def get_projects(self) -> list[str]:
        self._projects = {}
        self.logger.debug(f"Projects with permissions: {self.projects}")
        return list(self.projects.keys())

    @staticmethod
    def _get_allowed_values(allowed_values: list[dict] | list[Resource]) -> list[str]:
        values = []
        for value in allowed_values:
            if isinstance(value, Resource):
                if hasattr(value, "name"):
                    values.append(value.name)
                elif hasattr(value, "value"):
                    values.append(value.value)
                else:
                    print(f"Unknown allowed value format: {value} {type(value)}")
            elif isinstance(value, dict):
                if "name" in value:
                    values.append(value["name"])
                elif "value" in value:
                    values.append(value["value"])
                else:
                    print(f"Unknown allowed value format: {value}")
        return values

    def get_baselines(self, project: str) -> list[BaselineObject]:
        fields = self._get_fields(self.projects[project])
        for field in fields:
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
            if self.baseline_field in (field.name, field_id) and hasattr(field, "allowedValues"):
                self.baselines[project] = self._get_allowed_values(field.allowedValues)
                baselines = [
                    BaselineObject(
                        name=b,
                        date=datetime.now(timezone.utc),
                        type="UNLOCKED",
                        repositoryID=f"{project}/{b}",
                    )
                    for b in sorted(self.baselines[project])
                ]
                return [
                    BaselineObject(
                        name="Current Baseline",
                        date=datetime.now(timezone.utc),
                        type="CURRENT",
                        repositoryID=f"{project}/Current Baseline",
                    ),
                    *baselines,
                ]
        self.logger.warning(f"Field {self.baseline_field} not found in project {project}")
        return []

    def _get_fields(self, project_key: str) -> list[Resource] | list[DotDict]:
        if self.is_new_api:
            self.logger.debug("get_fields new api")
            fields = {}
            try:
                for issue_type in self.jira.project_issue_types(project_key, maxResults=100):
                    try:
                        for field in self.jira.project_issue_fields(
                            project_key, issue_type=issue_type.id, maxResults=100
                        ):
                            fields[field.fieldId] = field
                    except Exception as e:
                        self.logger.warning(f"Error fetching fields for issue type {issue_type.id}")
                        self.logger.debug(e)
                return list(fields.values())
            except Exception as e:
                self.logger.error(f"Error fetching fields for project {project_key}")
                raise e
        self.logger.debug("get_fields old api")
        return list(
            {
                field.fieldId: field
                for issuetype in DotDict(
                    self.jira.createmeta(project_key, expand="projects.issuetypes.fields")
                )
                .projects[0]
                .issuetypes
                for field in issuetype.fields.values()
            }.values()
        )

    @staticmethod
    def sort_by_issue_key(issue):
        try:
            return int(issue.key.split("-")[-1])
        except (AttributeError, ValueError, IndexError):
            return float("inf")  # Push invalid/malformed keys to the end

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
        if self.is_new_api:
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
            repositoryID=f"{project}/{baseline}",
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
        ]

    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[RequirementUserDefinedAttributes]:
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
                RequirementUserDefinedAttributes(key=req_key, userDefinedAttributes=udas)
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

    def embed_jira_images(self, html: str) -> str:
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

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        pass

    def _load_config_from_path(self, config_path: Path):
        try:
            return import_module_from_file_path(config_path)
        except Exception as e:
            raise ImportError(
                f"Importing reader config from '{config_path.resolve()}' failed."
            ) from e

    def _load_and_validate_config_from_path(self, config_path: Path) -> dict[str, str]:
        config = self._load_config_from_path(config_path)

        # if not hasattr(config, "BASE_DIR"):
        #     raise KeyError("BASE_DIR is missing in reader config file.")
        # if not getattr(config, "BASE_DIR", None):
        #     raise ValueError("BASE_DIR is required in reader config file.")
        # base_dir = Path(config.BASE_DIR)
        # if not base_dir.exists():
        #     raise FileNotFoundError(f"BASE_DIR not found: '{base_dir.resolve()}'.")

        return config
