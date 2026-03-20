from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class JsonCompat(TypeDecorator[Any]):
    """Store JSON as TEXT on all databases for identical cross-db behavior."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            # Keep valid JSON strings unchanged to avoid double encoding.
            try:
                json.loads(value)
                return value
            except ValueError:
                pass
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    baselines: Mapped[list[Baseline]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Baseline(Base):
    __tablename__ = "baselines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    date: Mapped[datetime] = mapped_column(DateTime)
    type: Mapped[str] = mapped_column(String(16))

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    project: Mapped[Project] = relationship(back_populates="baselines")

    requirement_nodes: Mapped[list[RequirementNode]] = relationship(
        back_populates="baseline", cascade="all, delete-orphan"
    )


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)
    extended_id: Mapped[str] = mapped_column(String(255))
    internal_id: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64))
    priority: Mapped[str] = mapped_column(String(64))
    requirement: Mapped[bool] = mapped_column(Boolean)
    description: Mapped[str] = mapped_column(
        Text().with_variant(mysql.LONGTEXT(), "mysql").with_variant(mysql.LONGTEXT(), "mariadb")
    )
    documents: Mapped[list[str]] = mapped_column(JsonCompat)
    version_name: Mapped[str] = mapped_column(String(255))
    version_date: Mapped[datetime] = mapped_column(DateTime)
    version_author: Mapped[str] = mapped_column(String(255))
    version_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_defined_fields: Mapped[dict[str, Any]] = mapped_column(JsonCompat, default=dict)

    __table_args__ = (Index("ix_requirements_internal_id_version", "internal_id", "version_name"),)

    nodes: Mapped[list[RequirementNode]] = relationship(back_populates="requirement")


class RequirementNode(Base):
    __tablename__ = "requirement_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    baseline_id: Mapped[int] = mapped_column(ForeignKey("baselines.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    internal_id: Mapped[str] = mapped_column(String(255))
    version_name: Mapped[str] = mapped_column(String(64))

    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id"), nullable=True, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirement_nodes.id"), nullable=True, index=True
    )

    baseline: Mapped[Baseline] = relationship(back_populates="requirement_nodes")
    requirement: Mapped[Requirement | None] = relationship(back_populates="nodes")
    parent: Mapped[RequirementNode | None] = relationship(
        back_populates="children", remote_side="RequirementNode.id"
    )
    children: Mapped[list[RequirementNode]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
