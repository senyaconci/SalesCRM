"""SQLAlchemy persistence for checkpoints, cache metadata, and cost ledger."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from org_intel.utils.io import read_json


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CheckpointRow(Base):
    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    phase: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    payload_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DocumentCacheRow(Base):
    __tablename__ = "document_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, unique=True, index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    local_path: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LLMCacheRow(Base):
    __tablename__ = "llm_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CostLedgerRow(Base):
    __tablename__ = "cost_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    task_type: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    actual_cost: Mapped[float] = mapped_column(Float, default=0.0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RunManifestRow(Base):
    __tablename__ = "run_manifests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    org_url: Mapped[str] = mapped_column(Text)
    organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mode: Mapped[str] = mapped_column(String(32))
    output_dir: Mapped[str] = mapped_column(Text)
    config_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Database:
    def __init__(self, database_url: str) -> None:
        connect_args: dict[str, Any] = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self.engine = create_engine(database_url, future=True, connect_args=connect_args)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.SessionLocal()

    def get_checkpoint(self, run_id: str, phase: str) -> CheckpointRow | None:
        with self.session() as session:
            return session.scalar(
                select(CheckpointRow).where(
                    CheckpointRow.run_id == run_id,
                    CheckpointRow.phase == phase,
                    CheckpointRow.status == "completed",
                )
            )

    def save_checkpoint(
        self,
        run_id: str,
        phase: str,
        payload_path: Path | str | None,
        organization_id: str | None = None,
        status: str = "completed",
        error: str | None = None,
    ) -> None:
        with self.session() as session:
            existing = session.scalar(
                select(CheckpointRow).where(
                    CheckpointRow.run_id == run_id,
                    CheckpointRow.phase == phase,
                )
            )
            if existing:
                existing.status = status
                existing.payload_path = str(payload_path) if payload_path else None
                existing.organization_id = organization_id
                existing.error = error
                existing.updated_at = _utcnow()
            else:
                session.add(
                    CheckpointRow(
                        run_id=run_id,
                        phase=phase,
                        status=status,
                        payload_path=str(payload_path) if payload_path else None,
                        organization_id=organization_id,
                        error=error,
                    )
                )
            session.commit()

    def load_checkpoint_payload(self, run_id: str, phase: str) -> Any | None:
        row = self.get_checkpoint(run_id, phase)
        if not row or not row.payload_path:
            return None
        path = Path(row.payload_path)
        if not path.exists():
            return None
        return read_json(path)

    def completed_phases(self, run_id: str) -> set[str]:
        with self.session() as session:
            rows = session.scalars(
                select(CheckpointRow).where(
                    CheckpointRow.run_id == run_id,
                    CheckpointRow.status == "completed",
                )
            ).all()
            return {row.phase for row in rows}

    def add_cost(self, run_id: str, entry: dict[str, Any]) -> None:
        with self.session() as session:
            session.add(CostLedgerRow(run_id=run_id, **entry))
            session.commit()

    def total_cost(self, run_id: str) -> float:
        with self.session() as session:
            rows = session.scalars(
                select(CostLedgerRow).where(CostLedgerRow.run_id == run_id)
            ).all()
            return sum(r.actual_cost or r.estimated_cost or 0.0 for r in rows)

    def cost_entries(self, run_id: str) -> list[dict[str, Any]]:
        with self.session() as session:
            rows = session.scalars(
                select(CostLedgerRow).where(CostLedgerRow.run_id == run_id)
            ).all()
            return [
                {
                    "task_id": r.task_id,
                    "task_type": r.task_type,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "estimated_cost": r.estimated_cost,
                    "actual_cost": r.actual_cost,
                    "cache_hit": r.cache_hit,
                    "organization_id": r.organization_id,
                    "document_id": r.document_id,
                    "project_id": r.project_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
