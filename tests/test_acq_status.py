from __future__ import annotations

import os
import uuid
from datetime import date
from typing import Any, Iterator, cast

import psycopg
import pytest
from psycopg import sql

from src.relml.etl.acq_status import ensure_tables, get_image_status, get_status, set_image_status, set_status


@pytest.fixture(scope="module")
def temp_conn() -> Iterator[tuple[psycopg.Connection, str]]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not configured for acquisition status tests.")
    assert database_url is not None
    conninfo = database_url.replace("+psycopg", "")
    try:
        conn = psycopg.connect(conninfo)
    except psycopg.OperationalError:
        pytest.skip("DATABASE_URL host not reachable for acquisition status tests.")
    conn.autocommit = True
    schema = f"acq_test_{uuid.uuid4().hex}"
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
    try:
        yield conn, schema
    finally:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        conn.close()


def test_ensure_tables_creates_daily_and_image_tables(temp_conn: tuple[psycopg.Connection, str]) -> None:
    conn, schema = temp_conn
    ensure_tables(conn, schema=schema)

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = %s
                """
            ),
            (schema,),
        )
        tables = {row[0] for row in cur.fetchall()}

    assert "acq_daily_status" in tables
    assert "acq_image_status" in tables


def test_set_status_upserts_and_returns_timezone_aware_timestamp(temp_conn: tuple[psycopg.Connection, str]) -> None:
    conn, schema = temp_conn
    ensure_tables(conn, schema=schema)

    day = date(2025, 10, 9)
    first = set_status(
        conn,
        day,
        "MISSING",
        files_count=0,
        notes="initial run",
        schema=schema,
    )
    assert first.status == "MISSING"
    assert first.files_count == 0  # noqa: PLR2004
    assert first.notes == "initial run"
    assert first.last_attempt_ts.tzinfo is not None

    second = set_status(
        conn,
        day,
        "COMPLETE",
        files_count=1200,
        notes="backfilled",
        schema=schema,
    )
    assert second.status == "COMPLETE"
    assert second.files_count == 1200  # noqa: PLR2004
    assert second.notes == "backfilled"
    assert second.last_attempt_ts >= first.last_attempt_ts

    fetched = get_status(conn, day, schema=schema)
    assert fetched is not None
    assert fetched.status == "COMPLETE"
    assert fetched.files_count == 1200  # noqa: PLR2004
    assert fetched.notes == "backfilled"


def test_set_image_status_upserts_per_listing_state(temp_conn: tuple[psycopg.Connection, str]) -> None:
    conn, schema = temp_conn
    ensure_tables(conn, schema=schema)

    first = set_image_status(
        conn,
        listing_key="123456",
        domain="SALE",
        status="no_images",
        notes="not provided",
        schema=schema,
    )
    assert first.status == "no_images"
    assert first.last_attempt_ts.tzinfo is not None

    second = set_image_status(
        conn,
        listing_key="123456",
        domain="SALE",
        status="complete",
        notes="downloaded",
        schema=schema,
    )
    assert second.status == "complete"
    row = get_image_status(conn, listing_key="123456", domain="SALE", schema=schema)
    assert row is not None
    assert row.status == "complete"
    assert row.notes == "downloaded"


def test_invalid_status_values_raise(temp_conn: tuple[psycopg.Connection, str]) -> None:
    conn, schema = temp_conn
    ensure_tables(conn, schema=schema)

    with pytest.raises(ValueError):
        set_status(conn, date.today(), cast(Any, "UNKNOWN"), schema=schema)

    with pytest.raises(ValueError):
        set_image_status(conn, "1", "SALE", "invalid", schema=schema)
