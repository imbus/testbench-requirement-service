from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
    description: Mapped[str] = mapped_column(Text)
    documents: Mapped[list[str]] = mapped_column(JSON)
    baseline: Mapped[str] = mapped_column(String(255))
    version_name: Mapped[str] = mapped_column(String(255))
    version_date: Mapped[datetime] = mapped_column(DateTime)
    version_author: Mapped[str] = mapped_column(String(255))
    version_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

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
