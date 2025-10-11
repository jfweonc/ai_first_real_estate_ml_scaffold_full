from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from src.relml.etl.image_zip_extractor import ExtractionResult, ImageZipExtractor

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "images_zip"


def _make_zip(
    target: Path,
    entries: list[tuple[str, bytes]],
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)


@pytest.fixture
def sample_zip(tmp_path: Path) -> Path:
    archive = tmp_path / "har_sale_batch.zip"
    _make_zip(
        archive,
        [
            ("123456_1.jpg", b"first"),
            ("123456_2.jpg", b"second"),
            ("654321_1.jpg", b"third"),
        ],
    )
    return archive


def test_extract_image_archives_writes_per_listing_directories(sample_zip: Path, tmp_path: Path) -> None:
    data_root = tmp_path / "Data"
    extractor = ImageZipExtractor(
        archives=[sample_zip],
        domain="SALE",
        data_root=data_root,
    )

    result = extractor.run()

    assert isinstance(result, ExtractionResult)
    assert result.archives_processed == 1  # noqa: PLR2004
    assert result.images_written == 3  # noqa: PLR2004
    manifest_path = data_root / "stage" / "images" / "SALE" / "manifest.jsonl"
    assert manifest_path.exists()
    contents = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(contents) == 3  # noqa: PLR2004
    entries = [json.loads(line) for line in contents]
    hashes = {entry["sha1"] for entry in entries}
    assert len(hashes) == 3  # noqa: PLR2004
    listing_dirs = [
        data_root / "stage" / "images" / "SALE" / "123456",
        data_root / "stage" / "images" / "SALE" / "654321",
    ]
    for directory in listing_dirs:
        assert directory.exists()
    image_files = sorted((data_root / "stage" / "images" / "SALE").glob("*/*.jpg"))
    assert len(image_files) == 3  # noqa: PLR2004


def test_extract_image_archives_skips_duplicates_on_rerun(sample_zip: Path, tmp_path: Path) -> None:
    data_root = tmp_path / "Data"
    extractor = ImageZipExtractor(
        archives=[sample_zip],
        domain="SALE",
        data_root=data_root,
    )
    first = extractor.run()
    assert first.images_written == 3  # noqa: PLR2004
    second = extractor.run()
    assert second.images_written == 0  # noqa: PLR2004
    manifest_path = data_root / "stage" / "images" / "SALE" / "manifest.jsonl"
    assert len(manifest_path.read_text(encoding="utf-8").splitlines()) == 3  # noqa: PLR2004


def test_extract_image_archives_appends_new_images(sample_zip: Path, tmp_path: Path) -> None:
    data_root = tmp_path / "Data"
    extractor = ImageZipExtractor(
        archives=[sample_zip],
        domain="SALE",
        data_root=data_root,
    )
    extractor.run()
    another = tmp_path / "har_sale_batch2.zip"
    _make_zip(
        another,
        [
            ("123456_3.jpg", b"new"),
            ("777777_1.jpg", b"fresh"),
        ],
    )
    extractor2 = ImageZipExtractor(
        archives=[another],
        domain="SALE",
        data_root=data_root,
    )
    result = extractor2.run()
    assert result.images_written == 2  # noqa: PLR2004
    manifest_path = data_root / "stage" / "images" / "SALE" / "manifest.jsonl"
    entries = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
    by_listing = {(item["listing_key"], item["filename"]) for item in entries}
    assert ("123456", "123456_3.jpg") in by_listing
    assert ("777777", "777777_1.jpg") in by_listing
