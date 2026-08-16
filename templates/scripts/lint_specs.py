#!/usr/bin/env python3
"""Traceability lint gate (`lint:specs`).

Every `#### Scenario:` in an OpenSpec spec MUST be immediately followed (first
non-empty line) by a `> **Tests:**` line citing the test(s) that exercise it,
or the literal word `none` when no test exists yet. Scans both the archived
baseline (`openspec/specs/**`) and unarchived change deltas
(`openspec/changes/*/specs/**`).

Beyond line-presence, a non-`none` citation MUST resolve to a test that
actually exists in the project's test suite: the gate discovers candidate test
functions and files (driven by the project's declared `Testing:` technology in
`openspec/config.yaml`) and fails when a cited identifier resolves to nothing.
The literal `none` is a tracked exemption — counted and reported, and failed
only when an optional `none`-share threshold (`.scaffold/gates.json`) is
exceeded.

Pure filesystem, no network, offline-safe. Reads test *source*; it never
executes the suite. Language-agnostic reimplementation of collaborativegherkin's
Node gate so non-Node projects need no toolchain.

Provenance: scaffold component `lint-gates`.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCENARIO_RE = re.compile(r"^####\s+Scenario:\s*(.*)$")
TESTS_RE = re.compile(r"^>\s*\*\*Tests:\*\*")

# Directories never worth scanning for test source.
_SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".tox", "openspec",
}

# Discovery patterns keyed by a substring that may appear in the `Testing:`
# answer. `func` is a compiled regex whose group(1) is a test-function name;
# omit it for stacks where a file-path citation is the unit of resolution.
# To extend: add an entry here mapping a new `Testing:` keyword to its globs
# (and optional function-name regex). Order matters — first substring hit wins.
TECH_PATTERNS = [
    (
        ("pytest", "python", "py.test"),
        {
            "globs": ["**/test_*.py", "**/*_test.py"],
            "func": re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)\s*\("),
        },
    ),
    (
        ("jest", "vitest", "mocha", "jasmine", "typescript", "javascript"),
        {
            "globs": [
                "**/*.test.js", "**/*.test.ts", "**/*.test.jsx", "**/*.test.tsx",
                "**/*.spec.js", "**/*.spec.ts", "**/*.spec.jsx", "**/*.spec.tsx",
            ],
            # `it('name')` / `test('name')` / `describe('name')` titles.
            "func": re.compile(r"""(?:^|\b)(?:it|test|describe)\s*\(\s*['"`]([^'"`]+)['"`]"""),
        },
    ),
    (
        ("go test", "golang", "go"),
        {
            "globs": ["**/*_test.go"],
            "func": re.compile(r"^\s*func\s+(Test\w*)\s*\("),
        },
    ),
]

# Default pattern set (pytest) used when the declared technology is unrecognized.
_DEFAULT_PATTERNS = TECH_PATTERNS[0][1]


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


# --------------------------------------------------------------------------- #
# Test-technology mapping + discovery
# --------------------------------------------------------------------------- #
def read_testing_answer(openspec_root: Path) -> str | None:
    """Extract the `Testing:` answer from config.yaml's `context:` block.

    The value lives inside a `context: |` block scalar (prose to YAML), so we
    keyword-scan the raw text for a `Testing: <answer>` line rather than parse a
    typed field. Returns the answer text, or None when absent.
    """
    cfg = openspec_root / "config.yaml"
    if not cfg.is_file():
        return None
    try:
        text = cfg.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"(?im)^\s*-?\s*Testing\s*:\s*(.+?)\s*$", text)
    return m.group(1).strip() if m else None


def discovery_patterns(answer: str | None) -> tuple[dict, bool]:
    """Map a `Testing:` answer to discovery patterns.

    Returns (patterns, recognized). When the answer matches no known
    technology (or is absent), returns the default pattern set with
    recognized=False so callers can log the fallback.
    """
    if answer:
        low = answer.lower()
        for keys, patterns in TECH_PATTERNS:
            if any(k in low for k in keys):
                return patterns, True
    return _DEFAULT_PATTERNS, False


def _iter_source_files(root: Path, globs: list[str]):
    seen: set[Path] = set()
    for glob in globs:
        for path in root.glob(glob):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path


def discover_tests(root: Path, patterns: dict) -> dict:
    """Scan test source and index function names + file paths.

    Returns {"func_names", "paths", "basenames", "stems"} — all sets. `paths`
    are posix-relative to `root`.
    """
    func_names: set[str] = set()
    paths: set[str] = set()
    basenames: set[str] = set()
    stems: set[str] = set()
    func_re = patterns.get("func")
    for path in _iter_source_files(root, patterns.get("globs", [])):
        rel = path.relative_to(root).as_posix()
        paths.add(rel)
        basenames.add(path.name)
        stems.add(path.stem)
        if func_re is None:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in source.splitlines():
            m = func_re.search(line)
            if m:
                func_names.add(m.group(1))
    return {
        "func_names": func_names,
        "paths": paths,
        "basenames": basenames,
        "stems": stems,
    }


# --------------------------------------------------------------------------- #
# Citation parsing + resolution
# --------------------------------------------------------------------------- #
def parse_citation(tests_text: str) -> list[str] | None:
    """Extract candidate identifiers from the text after `**Tests:**`.

    Returns None for the literal `none` exemption; otherwise a list of
    candidate tokens (paths and/or function names).
    """
    s = tests_text.strip()
    if s.lower().strip().rstrip(".") == "none":
        return None
    # Prefer backtick-quoted spans; they carry the real identifier even when
    # wrapped in a markdown link. Fall back to link targets, then to a bare
    # comma/space split of the citation head (before any `— description`).
    backticks = re.findall(r"`([^`]+)`", s)
    if backticks:
        tokens = backticks
    else:
        links = re.findall(r"\]\(([^)]+)\)", s)
        if links:
            tokens = links
        else:
            head = re.split(r"\s+[—–]\s+|\s+--?\s+", s)[0]
            tokens = re.split(r"[,\s]+", head)
    return [t.strip() for t in tokens if t.strip()]


def resolve_token(token: str, discovered: dict) -> bool:
    """True when `token` resolves to a discovered test function or file."""
    tok = token.strip().strip("`").strip().rstrip(",")
    if not tok:
        return True  # parsing noise, nothing to resolve
    # A pytest-style nodeid (`path::func`) resolves if any part resolves.
    for part in re.split(r"::", tok):
        p = part.strip()
        if not p:
            continue
        if p in discovered["func_names"]:
            return True
        pl = p.replace("\\", "/")
        if pl in discovered["paths"]:
            return True
        if any(fp == pl or fp.endswith("/" + pl) for fp in discovered["paths"]):
            return True
        base = pl.rsplit("/", 1)[-1]
        if base in discovered["basenames"]:
            return True
        stem = base.rsplit(".", 1)[0]
        if stem in discovered["stems"]:
            return True
    return False


def find_violations(content: str, file: str = "<memory>") -> list[dict]:
    """Scenarios whose first non-empty following line is not a `> **Tests:**`.

    Line-presence check only (kept for backward compatibility and for the
    commit gate's fast path). Resolution is handled by `analyze`.
    """
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


def analyze(content: str, discovered: dict, file: str = "<memory>") -> dict:
    """Full analysis of one file's scenarios.

    Returns {"presence", "unresolved", "none_count", "total"}:
      - presence: scenarios missing a `> **Tests:**` line (line-presence)
      - unresolved: {file,line,scenario,token} per unresolved non-`none` citation
      - none_count: scenarios citing the literal `none`
      - total: scenarios with a `> **Tests:**` line scanned
    """
    lines = content.splitlines()
    presence: list[dict] = []
    unresolved: list[dict] = []
    none_count = 0
    total = 0
    for i, line in enumerate(lines):
        match = SCENARIO_RE.match(line)
        if not match:
            continue
        scenario = match.group(1).strip() or "(untitled)"
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        tests_match = TESTS_RE.match(lines[j]) if j < len(lines) else None
        if not tests_match:
            presence.append({"file": file, "line": i + 1, "scenario": scenario})
            continue
        total += 1
        remainder = lines[j][tests_match.end():]
        tokens = parse_citation(remainder)
        if tokens is None:
            none_count += 1
            continue
        for tok in tokens:
            if not resolve_token(tok, discovered):
                unresolved.append(
                    {
                        "file": file,
                        "line": j + 1,
                        "scenario": scenario,
                        "token": tok,
                    }
                )
    return {
        "presence": presence,
        "unresolved": unresolved,
        "none_count": none_count,
        "total": total,
    }


def analyze_files(files: list[Path], discovered: dict) -> dict:
    presence: list[dict] = []
    unresolved: list[dict] = []
    none_count = 0
    total = 0
    for file in files:
        result = analyze(file.read_text(encoding="utf-8"), discovered, str(file))
        presence.extend(result["presence"])
        unresolved.extend(result["unresolved"])
        none_count += result["none_count"]
        total += result["total"]
    return {
        "presence": presence,
        "unresolved": unresolved,
        "none_count": none_count,
        "total": total,
    }


def lint_files(files: list[Path]) -> list[dict]:
    """Line-presence violations only (backward-compatible helper)."""
    violations = []
    for file in files:
        violations.extend(find_violations(file.read_text(encoding="utf-8"), str(file)))
    return violations


# --------------------------------------------------------------------------- #
# none-share threshold (enforcement config, separate from the interview answer)
# --------------------------------------------------------------------------- #
def read_none_threshold(root: Path) -> float | None:
    """Optional max share of `none` scenarios, from `.scaffold/gates.json`.

    Accepts `noneShareThreshold` (top level) or `lint_specs.noneShareThreshold`.
    Returns a float in [0, 1], or None when unconfigured/invalid.
    """
    cfg = root / ".scaffold" / "gates.json"
    if not cfg.is_file():
        return None
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("noneShareThreshold")
    if value is None and isinstance(data.get("lint_specs"), dict):
        value = data["lint_specs"].get("noneShareThreshold")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    openspec_root = root / "openspec"
    files = collect_spec_files(openspec_root)

    answer = read_testing_answer(openspec_root)
    patterns, recognized = discovery_patterns(answer)
    if not recognized:
        detail = f"declared Testing: '{answer}'" if answer else "no Testing: answer found"
        print(
            f"⚠ lint:specs: test technology not recognized ({detail}); "
            "falling back to default (pytest) discovery patterns — cited-test "
            "resolution may be incomplete.",
            file=sys.stderr,
        )
    discovered = discover_tests(root, patterns)

    result = analyze_files(files, discovered)
    presence = result["presence"]
    unresolved = result["unresolved"]
    none_count = result["none_count"]
    total = result["total"]

    if presence or unresolved:
        if presence:
            print(
                f"✗ spec traceability: {len(presence)} scenario(s) missing a "
                "'> **Tests:**' line:\n",
                file=sys.stderr,
            )
            for v in presence:
                print(
                    f"  {v['file']}:{v['line']}  Scenario: {v['scenario']}",
                    file=sys.stderr,
                )
        if unresolved:
            print(
                f"\n✗ spec traceability: {len(unresolved)} cited test(s) do not "
                "resolve to a real test in the suite:\n",
                file=sys.stderr,
            )
            for v in unresolved:
                print(
                    f"  {v['file']}:{v['line']}  Scenario: {v['scenario']}  "
                    f"unresolved: {v['token']}",
                    file=sys.stderr,
                )
        print(
            "\nEvery '#### Scenario:' must be followed by a '> **Tests:**' line "
            "citing test(s) that exist in the suite, or '> **Tests:** none' when "
            "untested.",
            file=sys.stderr,
        )
        return 1

    threshold = read_none_threshold(root)
    share = (none_count / total) if total else 0.0
    if threshold is not None and share > threshold:
        print(
            f"✗ spec traceability: {none_count}/{total} scenario(s) cite 'none' "
            f"({share:.0%}), exceeding the configured threshold of "
            f"{threshold:.0%}.",
            file=sys.stderr,
        )
        return 1

    summary = (
        f"✓ spec traceability: {len(files)} spec file(s) scanned, "
        f"every scenario declares its tests; {none_count}/{total} cite 'none'"
    )
    if threshold is not None:
        summary += f" (threshold {threshold:.0%})"
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
