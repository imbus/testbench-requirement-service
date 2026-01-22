"""Configuration model for SQL requirement reader."""

from pydantic import BaseModel


class SqlRequirementReaderConfig(BaseModel):
    """SQL reader configuration loaded from TOML."""

    database_url: str
    echo: bool = False
    pool_pre_ping: bool = True
