#!/usr/bin/env python3
"""Traceability lint gate (`lint:specs`).

Every `#### Scenario:` in an OpenSpec spec MUST be immediately followed (first
non-empty line) by a `> **Tests:**` line citing the test(s) that exercise it,
or the literal word `none` when no test exists yet. Scans both the archived
baseline (`openspec/specs/**`) and unarchived change deltas
(`openspec/changes/*/specs/**`).

Pure filesystem, no network, offline-safe. Language-agnostic reimplementation
of collaborativegherkin's Node gate so non-Node projects need no toolchain.

Provenance: scaffold component `lint-gates`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCENARIO_RE = re.compile(r"^####\s+Scenario:\s*(.*)$")
TESTS_RE = re.compile(r"^>\s*\*\*Tests:\*\*")


def collect_markdown_files(directory: Path) -> list[Path]:
    """Recursively collect every `.md` file under `directory` (empty if absent)."""
    if not directory.is_dir():
        return []
    return sorted(directory.rglob("*.md"))


def collect_spec_files(openspec_root: Path) -> list[Path]:
    """Archived baseline plus every unarchived change delta."""
    files = list(collect_markdown_files(openspec_root / "specs"))
    changes_dir = openspec_root / "changes"
    if changes_dir.is_dir():
        for change in sorted(changes_dir.iterdir()):
            if change.is_dir():
                files.extend(collect_markdown_files(change / "specs"))
    return files


def find_violations(content: str, file: str = "<memory>") -> list[dict]:
    """Scenarios whose first non-empty following line is not a `> **Tests:**`."""
    lines = content.splitlines()
    violations = []
    for i, line in enumerate(lines):
        match = SCENARIO_RE.match(line)
        if not match:
            continue
        scenario = match.group(1).strip() or "(untitled)"
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if j >= len(lines) or not TESTS_RE.match(lines[j]):
            violations.append({"file": file, "line": i + 1, "scenario": scenario})
    return violations


def lint_files(files: list[Path]) -> list[dict]:
    violations = []
    for file in files:
        violations.extend(find_violations(file.read_text(encoding="utf-8"), str(file)))
    return violations


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    openspec_root = root / "openspec"
    files = collect_spec_files(openspec_root)
    violations = lint_files(files)
    if not violations:
        print(
            f"✓ spec traceability: {len(files)} spec file(s) scanned, "
            "every scenario declares its tests"
        )
        return 0
    print(
        f"✗ spec traceability: {len(violations)} scenario(s) missing a "
        "'> **Tests:**' line:\n",
        file=sys.stderr,
    )
    for v in violations:
        print(f"  {v['file']}:{v['line']}  Scenario: {v['scenario']}", file=sys.stderr)
    print(
        "\nEvery '#### Scenario:' must be immediately followed by a "
        "'> **Tests:**' line citing the test(s), or '> **Tests:** none' "
        "when untested.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
