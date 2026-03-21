from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from testbench_requirement_service.models.requirement import RequirementKey
from testbench_requirement_service.readers.sql.config import SqlRequirementReaderConfig
from testbench_requirement_service.readers.sql.reader import SqlRequirementReader


@pytest.fixture
def sqlite_db(tmp_path: Path) -> str:
    db_path = tmp_path / "sql_reader.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")

    statements = [
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
        """,
        """
        CREATE TABLE baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            date TEXT,
            type TEXT,
            project_id INTEGER
        )
        """,
        """
        CREATE TABLE requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            extended_id TEXT,
            internal_id TEXT,
            owner TEXT,
            status TEXT,
            priority TEXT,
            requirement INTEGER,
            description TEXT,
            documents TEXT,
            version_name TEXT,
            version_date TEXT,
            version_author TEXT,
            version_comment TEXT
        )
        """,
        """
        CREATE TABLE requirement_udfs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_id INTEGER,
            udf_name TEXT,
            udf_type TEXT,
            udf_value TEXT
        )
        """,
        "INSERT INTO projects (id, name) VALUES (1, 'TB')",
        "INSERT INTO baselines (id, name, date, type, project_id) VALUES (1, 'BL1', '2026-01-01T00:00:00', 'CURRENT', 1)",
        """
        INSERT INTO requirements (
            id, name, extended_id, internal_id, owner, status, priority, requirement, description,
            documents, version_name, version_date, version_author, version_comment
        ) VALUES (
            1, 'Req 1', 'EXT-1', 'REQ-1', 'owner', 'open', 'high', 1, 'desc',
            '[]', '1', '2026-01-01T00:00:00', 'author', ''
        )
        """,
        "INSERT INTO requirement_udfs (requirement_id, udf_name, udf_type, udf_value) VALUES (1, 'Safety Relevant', 'boolean', 'true')",
        "INSERT INTO requirement_udfs (requirement_id, udf_name, udf_type, udf_value) VALUES (1, 'Divisions', 'string_array', '[\"A\", \"B\"]')",
        "INSERT INTO requirement_udfs (requirement_id, udf_name, udf_type, udf_value) VALUES (1, 'Feature Planned', 'string_array', '[\"X\", \"Y\"]')",
    ]

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))

    return f"sqlite:///{db_path.as_posix()}"


class TestSqlReaderUdas:
    def test_get_user_defined_attributes_returns_configured_definitions(
        self, sqlite_db: str
    ) -> None:
        config = SqlRequirementReaderConfig.model_validate(
            {
                "database_url": sqlite_db,
                "user_defined_attributes": [
                    {"name": "Safety Relevant", "type": "BOOLEAN"},
                    {"name": "Divisions", "type": "ARRAY"},
                ],
            }
        )
        reader = SqlRequirementReader(config)

        udas = reader.get_user_defined_attributes()

        assert [u.name for u in udas] == ["Safety Relevant", "Divisions"]
        assert [u.valueType for u in udas] == ["BOOLEAN", "ARRAY"]

    def test_get_all_user_defined_attributes_extracts_and_normalizes_values(
        self, sqlite_db: str
    ) -> None:
        config = SqlRequirementReaderConfig.model_validate(
            {
                "database_url": sqlite_db,
                "user_defined_attributes": [
                    {
                        "name": "Safety Relevant",
                        "type": "BOOLEAN",
                    },
                    {
                        "name": "Divisions",
                        "type": "ARRAY",
                    },
                    {
                        "name": "Feature Planned",
                        "type": "ARRAY",
                    },
                ],
            }
        )
        reader = SqlRequirementReader(config)

        result = reader.get_all_user_defined_attributes(
            project="TB",
            baseline="BL1",
            requirement_keys=[
                RequirementKey(id="REQ-1", version="1"),
                RequirementKey(id="REQ-404", version="1"),
            ],
            attribute_names=["Safety Relevant", "Divisions", "Feature Planned"],
        )

        assert len(result) == 1
        assert result[0].key.id == "REQ-1"
        assert len(result[0].userDefinedAttributes) == 3

        attrs = {attr.name: attr for attr in result[0].userDefinedAttributes}
        assert attrs["Safety Relevant"].booleanValue is True
        assert attrs["Divisions"].stringValues == ["A", "B"]
        assert attrs["Feature Planned"].stringValues == ["X", "Y"]

    def test_missing_attribute_names_returns_empty_payload_for_existing_key(
        self, sqlite_db: str
    ) -> None:
        config = SqlRequirementReaderConfig.model_validate(
            {
                "database_url": sqlite_db,
                "user_defined_attributes": [{"name": "Safety Relevant", "type": "BOOLEAN"}],
            }
        )
        reader = SqlRequirementReader(config)

        result = reader.get_all_user_defined_attributes(
            project="TB",
            baseline="BL1",
            requirement_keys=[RequirementKey(id="REQ-1", version="1")],
            attribute_names=["Unknown Attribute"],
        )

        assert len(result) == 1
        assert result[0].key.id == "REQ-1"
        assert result[0].userDefinedAttributes == []

    def test_imports_sample_user_defined_fields_payload(self, sqlite_db: str) -> None:
        config = SqlRequirementReaderConfig.model_validate(
            {
                "database_url": sqlite_db,
                "user_defined_attributes": [
                    {"name": "Feature Planned", "type": "ARRAY"},
                    {"name": "Divisions", "type": "ARRAY"},
                    {"name": "Test Departments", "type": "ARRAY"},
                    {"name": "Safety Relevant", "type": "BOOLEAN", "true_value": "true"},
                    {"name": "Safety Level", "type": "STRING"},
                    {"name": "Change Status", "type": "ARRAY"},
                    {"name": "Baseline Name", "type": "STRING"},
                    {"name": "Last Modified On", "type": "STRING"},
                    {"name": "Type", "type": "STRING"},
                    {"name": "State", "type": "STRING"},
                ],
            }
        )
        reader = SqlRequirementReader(config)

        udf_rows = [
            (
                1,
                "Feature Planned",
                "string_array",
                '["C0_Sample@EV$MnM_GEN4_ESCL", "A_Sample@W616$MnM_GEN4_ESCL"]',
            ),
            (1, "Divisions", "string_array", '["PEP"]'),
            (1, "Test Departments", "string_array", '["Validation"]'),
            (1, "Safety Relevant", "boolean", "false"),
            (1, "Safety Level", "string", "QM"),
            (1, "Change Status", "string_array", '["Unchanged"]'),
            (1, "Baseline Name", "string", "1.24_(SRS_OTS_C_Sample)"),
            (1, "Last Modified On", "string", "2025-06-11T15:28:01+00:00"),
            (1, "Type", "string", "3"),
            (1, "State", "string", "1"),
        ]
        with reader._session() as session:
            # Remove fixture UDFs and insert sample payload
            session.execute(text("DELETE FROM requirement_udfs WHERE requirement_id = 1"))
            for req_id, name, udf_type, value in udf_rows:
                session.execute(
                    text(
                        "INSERT INTO requirement_udfs (requirement_id, udf_name, udf_type, udf_value) "
                        "VALUES (:req_id, :name, :udf_type, :value)"
                    ),
                    {"req_id": req_id, "name": name, "udf_type": udf_type, "value": value},
                )
            session.commit()

        result = reader.get_all_user_defined_attributes(
            project="TB",
            baseline="BL1",
            requirement_keys=[RequirementKey(id="REQ-1", version="1")],
            attribute_names=[
                "Feature Planned",
                "Divisions",
                "Test Departments",
                "Safety Relevant",
                "Safety Level",
                "Change Status",
                "Baseline Name",
                "Last Modified On",
                "Type",
                "State",
            ],
        )

        assert len(result) == 1
        attrs = {attr.name: attr for attr in result[0].userDefinedAttributes}
        assert attrs["Feature Planned"].stringValues == [
            "C0_Sample@EV$MnM_GEN4_ESCL",
            "A_Sample@W616$MnM_GEN4_ESCL",
        ]
        assert attrs["Divisions"].stringValues == ["PEP"]
        assert attrs["Test Departments"].stringValues == ["Validation"]
        assert attrs["Safety Relevant"].booleanValue is False
        assert attrs["Safety Level"].stringValue == "QM"
        assert attrs["Change Status"].stringValues == ["Unchanged"]
        assert attrs["Baseline Name"].stringValue == "1.24_(SRS_OTS_C_Sample)"
        assert attrs["Last Modified On"].stringValue == "2025-06-11T15:28:01+00:00"
        assert attrs["Type"].stringValue == "3"
        assert attrs["State"].stringValue == "1"
