from __future__ import annotations

import json
from pathlib import Path

import pytest

from budget_extractor.checkpoint import CheckpointStore


def test_resume_manifest_roundtrip(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    manifest = store.load_or_create(
        document_hash="hash123",
        configuration_hash="cfg123",
        resume=False,
        force=False,
    )
    assert manifest.document_hash == "hash123"
    store.mark_chunk_completed("chunk_0001")
    store.set_ocr_cache("ocrkey", tmp_path / "ocr.json")
    (tmp_path / "ocr.json").write_text("{}", encoding="utf-8")

    store2 = CheckpointStore(tmp_path)
    loaded = store2.load_or_create(
        document_hash="hash123",
        configuration_hash="cfg123",
        resume=True,
        force=False,
    )
    assert "chunk_0001" in loaded.completed_chunks
    assert store2.get_ocr_cache("ocrkey") is not None


def test_resume_rejects_document_mismatch(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    store.load_or_create(
        document_hash="hashA",
        configuration_hash="cfg",
        resume=False,
        force=False,
    )
    with pytest.raises(ValueError, match="document hash"):
        CheckpointStore(tmp_path).load_or_create(
            document_hash="hashB",
            configuration_hash="cfg",
            resume=True,
            force=False,
        )


def test_failed_chunk_status_persisted(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    store.load_or_create(
        document_hash="h",
        configuration_hash="c",
        resume=False,
        force=False,
    )
    paths = store.chunk_paths("chunk_0003")
    status = {
        "chunk_id": "chunk_0003",
        "validation_status": "failed",
        "error_details": "invalid json",
    }
    store.write_json(paths["status"], status)
    store.mark_chunk_failed("chunk_0003")

    reloaded = json.loads(store.manifest_path.read_text(encoding="utf-8"))
    assert "chunk_0003" in reloaded["failed_chunks"]
    assert paths["status"].exists()
