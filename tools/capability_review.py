from __future__ import annotations

import argparse
import datetime
import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_notices(since: str | None) -> list[dict[str, Any]]:
    p = ROOT / "bus/capabilities.jsonl"
    if not p.exists():
        return []
    notes: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
            if "capability_notice" in obj:
                notes.append(obj["capability_notice"])
            elif "capability_sunset" in obj:
                notes.append(obj["capability_sunset"])
        except Exception:
            continue
    if since:
        try:
            cutoff = datetime.datetime.fromisoformat(since)
        except Exception:
            return notes
        filtered: list[dict[str, Any]] = []
        for notice in notes:
            date_str = notice.get("date") or notice.get("expires")
            if date_str:
                try:
                    parsed = datetime.datetime.fromisoformat(date_str.replace("Z", ""))
                    if parsed >= cutoff:
                        filtered.append(notice)
                except Exception:
                    filtered.append(notice)
        return filtered
    return notes


def render_report(notices: list[dict[str, Any]], out_path: pathlib.Path) -> None:
    lines = [
        "# Capability Review",
        "",
        "| Role | Capability | Level | First Seen | Expires | Tests | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for notice in notices:
        role = notice.get("from") or notice.get("role", "?")
        capability = notice.get("capability", "?")
        level = notice.get("level", notice.get("action", ""))
        tests = ", ".join(notice.get("tests_added", []))
        expires = notice.get("expires", notice.get("date", ""))
        lines.append(f"| {role} | {capability} | {level} | | {expires} | {tests} | {notice.get('reason', '')} |")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None, help="ISO date, e.g., 2025-09-01")
    ap.add_argument("--out", default="reports/capability_review.md")
    args = ap.parse_args()
    notices = load_notices(args.since)
    render_report(notices, ROOT / args.out)


if __name__ == "__main__":
    main()
