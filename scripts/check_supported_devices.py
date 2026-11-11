#!/usr/bin/env python3
"""Validate unique product IDs in the supported-device list."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys


SUPPORTED_DEVICES = Path("docs/supported-devices.md")


def _product_rows(path: Path) -> dict[str, list[tuple[int, str]]]:
    rows: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        prod_id = cells[0].strip("`").strip()
        if not prod_id or prod_id.casefold() == "prodid" or set(prod_id) <= {"-", " "}:
            continue
        rows[prod_id.casefold()].append((line_number, prod_id))
    return rows


def main() -> int:
    path = Path(__file__).resolve().parents[1] / SUPPORTED_DEVICES
    try:
        rows = _product_rows(path)
    except (OSError, UnicodeError) as error:
        print(f"Supported-device list validation failed: {error}", file=sys.stderr)
        return 2

    duplicates = [entries for entries in rows.values() if len(entries) > 1]
    if duplicates:
        print("Duplicate prodId values in supported-device list:", file=sys.stderr)
        for entries in duplicates:
            details = ", ".join(f"{prod_id} (line {line})" for line, prod_id in entries)
            print(f"- {details}", file=sys.stderr)
        return 1

    print(f"Validated {len(rows)} supported-device prodIds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
