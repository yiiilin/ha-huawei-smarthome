#!/usr/bin/env python3
"""Validate product adapter paths and product identifiers without importing HA."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
import sys


ADAPTER_DIR = Path("custom_components/huawei_smarthome/device_adapters")


def _simple_name(target: ast.expr) -> str | None:
    return target.id if isinstance(target, ast.Name) else None


def _string_value(node: ast.expr, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            value = _string_value(statement.value, constants)
            if value is None:
                continue
            for target in statement.targets:
                name = _simple_name(target)
                if name is not None:
                    constants[name] = value
        elif isinstance(statement, ast.AnnAssign):
            name = _simple_name(statement.target)
            value = (
                _string_value(statement.value, constants)
                if statement.value is not None
                else None
            )
            if name is not None and value is not None:
                constants[name] = value
    return constants


def _adapter_class_name(tree: ast.Module) -> str | None:
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(_simple_name(target) == "ADAPTER" for target in statement.targets):
            continue
        value = statement.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            return value.func.id
    return None


def _adapter_prod_id(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    class_name = _adapter_class_name(tree)
    if class_name is None:
        raise ValueError("does not expose ADAPTER = AdapterClass()")

    adapter_class = next(
        (
            statement
            for statement in tree.body
            if isinstance(statement, ast.ClassDef) and statement.name == class_name
        ),
        None,
    )
    if adapter_class is None:
        raise ValueError(f"ADAPTER class {class_name!r} is not defined")

    constants = _module_string_constants(tree)
    values: list[str] = []
    for statement in adapter_class.body:
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value = statement.value
        else:
            continue
        if not any(_simple_name(target) == "prod_id" for target in targets):
            continue
        resolved = _string_value(value, constants)
        if resolved is not None:
            values.append(resolved.strip())

    if len(values) != 1 or not values[0]:
        raise ValueError("ADAPTER.prod_id must be one non-empty string")
    return values[0]


def _adapter_files(root: Path) -> list[Path]:
    directory = root / ADAPTER_DIR
    if not directory.is_dir():
        raise ValueError(f"adapter directory does not exist: {directory}")
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.name.casefold().startswith("prod_")
        and path.suffix.casefold() == ".py"
    )


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    files = _adapter_files(root)

    by_path: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        by_path[path.name.casefold()].append(path)
    for paths in by_path.values():
        if len(paths) > 1:
            errors.append(
                "case-insensitive duplicate adapter paths: "
                + ", ".join(str(path.relative_to(root)) for path in paths)
            )

    by_prod_id: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for path in files:
        try:
            prod_id = _adapter_prod_id(path)
        except (SyntaxError, ValueError) as error:
            errors.append(f"{path.relative_to(root)}: {error}")
            continue
        by_prod_id[prod_id.casefold()].append((path, prod_id))
    for entries in by_prod_id.values():
        if len(entries) > 1:
            errors.append(
                "duplicate adapter prod_id: "
                + ", ".join(
                    f"{prod_id} ({path.relative_to(root)})"
                    for path, prod_id in entries
                )
            )

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    try:
        errors = validate(root)
    except OSError as error:
        print(f"Adapter validation could not run: {error}", file=sys.stderr)
        return 2
    if errors:
        print("Product adapter validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(_adapter_files(root))} product adapters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
