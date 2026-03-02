"""sonar_export.py — SonarQube Generic Issue Import adapter (Story 16.2).

Converts ruff and mypy tool output to SonarQube Generic Issue Import JSON format,
enabling external quality signals to appear in the SonarQube dashboard.

Usage:
    python scripts/sonar_export.py ruff ruff-report-raw.json ruff-sonar.json
    python scripts/sonar_export.py mypy mypy-report-raw.json mypy-sonar.json

Exit codes:
    0 — Conversion successful
    1 — Input file not found or parse error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Project root resolution
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _to_sonar_path(path_str: str, project_root: Path = _PROJECT_ROOT) -> str:
    """Convert an absolute or relative path to a SonarQube-compatible relative path.

    SonarQube requires paths relative to the project root using forward slashes.
    Absolute paths (e.g. from ruff on Windows) are stripped of the project root prefix.
    """
    p = Path(path_str)
    if p.is_absolute():
        try:
            rel = p.relative_to(project_root)
        except ValueError:
            print(
                f"WARNING: cannot make path relative to project root: {path_str}",
                file=sys.stderr,
            )
            rel = p
        return str(rel).replace("\\", "/")
    return str(p).replace("\\", "/")


# ---------------------------------------------------------------------------
# Task 1: Ruff adapter
# ---------------------------------------------------------------------------

def convert_ruff(input_path: Path, output_path: Path) -> int:
    """Convert ruff JSON output to SonarQube Generic Issue Import format.

    Ruff JSON format (``ruff check --output-format json``):
        [{"filename": "...", "location": {"row": 1, "column": 1},
          "code": "E501", "message": "..."}, ...]

    SonarQube mapping:
        engineId=ruff, severity=MAJOR, type=CODE_SMELL

    Args:
        input_path: Path to ruff JSON report.
        output_path: Path to write SonarQube-compatible JSON.

    Returns:
        Number of issues written.
    """
    raw = input_path.read_text(encoding="utf-8").strip()
    parsed = json.loads(raw) if raw else []
    if not isinstance(parsed, list):
        print(
            f"WARNING: ruff JSON is not a list (got {type(parsed).__name__}), treating as empty",
            file=sys.stderr,
        )
        parsed = []
    entries: list[Any] = parsed

    issues = []
    for entry in entries:
        filename = entry.get("filename", "")
        location = entry.get("location", {})
        row = location.get("row", 1)
        # ruff column is 1-based; SonarQube startColumn is 0-based
        col = max(0, location.get("column", 1) - 1)
        code = entry.get("code") or "unknown"
        message = entry.get("message", "")

        issues.append({
            "engineId": "ruff",
            "ruleId": code,
            "severity": "MAJOR",
            "type": "CODE_SMELL",
            "primaryLocation": {
                "message": message,
                "filePath": _to_sonar_path(filename),
                "textRange": {
                    "startLine": row,
                    "startColumn": col,
                },
            },
        })

    output_path.write_text(
        json.dumps({"issues": issues}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(issues)


# ---------------------------------------------------------------------------
# Task 2: Mypy adapter
# ---------------------------------------------------------------------------

# Regex for mypy plain-text output:
#   src/file.py:15:4: error: Incompatible return value type  [return-value]
_MYPY_TEXT_RE = re.compile(
    r"^(.+?):(\d+):(\d+):\s+(error|warning|note):\s+(.+?)(?:\s+\[([^\]]+)\])?\s*$"
)


def _parse_mypy_jsonl(content: str) -> list[dict[str, Any]]:
    """Parse mypy JSONL output (one JSON object per line)."""
    records: list[dict[str, Any]] = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"WARNING: skipped malformed mypy JSONL line: {line!r}", file=sys.stderr)
    return records


def _parse_mypy_text(content: str) -> list[dict[str, Any]]:
    """Parse mypy plain-text output as fallback when JSONL is unavailable."""
    records: list[dict[str, Any]] = []
    for line in content.splitlines():
        m = _MYPY_TEXT_RE.match(line.strip())
        if m:
            file, lineno, col, severity, message, code = m.groups()
            records.append({
                "file": file.replace("\\", "/"),
                "line": int(lineno),
                "column": int(col),
                "severity": severity,
                "message": message,
                "code": code or "mypy-error",
            })
    return records


def convert_mypy(input_path: Path, output_path: Path) -> int:
    """Convert mypy JSON/text output to SonarQube Generic Issue Import format.

    Supports:
    - JSONL format (``mypy --output json``, mypy 1.0+): detects by first char '{'
    - Plain-text format (``file:line:col: error: message  [code]``): fallback

    Only ``error`` severity entries are included (not ``note`` or ``warning``).

    SonarQube mapping:
        engineId=mypy, severity=CRITICAL, type=BUG

    Args:
        input_path: Path to mypy report.
        output_path: Path to write SonarQube-compatible JSON.

    Returns:
        Number of issues written.
    """
    content = input_path.read_text(encoding="utf-8").strip()

    records: list[dict[str, Any]] = []
    if content:
        first_line = content.splitlines()[0].strip()
        records = (
            _parse_mypy_jsonl(content)
            if first_line.startswith("{")
            else _parse_mypy_text(content)
        )

    issues = []
    for record in records:
        if record.get("severity") != "error":
            continue  # Only map type errors, skip notes/warnings

        file_path = record.get("file", "")
        line = record.get("line", 1)
        col = record.get("column", 0)
        message = record.get("message", "")
        code = record.get("code") or "mypy-error"

        issues.append({
            "engineId": "mypy",
            "ruleId": code,
            "severity": "CRITICAL",
            "type": "BUG",
            "primaryLocation": {
                "message": message,
                "filePath": _to_sonar_path(file_path),
                "textRange": {
                    "startLine": line,
                    "startColumn": col,
                },
            },
        })

    output_path.write_text(
        json.dumps({"issues": issues}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(issues)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on error."""
    parser = argparse.ArgumentParser(
        description="Convert tool output to SonarQube Generic Issue Import format",
    )
    subparsers = parser.add_subparsers(dest="tool", required=True)

    ruff_parser = subparsers.add_parser("ruff", help="Convert ruff JSON output")
    ruff_parser.add_argument("input_path", type=Path, help="Path to ruff JSON report")
    ruff_parser.add_argument("output_path", type=Path, help="Path for SonarQube JSON output")

    mypy_parser = subparsers.add_parser("mypy", help="Convert mypy JSON/text output")
    mypy_parser.add_argument("input_path", type=Path, help="Path to mypy report")
    mypy_parser.add_argument("output_path", type=Path, help="Path for SonarQube JSON output")

    args = parser.parse_args(argv)

    if not args.input_path.exists():
        print(f"ERROR: Input file not found: {args.input_path}", file=sys.stderr)
        return 1

    try:
        if args.tool == "ruff":
            count = convert_ruff(args.input_path, args.output_path)
            print(f"ruff: {count} issue(s) written to {args.output_path}")
        else:  # mypy
            count = convert_mypy(args.input_path, args.output_path)
            print(f"mypy: {count} issue(s) written to {args.output_path}")
    except (json.JSONDecodeError, OSError, TypeError, KeyError, AttributeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
