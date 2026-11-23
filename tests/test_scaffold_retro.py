"""Tests for the scaffold-retro spec.

The retro is a markdown skill, so its behaviour is the agent following SKILL.md.
These tests check (a) the file component installs and drifts like any other and
(b) SKILL.md's content contract: read-only boundary, inventory in sync with
scaffold.py, baseline resolution + offline degradation, every candidate
category, exclusions/redaction, and the report template.
"""
from __future__ import annotations

import json
import re

import pytest

import scaffold as s

COMPONENT_ID = "scaffold-retro"
SKILL_DEST = ".claude/skills/scaffold-retro/SKILL.md"
SKILL_TEMPLATE = s.TEMPLATES_DIR / SKILL_DEST


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL_TEMPLATE.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """Body of a markdown section, up to the next heading of the same or higher
    level. Lines inside ``` fences are body text, never headings."""
    level = None
    body: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        m = None if in_fence or line.startswith("```") else re.match(r"^(#+) (.*?)\s*$", line)
        if level is None:
            if m and m.group(2) == heading:
                level = len(m.group(1))
            continue
        if m and len(m.group(1)) <= level:
            break
        body.append(line)
    assert level is not None, f"missing section: {heading}"
    return "\n".join(body)


def _component():
    return next(c for c in s.build_registry() if c.id == COMPONENT_ID)


# --------------------------------------------------------------------------- #
# Inventory parsing + expected (from scaffold.py)
# --------------------------------------------------------------------------- #
def parse_inventory(text: str) -> dict[str, set[str]]:
    m = re.search(r"^```scaffold-inventory\n(.*?)^```", text, re.M | re.S)
    assert m, "missing ```scaffold-inventory fenced block"
    inv: dict[str, set[str]] = {
        "tracked-file": set(), "writer-file": set(), "gate": set(), "hook": set()
    }
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        kind, _, value = line.partition(": ")
        assert kind in inv, f"unknown inventory kind: {kind!r}"
        inv[kind].add(value)
    return inv


def expected_inventory(tmp_path) -> dict[str, set[str]]:
    tracked = {
        dest
        for c in s.build_registry()
        if isinstance(c, s.FileComponent)
        for _src, dest in c.files
    }
    writer = {f"{s.PRECOMMIT_HOOK_DEST} <- {s.PRECOMMIT_HOOK_SRC}"}
    gates = {g["name"] for g in s.BASE_COMMIT_GATES} | {
        g["name"] for lang in s.STATIC_ANALYSIS_GATES.values() for g in lang
    }
    # Hooks: run the real wire_hooks into a scratch project and read them back.
    scratch = tmp_path / "wire"
    scratch.mkdir()
    s.wire_hooks(scratch)
    settings = json.loads((scratch / ".claude" / "settings.json").read_text())
    hooks = {
        f"{event} :: {group.get('matcher', '')} :: {h['command']}"
        for event, groups in settings["hooks"].items()
        for group in groups
        for h in group["hooks"]
    }
    return {"tracked-file": tracked, "writer-file": writer, "gate": gates, "hook": hooks}


def inventory_mismatches(text: str, expected: dict[str, set[str]]) -> list[str]:
    got = parse_inventory(text)
    problems = []
    for kind, want in expected.items():
        for missing in sorted(want - got[kind]):
            problems.append(f"{kind} missing from SKILL.md: {missing}")
        for extra in sorted(got[kind] - want):
            problems.append(f"{kind} in SKILL.md but not in scaffold.py: {extra}")
    return problems


# --------------------------------------------------------------------------- #
# Requirement: Retro skill distributed as a file component
# --------------------------------------------------------------------------- #
def test_install_writes_retro_skill(project_dir):
    comp = _component()
    assert comp.files == [(SKILL_DEST, SKILL_DEST)]
    assert not (project_dir / SKILL_DEST).exists()
    manifest = s.read_manifest(project_dir)
    s.install_file_component(project_dir, comp, manifest, "deadbeef")
    s.write_manifest(project_dir, manifest)

    written = project_dir / SKILL_DEST
    assert written.read_bytes() == SKILL_TEMPLATE.read_bytes()
    entry = s.read_manifest(project_dir)["components"][COMPONENT_ID]
    assert entry["source_sha"] == "deadbeef"
    assert entry["files"] == {SKILL_DEST: s.sha256_file(written)}


