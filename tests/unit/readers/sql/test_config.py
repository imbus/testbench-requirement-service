import pytest

from testbench_requirement_service.readers.sql.config import SqlRequirementReaderConfig


class TestSqlRequirementReaderConfig:
    def test_minimal_config_is_valid(self) -> None:
        config = SqlRequirementReaderConfig.model_validate({"database_url": "sqlite:///example.db"})
        assert config.database_url == "sqlite:///example.db"
        assert config.pool_size == 5
        assert config.user_defined_attributes == []

    def test_rich_config_with_udas_is_valid(self) -> None:
        config = SqlRequirementReaderConfig.model_validate(
            {
                "database_url": "sqlite:///example.db",
                "connect_timeout_seconds": 15,
                "pool_size": 8,
                "max_overflow": 4,
                "pool_recycle_seconds": 600,
                "user_defined_attributes": [
                    {
                        "name": "Safety Relevant",
                        "type": "BOOLEAN",
                        "true_value": "yes",
                    },
                    {
                        "name": "Divisions",
                        "type": "ARRAY",
                        "array_separator": ";",
                    },
                ],
            }
        )
        assert len(config.user_defined_attributes) == 2
        assert config.user_defined_attributes[0].true_value == "yes"
        assert config.user_defined_attributes[1].array_separator == ";"

    def test_duplicate_uda_names_rejected_case_insensitive(self) -> None:
        with pytest.raises(ValueError, match="Duplicate user_defined_attributes name"):
            SqlRequirementReaderConfig.model_validate(
                {
                    "database_url": "sqlite:///example.db",
                    "user_defined_attributes": [
                        {"name": "Safety", "type": "STRING"},
                        {"name": "safety", "type": "BOOLEAN"},
                    ],
                }
            )

    def test_empty_database_url_rejected(self) -> None:
        with pytest.raises(ValueError, match="Value must not be empty"):
            SqlRequirementReaderConfig.model_validate({"database_url": "   "})

    def test_empty_uda_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            SqlRequirementReaderConfig.model_validate(
                {
                    "database_url": "sqlite:///example.db",
                    "user_defined_attributes": [
                        {
                            "name": "   ",
                            "type": "STRING",
                        }
                    ],
                }
            )
