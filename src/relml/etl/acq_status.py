from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

import psycopg
from psycopg import sql

DailyStatus = Literal["COMPLETE", "MISSING"]
IMAGE_STATUSES: set[str] = {"unknown", "complete", "no_images", "partial", "failed"}


@dataclass(slots=True)
class DailyStatusRow:
    date: date
    status: DailyStatus
    last_attempt_ts: datetime
    files_count: int | None
    notes: str | None


@dataclass(slots=True)
class ImageStatusRow:
    listing_key: str
    domain: str
    status: str
    last_attempt_ts: datetime
    notes: str | None


def _qualified(name: str, schema: str | None) -> sql.SQL:
    if schema:
        return sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(name))
    return sql.Identifier(name)


def ensure_tables(conn: psycopg.Connection, *, schema: str | None = None) -> None:
    with conn.cursor() as cur:
        if schema:
            cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        cur.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {} (
                    date date PRIMARY KEY,
                    status text NOT NULL CHECK (status IN ('COMPLETE','MISSING')),
                    last_attempt_ts timestamptz,
                    files_count int,
                    notes text
                )
                """
            ).format(_qualified("acq_daily_status", schema))
        )
        cur.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {} (
                    listing_key text NOT NULL,
                    domain text NOT NULL,
                    status text NOT NULL CHECK (status IN ('unknown','complete','no_images','partial','failed')),
                    last_attempt_ts timestamptz,
                    notes text,
                    PRIMARY KEY (listing_key, domain)
                )
                """
            ).format(_qualified("acq_image_status", schema))
        )
    conn.commit()


def _timestamp(value: datetime | None) -> datetime:
    if value:
        return value
    return datetime.now(timezone.utc)


def set_status(  # noqa: PLR0913
    conn: psycopg.Connection,
    day: date,
    status: DailyStatus,
    *,
    files_count: int | None = None,
    notes: str | None = None,
    last_attempt_ts: datetime | None = None,
    schema: str | None = None,
) -> DailyStatusRow:
    if status not in {"COMPLETE", "MISSING"}:
        raise ValueError(f"Unsupported status: {status}")
    ts = _timestamp(last_attempt_ts)
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {} (date, status, last_attempt_ts, files_count, notes)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (date) DO UPDATE
                SET status = EXCLUDED.status,
                    last_attempt_ts = EXCLUDED.last_attempt_ts,
                    files_count = EXCLUDED.files_count,
                    notes = EXCLUDED.notes
                RETURNING date, status, last_attempt_ts, files_count, notes
                """
            ).format(_qualified("acq_daily_status", schema)),
            (day, status, ts, files_count, notes),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return DailyStatusRow(*row)


def get_status(
    conn: psycopg.Connection,
    day: date,
    *,
    schema: str | None = None,
) -> DailyStatusRow | None:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                """
                SELECT date, status, last_attempt_ts, files_count, notes
                FROM {}
                WHERE date = %s
                """
            ).format(_qualified("acq_daily_status", schema)),
            (day,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return DailyStatusRow(*row)


def set_image_status(  # noqa: PLR0913
    conn: psycopg.Connection,
    listing_key: str,
    domain: str,
    status: str,
    *,
    notes: str | None = None,
    last_attempt_ts: datetime | None = None,
    schema: str | None = None,
) -> ImageStatusRow:
    status_lower = status.lower()
    if status_lower not in IMAGE_STATUSES:
        raise ValueError(f"Unsupported image status: {status}")
    ts = _timestamp(last_attempt_ts)
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                """
                INSERT INTO {} (listing_key, domain, status, last_attempt_ts, notes)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (listing_key, domain) DO UPDATE
                SET status = EXCLUDED.status,
                    last_attempt_ts = EXCLUDED.last_attempt_ts,
                    notes = EXCLUDED.notes
                RETURNING listing_key, domain, status, last_attempt_ts, notes
                """
            ).format(_qualified("acq_image_status", schema)),
            (listing_key, domain.upper(), status_lower, ts, notes),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return ImageStatusRow(*row)


def get_image_status(
    conn: psycopg.Connection,
    *,
    listing_key: str,
    domain: str,
    schema: str | None = None,
) -> ImageStatusRow | None:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                """
                SELECT listing_key, domain, status, last_attempt_ts, notes
                FROM {}
                WHERE listing_key = %s AND domain = %s
                """
            ).format(_qualified("acq_image_status", schema)),
            (listing_key, domain.upper()),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return ImageStatusRow(*row)
