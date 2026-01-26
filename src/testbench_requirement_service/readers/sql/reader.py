from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from sanic.exceptions import NotFound
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, joinedload

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
from testbench_requirement_service.readers.sql.config import SqlRequirementReaderConfig
from testbench_requirement_service.readers.sql.orm import (
    Baseline,
    Project,
    Requirement,
    RequirementNode,
)
from testbench_requirement_service.readers.utils import load_reader_config_from_path


class SqlRequirementReader(AbstractRequirementReader):
    def __init__(self, config_path: str):
        self.config = load_reader_config_from_path(
            config_path=Path(config_path),
            config_class=SqlRequirementReaderConfig,
            config_prefix="sql",
        )
        self._engine = create_engine(
            self.config.database_url,
            echo=self.config.echo,
            pool_pre_ping=self.config.pool_pre_ping,
        )

    @contextmanager
    def _session(self):
        session = Session(self._engine)
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
        return []

    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributeResponse]:
        if not requirement_keys:
            return []

        with self._session() as session:
            baseline_obj = self._get_baseline(session, project, baseline)
            if baseline_obj is None:
                raise NotFound("Baseline not found")

            stmt = select(Requirement.internal_id, Requirement.version_name).where(
                Requirement.baseline == baseline_obj.name
            )
            existing = set(session.execute(stmt).all())

        return [
            UserDefinedAttributeResponse(key=key, userDefinedAttributes=[])
            for key in requirement_keys
            if (key.id, key.version) in existing
        ]

    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        with self._session() as session:
            baseline_obj = self._get_baseline(session, project, baseline)
            if baseline_obj is None:
                raise NotFound("Baseline not found")

            stmt = select(Requirement).where(
                Requirement.internal_id == key.id,
                Requirement.version_name == key.version,
            )
            requirement = session.scalar(stmt)
            if requirement is None:
                raise NotFound("Requirement not found")

            return ExtendedRequirementObject(
                name=requirement.name,
                extendedID=requirement.extended_id,
                key=RequirementKey(id=requirement.internal_id, version=requirement.version_name),
                owner=requirement.owner,
                status=requirement.status,
                priority=requirement.priority,
                requirement=requirement.requirement,
                description=requirement.description,
                documents=requirement.documents or [],
                baseline=requirement.baseline,
            )

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        with self._session() as session:
            baseline_obj = self._get_baseline(session, project, baseline)
            if baseline_obj is None:
                raise NotFound("Baseline not found")

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
                    author=req.version_author,
                    comment=req.version_comment,
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
    def _normalize_dt(value: datetime) -> datetime:
        if value.tzinfo is None:
            local_tz = datetime.now().astimezone().tzinfo
            return value.replace(tzinfo=local_tz)
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
        return session.scalar(stmt)
