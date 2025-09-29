from __future__ import annotations
import argparse, json, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parents[1]

def load_notices(since: str | None):
    p = ROOT / "bus/capabilities.jsonl"
    if not p.exists():
        return []
    notes = []
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
        filtered = []
        for n in notes:
            d = n.get("date") or n.get("expires")
            if d:
                try:
                    di = datetime.datetime.fromisoformat(d.replace("Z",""))
                    if di >= cutoff:
                        filtered.append(n)
                except Exception:
                    filtered.append(n)
        return filtered
    return notes

def render_report(notices, out_path: pathlib.Path):
    lines = ["# Capability Review", "", "| Role | Capability | Level | First Seen | Expires | Tests | Notes |", "|---|---|---|---|---|---|---|"]
    for n in notices:
        role = n.get("from") or n.get("role","?")
        cap = n.get("capability","?")
        lvl = n.get("level", n.get("action",""))
        tests = ", ".join(n.get("tests_added", []))
        exp = n.get("expires", n.get("date",""))
        lines.append(f"| {role} | {cap} | {lvl} | | {exp} | {tests} | {n.get('reason','')} |")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None, help="ISO date, e.g., 2025-09-01")
    ap.add_argument("--out", default="reports/capability_review.md")
    args = ap.parse_args()
    notices = load_notices(args.since)
    render_report(notices, (ROOT / args.out))

if __name__ == "__main__":
    main()
