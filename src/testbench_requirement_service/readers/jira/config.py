import os
import sys
from pathlib import Path
from typing import Any, Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from pydantic import BaseModel, ValidationError, model_validator
from pydantic.fields import Field as ModelField


class JiraProjectConfig(BaseModel):
    baseline_field: str | None = None
    baseline_jql: str | None = None
    current_baseline_jql: str | None = None
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
    baseline_jql: str = 'fixVersion = "{baseline}"'
    current_baseline_jql: str = ""
    requirement_types: list[str] = ["Story", "User Story", "Task", "Bug"]
    requirement_group_types: list[str] = ["Epic"]

    projects: dict[str, JiraProjectConfig] = ModelField(default_factory=dict)

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


def load_config_dict_from_path(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Reader config file not found at: '{config_path.resolve()}'")

    try:
        with config_path.open("rb") as config_file:
            config_dict = tomllib.load(config_file)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"Failed to parse TOML in reader config file: {e}") from e

    return config_dict


def load_and_validate_config_from_path(config_path: Path) -> JiraRequirementReaderConfig:
    config_dict = load_config_dict_from_path(config_path)

    config_prefix = "jira"
    if config_prefix not in config_dict:
        raise ValueError(f"TOML section [{config_prefix}] not found in reader config file.")

    project_configs = config_dict.get("projects", {})

    try:
        return JiraRequirementReaderConfig(**config_dict[config_prefix], projects=project_configs)
    except ValidationError as e:
        error_message = "; ".join([err["msg"] for err in e.errors()])
        raise ValueError(f"Invalid reader config: {error_message}") from e
