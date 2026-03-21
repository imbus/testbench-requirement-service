from __future__ import annotations

import base64
import json
import re
from contextlib import contextmanager
from datetime import datetime
from typing import Literal, cast

from sanic.exceptions import NotFound
from sqlalchemy import create_engine, select, tuple_  # type: ignore[import-not-found]
from sqlalchemy.orm import Session, joinedload, sessionmaker  # type: ignore[import-not-found]

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
from testbench_requirement_service.readers.sql.config import (
    SqlRequirementReaderConfig,
    SqlUserDefinedAttributeConfig,
)
from testbench_requirement_service.readers.sql.orm import (
    Baseline,
    Project,
    Requirement,
    RequirementImage,
    RequirementNode,
    RequirementUdf,
)

_LOCAL_TZ = datetime.now().astimezone().tzinfo

_BATCH_SIZE = 450
_IMAGE_REF_PATTERN = re.compile(r"image://([0-9a-f]{64})")


class SqlRequirementReader(AbstractRequirementReader):
    CONFIG_CLASS = SqlRequirementReaderConfig

    def __init__(self, config: SqlRequirementReaderConfig):
        self.config = config
        engine_kwargs: dict = {
            "echo": self.config.echo,
            "pool_pre_ping": self.config.pool_pre_ping,
        }
        is_sqlite = self.config.database_url.strip().lower().startswith("sqlite")
        if not is_sqlite:
            engine_kwargs.update(
                {
                    "pool_size": self.config.pool_size,
                    "max_overflow": self.config.max_overflow,
                    "pool_recycle": self.config.pool_recycle_seconds,
                }
            )

        if self.config.connect_timeout_seconds is not None:
            timeout_key = "timeout" if is_sqlite else "connect_timeout"
            engine_kwargs["connect_args"] = {timeout_key: self.config.connect_timeout_seconds}

        self._engine = create_engine(
            self.config.database_url,
            **engine_kwargs,
        )
        self._session_factory = sessionmaker(bind=self._engine)

    @contextmanager
    def _session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def project_exists(self, project: str) -> bool:
        with self._session() as session:
            stmt = select(Project.id).where(Project.name == project).limit(1)
            return session.scalar(stmt) is not None

    def baseline_exists(self, project: str, baseline: str) -> bool:
        with self._session() as session:
            stmt = (
                select(Baseline.id)
                .join(Baseline.project)
                .where(Project.name == project, Baseline.name == baseline)
                .limit(1)
            )
            return session.scalar(stmt) is not None

    def get_projects(self) -> list[str]:
        with self._session() as session:
            stmt = select(Project.name).order_by(Project.name)
            return list(session.scalars(stmt).all())

    def get_baselines(self, project: str) -> list[BaselineObject]:
        with self._session() as session:
            stmt = (
                select(Baseline)
                .join(Baseline.project)
                .where(Project.name == project)
                .order_by(Baseline.name)
            )
            baselines = session.scalars(stmt).all()
            return [
                BaselineObject(
                    name=b.name,
                    date=self._normalize_dt(b.date),
                    type=self._normalize_baseline_type(b.type),
                )
                for b in baselines
            ]

    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        with self._session() as session:
            baseline_obj = self._get_baseline(session, project, baseline)
            if baseline_obj is None:
                raise NotFound("Baseline not found")

            stmt = (
                select(RequirementNode)
                .where(RequirementNode.baseline_id == baseline_obj.id)
                .options(joinedload(RequirementNode.requirement))
            )
            nodes = session.scalars(stmt).all()

            requirement_nodes: dict[int, RequirementObjectNode] = {}
            roots: list[RequirementObjectNode] = []

            for node in nodes:
                requirement_nodes[node.id] = self._build_requirement_node(node)

            for node in nodes:
                current = requirement_nodes[node.id]
                if node.parent_id:
                    parent = requirement_nodes.get(node.parent_id)
                    if parent is None:
                        continue
                    parent.children = parent.children or []
                    parent.children.append(current)
                else:
                    roots.append(current)

            return BaselineObjectNode(
                name=baseline_obj.name,
                date=self._normalize_dt(baseline_obj.date),
                type=self._normalize_baseline_type(baseline_obj.type),
                children=roots,
            )

    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        return [
            UserDefinedAttribute(name=uda.name, valueType=uda.type)
            for uda in self.config.user_defined_attributes
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

        selected_udas = self._resolve_selected_udas(attribute_names)

        if selected_udas:
            with self._session() as session:
                row_map = self._load_requirement_row_map(session, requirement_keys)
        else:
            row_map = {(k.id, k.version): {} for k in requirement_keys}

        responses: list[UserDefinedAttributeResponse] = []
        for key in requirement_keys:
            row = row_map.get((key.id, key.version))
            if row is None:
                continue

            attributes: list[UserDefinedAttribute] = []
            for udf in selected_udas:
                value = self._extract_uda_value(udf, row)
                attr = self._to_user_defined_attribute(udf, value)
                if attr is not None:
                    attributes.append(attr)

            responses.append(
                UserDefinedAttributeResponse(key=key, userDefinedAttributes=attributes)
            )

        return responses

    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        with self._session() as session:
            stmt = select(Requirement).where(
                Requirement.internal_id == key.id,
                Requirement.version_name == key.version,
            )
            requirement = session.scalar(stmt)
            if requirement is None:
                raise NotFound("Requirement not found")

            description = self._reembed_images(requirement.description, session)

            return ExtendedRequirementObject(
                name=requirement.name,
                extendedID=requirement.extended_id,
                key=RequirementKey(id=requirement.internal_id, version=requirement.version_name),
                owner=requirement.owner,
                status=requirement.status,
                priority=requirement.priority,
                requirement=requirement.requirement,
                description=description,
                documents=requirement.documents or [],
                baseline=baseline,
            )

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        with self._session() as session:
            stmt = (
                select(Requirement)
                .where(Requirement.internal_id == key.id)
                .order_by(Requirement.version_date)
            )
            requirements = session.scalars(stmt).all()

            return [
                RequirementVersionObject(
                    name=req.version_name,
                    date=self._normalize_dt(req.version_date),
                    author=req.version_author or "",
                    comment=req.version_comment or "",
                )
                for req in requirements
            ]

    @staticmethod
    def _build_requirement_node(node: RequirementNode) -> RequirementObjectNode:
        req = node.requirement
        if req:
            key = RequirementKey(id=req.internal_id, version=req.version_name)
            return RequirementObjectNode(
                name=req.name,
                extendedID=req.extended_id,
                key=key,
                owner=req.owner,
                status=req.status,
                priority=req.priority,
                requirement=req.requirement,
                children=[],
            )

        key = RequirementKey(id=node.internal_id, version=node.version_name)
        return RequirementObjectNode(
            name=node.name,
            extendedID="",
            key=key,
            owner="",
            status="",
            priority="",
            requirement=False,
            children=[],
        )

    @staticmethod
    def _reembed_images(description: str, session: Session) -> str:
        hashes = set(_IMAGE_REF_PATTERN.findall(description))
        if not hashes:
            return description

        images = {
            row.hash: row
            for row in session.query(RequirementImage)
            .filter(RequirementImage.hash.in_(hashes))
            .all()
        }

        def replace_ref(match: re.Match[str]) -> str:
            h = match.group(1)
            img = images.get(h)
            if img is None:
                return match.group(0)
            b64 = base64.b64encode(img.data).decode("ascii")
            return f"data:{img.mime_type};base64,{b64}"

        return _IMAGE_REF_PATTERN.sub(replace_ref, description)

    @staticmethod
    def _normalize_dt(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=_LOCAL_TZ)
        return value

    @staticmethod
    def _normalize_baseline_type(
        value: str,
    ) -> Literal["CURRENT", "UNLOCKED", "LOCKED", "DISABLED", "INVALID"]:
        allowed = {"CURRENT", "UNLOCKED", "LOCKED", "DISABLED", "INVALID"}
        if value in allowed:
            return cast(
                Literal["CURRENT", "UNLOCKED", "LOCKED", "DISABLED", "INVALID"],
                value,
            )
        return "INVALID"

    @staticmethod
    def _get_baseline(session: Session, project: str, baseline: str) -> Baseline | None:
        stmt = (
            select(Baseline)
            .join(Baseline.project)
            .where(Project.name == project, Baseline.name == baseline)
        )
        return session.scalar(stmt)  # type: ignore[no-any-return]

    def _resolve_selected_udas(
        self, attribute_names: list[str]
    ) -> list[SqlUserDefinedAttributeConfig]:
        if not self.config.user_defined_attributes:
            return []

        if not attribute_names:
            return self.config.user_defined_attributes

        requested = {name.casefold() for name in attribute_names}
        return [
            uda for uda in self.config.user_defined_attributes if uda.name.casefold() in requested
        ]

    def _load_requirement_row_map(
        self,
        session: Session,
        requirement_keys: list[RequirementKey],
    ) -> dict[tuple[str, str], dict[str, object]]:
        pairs = [(key.id, key.version) for key in requirement_keys]
        row_map: dict[tuple[str, str], dict[str, object]] = {}

        for i in range(0, len(pairs), _BATCH_SIZE):
            batch = pairs[i : i + _BATCH_SIZE]
            stmt = (
                select(
                    Requirement.internal_id,
                    Requirement.version_name,
                    RequirementUdf.udf_name,
                    RequirementUdf.udf_type,
                    RequirementUdf.udf_value,
                )
                .join(RequirementUdf, Requirement.id == RequirementUdf.requirement_id)
                .where(tuple_(Requirement.internal_id, Requirement.version_name).in_(batch))
            )
            for internal_id, version_name, udf_name, udf_type, udf_value in session.execute(stmt):
                key = (str(internal_id), str(version_name))
                if key not in row_map:
                    row_map[key] = {}
                row_map[key][udf_name] = self._decode_udf_value(udf_type, udf_value)

        # Ensure keys with no UDF rows still appear in the map
        for i in range(0, len(pairs), _BATCH_SIZE):
            batch = pairs[i : i + _BATCH_SIZE]
            key_stmt = select(Requirement.internal_id, Requirement.version_name).where(
                tuple_(Requirement.internal_id, Requirement.version_name).in_(batch)
            )
            for internal_id, version_name in session.execute(key_stmt):
                key = (str(internal_id), str(version_name))
                row_map.setdefault(key, {})

        return row_map

    @staticmethod
    def _decode_udf_value(udf_type: str, udf_value: str) -> object:
        if udf_type == "boolean":
            return udf_value == "true"
        if udf_type == "string_array":
            return json.loads(udf_value)
        return udf_value

    @staticmethod
    def _extract_uda_value(udf: SqlUserDefinedAttributeConfig, row: dict[str, object]) -> object:
        return row.get(udf.name)

    @staticmethod
    def _to_bool(value: object, true_value: str) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().casefold() == true_value.strip().casefold()
        return bool(value)

    @staticmethod
    def _to_array(value: object, separator: str) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if item is not None]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed if item is not None]
                except json.JSONDecodeError:
                    pass
            return [part.strip() for part in stripped.split(separator) if part.strip()]
        return [str(value)]

    def _to_user_defined_attribute(
        self, udf: SqlUserDefinedAttributeConfig, value: object
    ) -> UserDefinedAttribute | None:
        if udf.type == "STRING":
            if value is None:
                return None
            return UserDefinedAttribute(name=udf.name, valueType="STRING", stringValue=str(value))

        if udf.type == "ARRAY":
            string_values = self._to_array(value, udf.array_separator)
            if string_values is None:
                return None
            return UserDefinedAttribute(
                name=udf.name,
                valueType="ARRAY",
                stringValues=string_values,
            )

        boolean_value = self._to_bool(value, udf.true_value)
        if boolean_value is None:
            return None
        return UserDefinedAttribute(name=udf.name, valueType="BOOLEAN", booleanValue=boolean_value)
