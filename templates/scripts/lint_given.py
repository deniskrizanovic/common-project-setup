#!/usr/bin/env python3
"""GIVEN-clause lint gate (`lint:given`).

Every `#### Scenario:` in an OpenSpec spec MUST contain at least one
`- **GIVEN**` clause describing its initial state, somewhere in the scenario's
lines before the next `#### Scenario:`, `### Requirement:`, or `## ` boundary.
Scans both the archived baseline (`openspec/specs/**`) and unarchived change
deltas (`openspec/changes/*/specs/**`).

Pure filesystem, no network, offline-safe. Sibling of `lint_specs.py`.

Provenance: scaffold component `lint-gates`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCENARIO_RE = re.compile(r"^####\s+Scenario:\s*(.*)$")
GIVEN_RE = re.compile(r"^\s*[-*]\s*\*\*GIVEN\*\*")
BOUNDARY_RE = re.compile(r"^(####\s+Scenario:|###\s+Requirement:|##\s+)")


def collect_markdown_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(directory.rglob("*.md"))


def collect_spec_files(openspec_root: Path) -> list[Path]:
    files = list(collect_markdown_files(openspec_root / "specs"))
    changes_dir = openspec_root / "changes"
    if changes_dir.is_dir():
        for change in sorted(changes_dir.iterdir()):
            if change.is_dir():
                files.extend(collect_markdown_files(change / "specs"))
    return files


def find_violations(content: str, file: str = "<memory>") -> list[dict]:
    """Scenarios with no `- **GIVEN**` clause before the next boundary."""
    lines = content.splitlines()
    violations = []
    for i, line in enumerate(lines):
        match = SCENARIO_RE.match(line)
        if not match:
            continue
        scenario = match.group(1).strip() or "(untitled)"
        has_given = False
        for j in range(i + 1, len(lines)):
            if BOUNDARY_RE.match(lines[j]):
                break
            if GIVEN_RE.match(lines[j]):
                has_given = True
                break
        if not has_given:
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
            f"✓ spec given-clause: {len(files)} spec file(s) scanned, "
            "every scenario declares a GIVEN precondition"
        )
        return 0
    print(
        f"✗ spec given-clause: {len(violations)} scenario(s) missing a "
        "'- **GIVEN**' clause:\n",
        file=sys.stderr,
    )
    for v in violations:
        print(f"  {v['file']}:{v['line']}  Scenario: {v['scenario']}", file=sys.stderr)
    print(
        "\nEvery '#### Scenario:' must contain a '- **GIVEN**' clause describing "
        "its initial state, before the next scenario/requirement/heading boundary.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
