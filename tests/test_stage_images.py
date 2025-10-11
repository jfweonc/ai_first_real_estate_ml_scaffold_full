from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.relml.etl.stage_images import StageImagesResult, stage_images


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


@pytest.mark.integration
def test_stage_images_summarizes_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))
    manifest = ingest_root / "images.jsonl"

    _write_manifest(
        manifest,
        [
            {
                "listing_key": "HAR123",
                "domain": "TEST",
                "filename": "HAR123_1.jpg",
                "sha1": "a" * 40,
                "source_file": "HAR123/1.jpg",
            },
            {
                "listing_key": "HAR123",
                "domain": "TEST",
                "filename": "HAR123_2.jpg",
                "sha1": "b" * 40,
                "source_file": "HAR123/2.jpg",
            },
            {
                "listing_key": "HAR124",
                "domain": "TEST",
                "filename": "HAR124_1.jpg",
                "sha1": "c" * 40,
                "source_file": "HAR124/1.jpg",
            },
        ],
    )

    result = stage_images(ingest_root, dry_run=False)

    assert isinstance(result, StageImagesResult)
    assert result.discovered_files == 1  # noqa: PLR2004
    assert result.staged_rows == 2  # noqa: PLR2004
    assert result.stage_file is not None

    stage_path = Path(result.stage_file)
    assert stage_path.exists()

    content = json.loads(stage_path.read_text(encoding="utf-8"))
    assert content["images_total"] == 3  # noqa: PLR2004
    per_listing = {row["listing_key"]: row for row in content["listings"]}

    assert per_listing["HAR123"]["images_count"] == 2  # noqa: PLR2004
    assert per_listing["HAR123"]["status"] == "complete"
    assert per_listing["HAR124"]["status"] == "partial"


def test_stage_images_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))
    manifest = ingest_root / "images.jsonl"

    _write_manifest(
        manifest,
        [
            {
                "listing_key": "HAR999",
                "domain": "TEST",
                "filename": "HAR999_1.jpg",
                "sha1": "d" * 40,
            }
        ],
    )

    result = stage_images(ingest_root, dry_run=True)

    assert result.stage_file is None
    assert result.staged_rows == 0  # noqa: PLR2004
    stage_file = data_root / "stage" / "images_summary.json"
    assert not stage_file.exists()


def test_stage_images_ignores_invalid_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))
    manifest = ingest_root / "images.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "\n".join(
            [
                '{"listing_key": "HAR700", "domain": "TEST", "filename": "HAR700_1.jpg", "sha1": "' + "e" * 40 + '"}',
                "{invalid-json}",
                '{"listing_key": "HAR701", "domain": "TEST", "filename": "HAR701_1.jpg", "sha1": "' + "f" * 40 + '"}',
            ]
        ),
        encoding="utf-8",
    )

    result = stage_images(ingest_root, dry_run=False)

    assert result.staged_rows == 2  # noqa: PLR2004
    stage_path = Path(result.stage_file or "")
    payload = json.loads(stage_path.read_text(encoding="utf-8"))
    ids = {entry["listing_key"] for entry in payload["listings"]}
    assert ids == {"HAR700", "HAR701"}


def test_stage_images_skips_rows_missing_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    ingest_root = tmp_path / "ingest"
    monkeypatch.setenv("RELML_DATA_ROOT", str(data_root))
    manifest = ingest_root / "images.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "\n".join(
            [
                '{"listing_key": "HAR800", "domain": "TEST", "filename": "HAR800_1.jpg", "sha1": "' + "g" * 40 + '"}',
                '{"listing_key": "", "domain": "TEST", "filename": "HAR800_2.jpg", "sha1": "' + "h" * 40 + '"}',
            ]
        ),
        encoding="utf-8",
    )

    result = stage_images(ingest_root, dry_run=False)

    assert result.staged_rows == 1  # noqa: PLR2004
    payload = json.loads(Path(result.stage_file or "").read_text(encoding="utf-8"))
    assert len(payload["listings"]) == 1  # noqa: PLR2004
    assert payload["listings"][0]["listing_key"] == "HAR800"
