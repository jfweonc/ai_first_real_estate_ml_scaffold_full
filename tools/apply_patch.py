from __future__ import annotations

import argparse
import pathlib

from unidiff import PatchSet

ROOT = pathlib.Path(__file__).resolve().parents[1]


def apply_unified_diff(diff_text: str) -> None:
    patch = PatchSet(diff_text)
    for patched_file in patch:
        target = ROOT / patched_file.path
        original = target.read_text(encoding="utf-8") if target.exists() else ""
        lines = original.splitlines(keepends=True)
        offset = 0
        for hunk in patched_file:
            start = hunk.source_start - 1 + offset
            length = hunk.source_length
            repl = []
            for hunk_line in hunk:
                if hunk_line.is_added or hunk_line.is_context:
                    repl.append(hunk_line.value)
            lines[start : start + length] = repl
            offset += len(repl) - length
        new_content = "".join(lines)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content, encoding="utf-8")
        print(f"Applied: {patched_file.path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", required=True, help="Path to unified diff file")
    args = ap.parse_args()
    diff_text = pathlib.Path(args.diff).read_text(encoding="utf-8")
    apply_unified_diff(diff_text)


if __name__ == "__main__":
    main()
