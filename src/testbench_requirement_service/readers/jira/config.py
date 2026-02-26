import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator
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
    auth_type: Literal["basic", "token", "oauth1"] = Field(
        "basic",
        description=(
            "Authentication type: basic (Cloud), token (Self-Hosted), or oauth1 (OAuth 1.0a)"
        ),
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

    oauth1_access_token: str | None = Field(
        None,
        description="OAuth1 access token",
        json_schema_extra={
            "sensitive": True,
            "env_var": "JIRA_OAUTH1_ACCESS_TOKEN",
            "depends_on": {"auth_type": "oauth1"},
            "required": True,
        },
    )
    oauth1_access_token_secret: str | None = Field(
        None,
        description="OAuth1 access token secret",
        json_schema_extra={
            "sensitive": True,
            "env_var": "JIRA_OAUTH1_ACCESS_TOKEN_SECRET",
            "depends_on": {"auth_type": "oauth1"},
            "required": True,
        },
    )
    oauth1_consumer_key: str | None = Field(
        None,
        description="OAuth1 consumer key",
        json_schema_extra={
            "env_var": "JIRA_OAUTH1_CONSUMER_KEY",
            "depends_on": {"auth_type": "oauth1"},
            "required": True,
        },
    )
    oauth1_key_cert_path: str | None = Field(
        None,
        description="Path to the OAuth1 private key certificate file (.pem)",
        json_schema_extra={
            "env_var": "JIRA_OAUTH1_KEY_CERT_PATH",
            "depends_on": {"auth_type": "oauth1"},
            "required": True,
        },
    )
    oauth1_key_cert: str | None = Field(
        None,
        description="OAuth1 private key certificate content (use oauth1_key_cert_path instead)",
        json_schema_extra={
            "sensitive": True,
            "env_var": "JIRA_OAUTH1_KEY_CERT",
            "depends_on": {"auth_type": "oauth1"},
            "required": False,
            "skip_if_wizard": True,
        },
    )

    client_cert_path: str | None = Field(
        None,
        description="Path to client certificate file for mutual TLS authentication (.pem or .crt)",
        json_schema_extra={
            "env_var": "JIRA_CLIENT_CERT_PATH",
        },
    )
    client_key_path: str | None = Field(
        None,
        description="Path to client private key file for mutual TLS authentication (.key or .pem). "
        "Only needed when the key is stored separately from the certificate.",
        json_schema_extra={
            "env_var": "JIRA_CLIENT_KEY_PATH",
        },
    )

    baseline_field: str = Field(
        "fixVersions", description="Jira field used to identify baselines/versions"
    )
    baseline_jql: str = Field(
        'project = "{project}" AND fixVersion = "{baseline}" AND issuetype in standardIssueTypes()',
        description="JQL query template for fetching baseline requirements",
    )
    current_baseline_jql: str = Field(
        'project = "{project}" AND issuetype in standardIssueTypes()',
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
    owner_field: str = Field("assignee", description="Jira field used for requirement owner")
    rendered_fields: list[str] = Field(
        default_factory=list, description="Fields to render as HTML (e.g., description)"
    )
    timeout: int = Field(
        30,
        description="HTTP request timeout in seconds for Jira API calls",
        ge=1,
        le=300,
    )
    max_retries: int = Field(
        3,
        description="Maximum number of retries for failed Jira API requests",
        ge=0,
        le=10,
    )
    cache_ttl: float = Field(
        300.0,
        description="Default time-to-live in seconds for all internal caches (0 = no caching)",
        ge=0,
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

    @property
    def client_cert(self) -> str | tuple[str, str] | None:
        """Build the client_cert value expected by the jira package ``options`` dict.

        Returns:
        - ``str`` path when only ``client_cert_path`` is set (combined cert+key file).
        - ``(cert, key)`` tuple when both ``client_cert_path`` and ``client_key_path`` are set.
        - ``None`` when no client certificate is configured.
        """
        cert = self.client_cert_path or os.getenv("JIRA_CLIENT_CERT_PATH")
        key = self.client_key_path or os.getenv("JIRA_CLIENT_KEY_PATH")
        if cert and key:
            return (cert, key)
        return cert or None

    @field_validator("oauth1_key_cert_path")
    @classmethod
    def validate_oauth1_key_cert_path_exists(cls, v: str | None) -> str | None:
        """Validate that oauth1_key_cert_path exists if provided."""
        if v is not None and not Path(v).exists():
            raise ValueError(f"OAuth1 private key file not found: '{v}'")
        return v

    @field_validator("client_cert_path", "client_key_path")
    @classmethod
    def validate_client_cert_files_exist(cls, v: str | None) -> str | None:
        """Validate that client certificate/key files exist if provided."""
        if v is not None and not Path(v).exists():
            raise ValueError(f"Client certificate/key file not found: '{v}'")
        return v

    def _validate_basic_auth(self) -> None:
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

    def _validate_token_auth(self) -> None:
        self.token = self.token or os.getenv("JIRA_BEARER_TOKEN")
        if not self.token:
            raise ValueError(
                "Jira Personal Access Token must be provided for token auth "
                "(via config or JIRA_BEARER_TOKEN env)"
            )

    def _validate_oauth1(self) -> None:
        self.oauth1_access_token = self.oauth1_access_token or os.getenv("JIRA_OAUTH1_ACCESS_TOKEN")
        self.oauth1_access_token_secret = self.oauth1_access_token_secret or os.getenv(
            "JIRA_OAUTH1_ACCESS_TOKEN_SECRET"
        )
        self.oauth1_consumer_key = self.oauth1_consumer_key or os.getenv("JIRA_OAUTH1_CONSUMER_KEY")
        self.oauth1_key_cert_path = self.oauth1_key_cert_path or os.getenv(
            "JIRA_OAUTH1_KEY_CERT_PATH"
        )
        if self.oauth1_key_cert_path:
            try:
                self.oauth1_key_cert = Path(self.oauth1_key_cert_path).read_text(encoding="utf-8")
            except OSError as e:
                raise ValueError(
                    f"Could not read OAuth1 private key from '{self.oauth1_key_cert_path}': {e}"
                ) from e
        else:
            self.oauth1_key_cert = self.oauth1_key_cert or os.getenv("JIRA_OAUTH1_KEY_CERT")
        if not self.oauth1_access_token:
            raise ValueError(
                "Jira Access Token must be provided for OAuth1 "
                "(via config or JIRA_OAUTH1_ACCESS_TOKEN env)"
            )
        if not self.oauth1_access_token_secret:
            raise ValueError(
                "Jira Access Token Secret must be provided for OAuth1 "
                "(via config or JIRA_OAUTH1_ACCESS_TOKEN_SECRET env)"
            )
        if not self.oauth1_consumer_key:
            raise ValueError(
                "Jira consumer key must be provided for OAuth1 "
                "(via config or JIRA_OAUTH1_CONSUMER_KEY env)"
            )
        if not self.oauth1_key_cert:
            raise ValueError(
                "Jira Private Key must be provided for OAuth1 "
                "(via oauth1_key_cert_path / JIRA_OAUTH1_KEY_CERT_PATH "
                "or oauth1_key_cert / JIRA_OAUTH1_KEY_CERT env)"
            )

    @model_validator(mode="after")
    def validate_config(self) -> "JiraRequirementReaderConfig":
        if self.auth_type == "basic":
            self._validate_basic_auth()
        elif self.auth_type == "token":
            self._validate_token_auth()
        elif self.auth_type == "oauth1":
            self._validate_oauth1()
        return self
