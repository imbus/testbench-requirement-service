import os
from typing import Literal

from pydantic import BaseModel, model_validator
from pydantic.fields import Field


class JiraProjectConfig(BaseModel):
    baseline_field: str | None = Field(
        None, description="Jira field used to identify baselines/versions for this project"
    )
    baseline_jql: str | None = Field(
        None, description="JQL query template for fetching baseline requirements for this project"
    )
    current_baseline_jql: str | None = Field(
        None,
        description="JQL query template for fetching current baseline requirements "
        "for this project",
    )
    requirement_group_types: list[str] | None = Field(
        None, description="Issue types that represent requirement groups/folders for this project"
    )
    major_change_fields: list[str] | None = Field(
        None, description="Fields that trigger major version changes for this project"
    )
    minor_change_fields: list[str] | None = Field(
        None, description="Fields that trigger minor version changes for this project"
    )
    owner: str | None = Field(
        None, description="Jira field used for requirement owner for this project"
    )
    rendered_fields: list[str] | None = Field(
        None, description="Fields to render as HTML (e.g., description) for this project"
    )


class JiraRequirementReaderConfig(BaseModel):
    server_url: str = Field(
        ..., description="Jira server URL (e.g., https://your-domain.atlassian.net)"
    )
    auth_type: Literal["basic", "token", "oauth"] = Field(
        "basic", description="Authentication type: basic (Cloud), token (Self-Hosted), or oauth"
    )

    username: str | None = Field(
        None,
        description="Username for basic authentication (Jira Cloud)",
        json_schema_extra={
            "env_var": "JIRA_USERNAME",
            "depends_on": {"auth_type": "basic"},
            "required": True,
        },
    )
    api_token: str | None = Field(
        None,
        description="API token for basic authentication (Jira Cloud)",
        json_schema_extra={
            "sensitive": True,
            "env_var": "JIRA_API_TOKEN",
            "depends_on": {"auth_type": "basic"},
            "required": True,
        },
    )

    token: str | None = Field(
        None,
        description="Personal Access Token for token-based auth (Jira Self-Hosted)",
        json_schema_extra={
            "sensitive": True,
            "env_var": "JIRA_BEARER_TOKEN",
            "depends_on": {"auth_type": "token"},
            "required": True,
        },
    )

    access_token: str | None = Field(
        None,
        description="OAuth access token",
        json_schema_extra={
            "sensitive": True,
            "env_var": "JIRA_ACCESS_TOKEN",
            "depends_on": {"auth_type": "oauth"},
            "required": True,
        },
    )
    access_token_secret: str | None = Field(
        None,
        description="OAuth access token secret",
        json_schema_extra={
            "sensitive": True,
            "env_var": "JIRA_ACCESS_TOKEN_SECRET",
            "depends_on": {"auth_type": "oauth"},
            "required": True,
        },
    )
    consumer_key: str | None = Field(
        None,
        description="OAuth consumer key",
        json_schema_extra={
            "env_var": "JIRA_CONSUMER_KEY",
            "depends_on": {"auth_type": "oauth"},
            "required": True,
        },
    )
    key_cert: str | None = Field(
        None,
        description="OAuth private key certificate",
        json_schema_extra={
            "sensitive": True,
            "env_var": "JIRA_KEY_CERT",
            "depends_on": {"auth_type": "oauth"},
            "required": True,
        },
    )

    baseline_field: str = Field(
        "fixVersions", description="Jira field used to identify baselines/versions"
    )
    baseline_jql: str = Field(
        'project = "{project}" AND fixVersion = "{baseline}" AND issuetype in ("Epic", "Story", "User Story", "Task", "Bug")',  # noqa: E501
        description="JQL query template for fetching baseline requirements",
    )
    current_baseline_jql: str = Field(
        'project = "{project}" AND issuetype in ("Epic", "Story", "User Story", "Task", "Bug")',
        description="JQL query template for fetching current baseline requirements",
    )
    requirement_group_types: list[str] = Field(
        ["Epic"], description="Issue types that represent requirement groups/folders"
    )
    major_change_fields: list[str] = Field(
        ["fixVersions"], description="Fields that trigger major version changes"
    )
    minor_change_fields: list[str] = Field(
        ["summary", "description", "affectsVersions", "status"],
        description="Fields that trigger minor version changes",
    )
    owner: str = Field("assignee", description="Jira field used for requirement owner")
    rendered_fields: list[str] = Field(
        default_factory=list, description="Fields to render as HTML (e.g., description)"
    )

    projects: dict[str, JiraProjectConfig] = Field(
        default_factory=dict,
        description="Project-specific configuration overrides",
        json_schema_extra={
            "prompt_as_dict": True,
            "item_label": "Project Configuration",
            "key_label": "Project Key",
            "add_prompt": "Would you like to add a project-specific configuration?",
            "add_another_prompt": "Add another project configuration?",
        },
    )

    @model_validator(mode="after")
    def validate_config(self):  # noqa: C901
        if self.auth_type == "basic":
            self.username = self.username or os.getenv("JIRA_USERNAME")
            if not self.username:
                raise ValueError(
                    "Jira username must be provided for basic auth "
                    "(via config or JIRA_USERNAME env)"
                )

            self.api_token = self.api_token or os.getenv("JIRA_API_TOKEN")
            if not self.api_token:
                raise ValueError(
                    "Jira API token must be provided for basic auth "
                    "(via config or JIRA_API_TOKEN env)"
                )
        elif self.auth_type == "token":
            self.token = self.token or os.getenv("JIRA_BEARER_TOKEN")
            if not self.token:
                raise ValueError(
                    "Jira Personal Access Token must be provided for token auth "
                    "(via config or JIRA_BEARER_TOKEN env)"
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
                    "Jira Access Token must be provided for OAuth "
                    "(via config or JIRA_ACCESS_TOKEN env)"
                )
            if not self.access_token_secret:
                raise ValueError(
                    "Jira Access Token Secret must be provided for OAuth "
                    "(via config or JIRA_ACCESS_TOKEN_SECRET env)"
                )
            if not self.consumer_key:
                raise ValueError(
                    "Jira consumer key must be provided for OAuth "
                    "(via config or JIRA_CONSUMER_KEY env)"
                )
            if not self.key_cert:
                raise ValueError(
                    "Jira Private Key must be provided for OAuth (via config or JIRA_KEY_CERT env)"
                )

        return self
