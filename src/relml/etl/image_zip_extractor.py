from __future__ import annotations

import hashlib
import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import structlog

DEFAULT_STAGE_ROOT = Path(os.environ.get("RELML_DATA_ROOT", "Data")) / "stage" / "images"
logger = structlog.get_logger(__name__)


def sha1_digest(data: bytes) -> str:
    digest = hashlib.sha1()
    digest.update(data)
    return digest.hexdigest()


@dataclass(slots=True)
class ExtractionResult:
    archives_processed: int
    images_written: int
    skipped: int


class ImageZipExtractor:
    def __init__(
        self,
        archives: Iterable[Path],
        domain: str,
        data_root: Path | None = None,
    ) -> None:
        self.archives = list(archives)
        self.domain = domain.upper()
        stage_root = DEFAULT_STAGE_ROOT if data_root is None else Path(data_root) / "stage" / "images"
        self.domain_root = stage_root / self.domain
        self.domain_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.domain_root / "manifest.jsonl"
        self._seen_hashes: set[str] = set()
        if self.manifest_path.exists():
            with self.manifest_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    digest = record.get("sha1")
                    if digest:
                        self._seen_hashes.add(digest)

    def run(self) -> ExtractionResult:
        archives_processed = 0
        written = 0
        skipped = 0
        records: list[str] = []
        for archive in sorted(self.archives):
            archives_processed += 1
            if not archive.exists():
                logger.warning("image_zip_extractor.missing_archive", archive=str(archive))
                continue
            try:
                with zipfile.ZipFile(archive, "r") as zf:
                    for info in zf.infolist():
                        filename = Path(info.filename).name
                        if "_" not in filename or not filename.lower().endswith(".jpg"):
                            logger.warning(
                                "image_zip_extractor.unexpected_name",
                                archive=str(archive),
                                name=info.filename,
                            )
                            continue
                        listing_key = filename.split("_", 1)[0]
                        with zf.open(info, "r") as member:
                            data = member.read()
                        digest = sha1_digest(data)
                        if digest in self._seen_hashes:
                            skipped += 1
                            continue
                        listing_dir = self.domain_root / listing_key
                        listing_dir.mkdir(parents=True, exist_ok=True)
                        image_path = listing_dir / filename
                        image_path.write_bytes(data)
                        record = {
                            "listing_key": listing_key,
                            "domain": self.domain,
                            "filename": filename,
                            "sha1": digest,
                            "source_zip": archive.as_posix(),
                            "extracted_path": image_path.as_posix(),
                        }
                        records.append(json.dumps(record))
                        self._seen_hashes.add(digest)
                        written += 1
            except zipfile.BadZipFile:
                logger.error("image_zip_extractor.bad_zip", archive=str(archive))
        if records:
            with self.manifest_path.open("a", encoding="utf-8") as handle:
                for line in records:
                    handle.write(line + "\n")
        return ExtractionResult(
            archives_processed=archives_processed,
            images_written=written,
            skipped=skipped,
        )


def extract_image_archives(
    archives: Iterable[Path],
    domain: str,
    data_root: Path | None = None,
) -> ExtractionResult:
    extractor = ImageZipExtractor(archives=archives, domain=domain, data_root=data_root)
    return extractor.run()
