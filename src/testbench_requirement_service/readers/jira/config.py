import os
from typing import Literal

from pydantic import BaseModel, model_validator
from pydantic.fields import Field


class JiraProjectConfig(BaseModel):
    baseline_field: str | None = None
    baseline_jql: str | None = None
    current_baseline_jql: str | None = None
    requirement_group_types: list[str] | None = None
    major_change_fields: list[str] | None = None
    minor_change_fields: list[str] | None = None
    owner: str | None = None
    rendered_fields: list[str] | None = None


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
    baseline_jql: str = 'project = "{project}" AND fixVersion = "{baseline}" AND issuetype in ("Epic", "Story", "User Story", "Task", "Bug")'  # noqa: E501
    current_baseline_jql: str = (
        'project = "{project}" AND issuetype in ("Epic", "Story", "User Story", "Task", "Bug")'
    )
    requirement_group_types: list[str] = ["Epic"]
    major_change_fields: list[str] = ["fixVersions"]
    minor_change_fields: list[str] = ["summary", "description", "affectsVersions", "status"]
    owner: str = "assignee"
    rendered_fields: list[str] = Field(default_factory=list)

    projects: dict[str, JiraProjectConfig] = Field(default_factory=dict)

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
