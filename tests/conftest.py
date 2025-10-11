from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import psycopg
import pytest
from testcontainers.postgres import PostgresContainer

DDL_PATH = Path(__file__).resolve().parents[1] / "db" / "ddl" / "etl_ledger.sql"


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    """Spin up ephemeral Postgres for ETL integration tests."""

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


@pytest.fixture(autouse=True)
def clean_ledger_table(postgres_url: str) -> Iterator[None]:
    with psycopg.connect(postgres_url) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE etl_ledger")
        conn.commit()
    yield