def test_retro_skill_modified_detected(project_dir):
    comp = _component()
    manifest = s.read_manifest(project_dir)
    s.install_file_component(project_dir, comp, manifest, "sha1")
    assert s.classify_file_component(project_dir, comp, manifest, "sha1") == s.OK
    (project_dir / SKILL_DEST).write_text("locally edited\n", encoding="utf-8")
    assert s.classify_file_component(project_dir, comp, manifest, "sha1") == s.MODIFIED


def test_retro_installs_without_openspec_root(
    project_dir, fake_claude_home, no_openspec_root, monkeypatch
):
    comp = _component()
    assert comp.needs_openspec is False
    assert comp.needs_git is False
    assert comp.precondition is None
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    status = s.compute_status(project_dir, s.build_registry(), fetch=False)
    assert status.file_statuses[COMPONENT_ID] == s.MISSING


# --------------------------------------------------------------------------- #
# Requirement: Read-only apart from the report
# --------------------------------------------------------------------------- #
def test_skill_declares_read_only_boundary(skill_text):
    front = re.match(r"^---\n(.*?)\n---\n", skill_text, re.S)
    assert front, "missing frontmatter"
    assert re.search(r"^name: scaffold-retro$", front.group(1), re.M)
    desc = front.group(1).lower()
    for trigger in ("retro", "what should go back into common-project-setup",
                    "upstream scaffold improvements"):
        assert trigger in desc

    body = _section(skill_text, "Read-only boundary")
    assert "only allowed write" in body
    assert ".scaffold/retro/retro-<YYYY-MM-DD>.md" in body
    for forbidden in ("issues", "PRs", "push", "scaffold-tracked files",
                      "project files", "common-project-setup"):
        assert forbidden in body, forbidden

    # Unprovisioned project: stop and write nothing.
    pre = _section(skill_text, "Preflight: provisioned project only")
    assert ".scaffold/manifest.json" in pre
    assert "stop" in pre.lower()
    assert "no report" in pre.lower()
    assert "install" in pre


# --------------------------------------------------------------------------- #
# Scaffold-owned inventory stays in sync with scaffold.py (design D2)
# --------------------------------------------------------------------------- #
def test_skill_inventory_matches_scaffold(skill_text, tmp_path):
    problems = inventory_mismatches(skill_text, expected_inventory(tmp_path))
    assert not problems, "\n".join(problems)


def test_inventory_check_catches_removed_entry(skill_text, tmp_path):
    """The sync check fails when any single inventory line is dropped."""
    expected = expected_inventory(tmp_path)
    block = re.search(r"^```scaffold-inventory\n(.*?)^```", skill_text, re.M | re.S)
    lines = [ln for ln in block.group(1).splitlines() if ln.strip()]
    for line in lines:
        mutated = skill_text.replace(line + "\n", "", 1)
        assert inventory_mismatches(mutated, expected), f"removal not caught: {line}"


# --------------------------------------------------------------------------- #
# Requirement: Degraded run when the source is unreachable (design D3)
# --------------------------------------------------------------------------- #
def test_skill_defines_offline_degradation(skill_text):
    body = _section(skill_text, "Baseline resolution")
    order = [
        "SCAFFOLD_SOURCE_URL",
        ".scaffold/source.json",
        "Ask the user for the path to a local `common-project-setup` checkout",
        "https://github.com/deniskrizanovic/common-project-setup",
    ]
    positions = [body.index(marker) for marker in order]
    assert positions == sorted(positions), "baseline resolution out of order"
    assert "outside the project" in body
    assert "--filter=blob:none" in body
    assert "show <source_sha>:templates/<dest>" in body

    offline = _section(skill_text, "Offline degradation")
    assert "by path only" in offline
    assert "Baseline status" in offline
    assert "every other category" in offline


