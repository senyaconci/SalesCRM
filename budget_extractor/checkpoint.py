"""Checkpoint and resume manifest management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from budget_extractor.utils import atomic_write_json, ensure_dir, read_json


@dataclass
class RunManifest:
    document_hash: str = ""
    configuration_hash: str = ""
    completed_chunks: list[str] = field(default_factory=list)
    failed_chunks: list[str] = field(default_factory=list)
    ocr_cache: dict[str, str] = field(default_factory=dict)
    extraction_cache: dict[str, str] = field(default_factory=dict)
    consolidation_completed: bool = False
    exports_completed: bool = False
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_hash": self.document_hash,
            "configuration_hash": self.configuration_hash,
            "completed_chunks": list(self.completed_chunks),
            "failed_chunks": list(self.failed_chunks),
            "ocr_cache": dict(self.ocr_cache),
            "extraction_cache": dict(self.extraction_cache),
            "consolidation_completed": self.consolidation_completed,
            "exports_completed": self.exports_completed,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunManifest:
        return cls(
            document_hash=str(data.get("document_hash", "")),
            configuration_hash=str(data.get("configuration_hash", "")),
            completed_chunks=list(data.get("completed_chunks", [])),
            failed_chunks=list(data.get("failed_chunks", [])),
            ocr_cache=dict(data.get("ocr_cache", {})),
            extraction_cache=dict(data.get("extraction_cache", {})),
            consolidation_completed=bool(data.get("consolidation_completed", False)),
            exports_completed=bool(data.get("exports_completed", False)),
            updated_at=str(data.get("updated_at", "")),
        )


class CheckpointStore:
    """Filesystem-backed checkpoint store with atomic writes."""

    def __init__(self, output_dir: str | Path):
        self.output_dir = ensure_dir(output_dir)
        self.checkpoint_dir = ensure_dir(self.output_dir / "checkpoints")
        self.manifest_path = self.output_dir / "run_manifest.json"
        self.manifest = RunManifest()

    def load_or_create(
        self,
        *,
        document_hash: str,
        configuration_hash: str,
        resume: bool,
        force: bool,
    ) -> RunManifest:
        if resume and self.manifest_path.exists() and not force:
            existing = RunManifest.from_dict(read_json(self.manifest_path))
            if existing.document_hash and existing.document_hash != document_hash:
                raise ValueError(
                    "Resume requested but document hash does not match the existing manifest."
                )
            if (
                existing.configuration_hash
                and existing.configuration_hash != configuration_hash
            ):
                raise ValueError(
                    "Resume requested but configuration is incompatible with the existing manifest."
                )
            self.manifest = existing
            return self.manifest

        self.manifest = RunManifest(
            document_hash=document_hash,
            configuration_hash=configuration_hash,
        )
        self.save_manifest()
        return self.manifest

    def save_manifest(self) -> None:
        self.manifest.updated_at = datetime.now(timezone.utc).isoformat()
        atomic_write_json(self.manifest_path, self.manifest.to_dict())

    def chunk_paths(self, chunk_id: str) -> dict[str, Path]:
        return {
            "input": self.checkpoint_dir / f"{chunk_id}_input.txt",
            "raw_response": self.checkpoint_dir / f"{chunk_id}_raw_response.json",
            "validated": self.checkpoint_dir / f"{chunk_id}_validated.json",
            "status": self.checkpoint_dir / f"{chunk_id}_status.json",
        }

    def write_chunk_input(self, chunk_id: str, text: str) -> Path:
        path = self.chunk_paths(chunk_id)["input"]
        path.write_text(text, encoding="utf-8")
        return path

    def write_json(self, path: Path, data: Any) -> None:
        atomic_write_json(path, data)

    def mark_chunk_completed(self, chunk_id: str) -> None:
        if chunk_id not in self.manifest.completed_chunks:
            self.manifest.completed_chunks.append(chunk_id)
        if chunk_id in self.manifest.failed_chunks:
            self.manifest.failed_chunks = [
                item for item in self.manifest.failed_chunks if item != chunk_id
            ]
        self.manifest.extraction_cache[chunk_id] = str(
            self.chunk_paths(chunk_id)["validated"]
        )
        self.save_manifest()

    def mark_chunk_failed(self, chunk_id: str) -> None:
        if chunk_id not in self.manifest.failed_chunks:
            self.manifest.failed_chunks.append(chunk_id)
        if chunk_id in self.manifest.completed_chunks:
            self.manifest.completed_chunks = [
                item for item in self.manifest.completed_chunks if item != chunk_id
            ]
        self.save_manifest()

    def is_chunk_completed(self, chunk_id: str) -> bool:
        paths = self.chunk_paths(chunk_id)
        return (
            chunk_id in self.manifest.completed_chunks
            and paths["validated"].exists()
            and paths["status"].exists()
        )

    def set_ocr_cache(self, key: str, path: str | Path) -> None:
        self.manifest.ocr_cache[key] = str(path)
        self.save_manifest()

    def get_ocr_cache(self, key: str) -> Path | None:
        value = self.manifest.ocr_cache.get(key)
        if not value:
            return None
        path = Path(value)
        return path if path.exists() else None

    def mark_consolidation_completed(self) -> None:
        self.manifest.consolidation_completed = True
        self.save_manifest()

    def mark_exports_completed(self) -> None:
        self.manifest.exports_completed = True
        self.save_manifest()

    def load_validated_chunks(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for chunk_id in self.manifest.completed_chunks:
            path = self.chunk_paths(chunk_id)["validated"]
            if path.exists():
                results.append(read_json(path))
        return results
