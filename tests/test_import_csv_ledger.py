from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import psycopg
import pytest
from testcontainers.postgres import PostgresContainer

from src.relml.etl import import_csv

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "p1"
DDL_PATH = Path(__file__).resolve().parents[1] / "db" / "ddl" / "etl_ledger.sql"
EXPECTED_ROW_COUNT = 2
EXPECTED_STATUS = "ingested"


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    """Spin up ephemeral Postgres for ledger tests."""

    with PostgresContainer("postgres:16", username="app", password="app", dbname="real_estate_ml_test") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")
        previous = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = url
        statements = [stmt.strip() for stmt in DDL_PATH.read_text(encoding="utf-8").split(";") if stmt.strip()]
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
            conn.commit()
        try:
            yield url
        finally:
            if previous is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous


def _fetch_ledger_rows(url: str) -> list[tuple[str, str, str, int, int, int]]:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT file_hash, raw_source, status, rows_total, rows_clean, rows_quarantined FROM etl_ledger")
        return list(cur.fetchall())


@pytest.mark.integration
def test_import_csv_writes_ledger_entries_and_is_idempotent(postgres_url: str) -> None:
    result1 = import_csv(FIXTURE_ROOT, dry_run=False)

    assert result1.processed_files == 1
    assert result1.skipped_files == 0

    rows = _fetch_ledger_rows(postgres_url)
    assert len(rows) == 1
    (
        file_hash,
        raw_source,
        status,
        rows_total,
        rows_clean,
        rows_quarantined,
    ) = rows[0]
    assert status == EXPECTED_STATUS
    assert rows_total == EXPECTED_ROW_COUNT
    assert rows_clean == EXPECTED_ROW_COUNT
    assert result1.ledgers and result1.ledgers[0]["status"] == EXPECTED_STATUS
    assert rows_quarantined == 0
    assert raw_source.endswith("raw_listings_sample.csv")

    result2 = import_csv(FIXTURE_ROOT, dry_run=False)
    assert result2.processed_files == 0
    assert result2.skipped_files == 1
    assert result2.ledgers and result2.ledgers[0]["status"] == EXPECTED_STATUS

    rows_after = _fetch_ledger_rows(postgres_url)
    assert len(rows_after) == 1
    assert rows_after[0][2] == EXPECTED_STATUS