# --------------------------------------------------------------------------- #
# Requirement: Modified scaffold files surfaced as candidates
# --------------------------------------------------------------------------- #
def test_skill_instructs_modified_file_diff(skill_text):
    body = _section(skill_text, "1. Modified scaffold files")
    assert ".scaffold/manifest.json" in body
    assert "shasum -a 256" in body
    assert "pristine template" in body
    assert "diff" in body
    assert "plain language" in body
    for field in ("benefits", "risks or costs", "recommendation"):
        assert field in body, field


# --------------------------------------------------------------------------- #
# Requirements: Local additions + Recurring patterns surfaced as candidates
# --------------------------------------------------------------------------- #
CATEGORIES = [
    "Modified scaffold files",
    "Local gates",
    "Local hooks and scripts",
    "Wishlist overrides",
    "Config rules",
    "Recurring patterns",
]


def test_skill_covers_all_candidate_categories(skill_text):
    checklist = _section(skill_text, "Checklist")
    positions = [checklist.index(f"### {i}. {c}") for i, c in enumerate(CATEGORIES, 1)]
    assert positions == sorted(positions), "checklist categories out of order"

    assert ".scaffold/gates.json" in _section(skill_text, "2. Local gates")
    hooks = _section(skill_text, "3. Local hooks and scripts")
    assert ".claude/settings.json" in hooks and "scripts/" in hooks
    wish = _section(skill_text, "4. Wishlist overrides")
    assert ".scaffold/plugins.json" in wish and ".scaffold/skills.yaml" in wish
    assert "rules:" in _section(skill_text, "5. Config rules")
    patterns = _section(skill_text, "6. Recurring patterns")
    assert "CLAUDE.md" in patterns
    assert "openspec/changes/archive" in patterns
    assert "Skip the OpenSpec archive" in patterns and "`openspec/` is absent" in patterns

    # Every category has its own section in the report template.
    template = _section(skill_text, "Report template")
    for c in CATEGORIES:
        assert f"## {c}" in template, c


# --------------------------------------------------------------------------- #
# Requirement: Project-specific content and secrets excluded (design D5)
# --------------------------------------------------------------------------- #
def test_skill_excludes_project_specific_and_secrets(skill_text):
    excl = _section(skill_text, "Exclusions")
    assert "`context:` block" in excl
    assert "Never" in excl
    assert "domain code" in excl

    secrets = _section(skill_text, "Secrets")
    assert "<redacted>" in secrets
    for pattern in ("*_TOKEN=", "*_KEY=", "API keys", "credentials"):
        assert pattern in secrets, pattern
    # Worked hook example shows the redaction.
    assert "Bearer <redacted>" in secrets


# --------------------------------------------------------------------------- #
# Requirement: Candidate report structure
# --------------------------------------------------------------------------- #
def test_skill_defines_report_contract(skill_text):
    template = _section(skill_text, "Report template")
    assert ".scaffold/retro/retro-<YYYY-MM-DD>.md" in template
    sections = ["## Summary", "## Baseline status", "## Modified scaffold files",
                "## Categories checked with none found"]
    positions = [template.index(h) for h in sections]
    assert positions == sorted(positions), "report sections out of order"

    fields = _section(skill_text, "Candidate fields")
    for field in ("**Category:**", "**Evidence:**", "**Change summary:**",
                  "**Benefits:**", "**Risks/costs:**", "**Recommendation:**",
                  "**Upstream target:**", "**Suggested change name:**"):
        assert field in fields, field
    assert "`promote` | `adapt` | `keep-local`" in fields
    assert "kebab-case" in fields
    assert re.search(r"Omit \*\*Suggested change name\*\* when the recommendation "
                     r"is `keep-local`", fields)

    empty = _section(skill_text, "No-candidates form")
    assert "No candidates found." in empty
    assert "## Categories checked with none found" in empty
    for c in CATEGORIES:
        assert f"- {c}: none found" in empty, c
