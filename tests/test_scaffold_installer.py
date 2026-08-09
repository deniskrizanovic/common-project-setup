"""Tests for the scaffold-installer spec.

Covers each drift classification, `check` writing nothing, `list` prompting
nothing, MODIFIED update refused without --force, present component skipped.
"""
from __future__ import annotations

import io

import pytest

import scaffold as s


def _install(project_dir, comp_id, source_sha="abc123"):
    registry = s.build_registry()
    comp = next(c for c in registry if c.id == comp_id)
    manifest = s.read_manifest(project_dir)
    s.install_file_component(project_dir, comp, manifest, source_sha)
    s.write_manifest(project_dir, manifest)
    return comp


def test_missing_when_no_manifest(project_dir):
    """GIVEN a component never installed THEN it classifies MISSING."""
    registry = s.build_registry()
    comp = next(c for c in registry if c.id == "lint-gates")
    manifest = s.read_manifest(project_dir)
    assert s.classify_file_component(project_dir, comp, manifest, "sha") == s.MISSING


def test_ok_after_install(project_dir):
    comp = _install(project_dir, "lint-gates", "sha1")
    manifest = s.read_manifest(project_dir)
    assert s.classify_file_component(project_dir, comp, manifest, "sha1") == s.OK


def test_stale_when_source_advanced(project_dir):
    comp = _install(project_dir, "lint-gates", "sha_old")
    manifest = s.read_manifest(project_dir)
    assert s.classify_file_component(project_dir, comp, manifest, "sha_new") == s.STALE


def test_modified_when_disk_edited(project_dir):
    comp = _install(project_dir, "lint-gates", "sha1")
    (project_dir / "scripts" / "lint_specs.py").write_text("tampered", encoding="utf-8")
    manifest = s.read_manifest(project_dir)
    assert s.classify_file_component(project_dir, comp, manifest, "sha1") == s.MODIFIED


def test_modified_stale_when_both(project_dir):
    comp = _install(project_dir, "lint-gates", "sha_old")
    (project_dir / "scripts" / "lint_specs.py").write_text("tampered", encoding="utf-8")
    manifest = s.read_manifest(project_dir)
    assert (
        s.classify_file_component(project_dir, comp, manifest, "sha_new")
        == s.MODIFIED_STALE
    )


def test_check_writes_nothing(project_dir, fake_claude_home, monkeypatch):
    """`check` must not create or mutate the manifest or any files."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    before = sorted(p.name for p in project_dir.iterdir())
    out = io.StringIO()
    s.cmd_check(project_dir, s.build_registry(), out=out)
    after = sorted(p.name for p in project_dir.iterdir())
    assert before == after
    assert not s.manifest_path(project_dir).exists()


def test_list_no_prompts(project_dir, fake_claude_home, monkeypatch):
    """`list` must not call input()."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)

    def boom(*a, **k):
        raise AssertionError("list must not prompt")

    monkeypatch.setattr("builtins.input", boom)
    out = io.StringIO()
    assert s.cmd_list(project_dir, s.build_registry(), out=out) == 0
    assert "lint-gates" in out.getvalue()


def test_update_modified_refused_without_force(project_dir, fake_claude_home, monkeypatch):
    _install(project_dir, "lint-gates", "sha_old")
    edited = project_dir / "scripts" / "lint_specs.py"
    edited.write_text("tampered", encoding="utf-8")
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: "sha_new")
    out = io.StringIO()
    s.cmd_update(project_dir, s.build_registry(), "lint-gates", force=False, out=out)
    assert edited.read_text(encoding="utf-8") == "tampered"
    assert "refusing to overwrite" in out.getvalue()


def test_update_modified_overwrites_with_force(project_dir, fake_claude_home, monkeypatch):
    _install(project_dir, "lint-gates", "sha_old")
    edited = project_dir / "scripts" / "lint_specs.py"
    edited.write_text("tampered", encoding="utf-8")
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: "sha_new")
    out = io.StringIO()
    s.cmd_update(project_dir, s.build_registry(), "lint-gates", force=True, out=out)
    assert "tampered" not in edited.read_text(encoding="utf-8")
    assert "updated" in out.getvalue()


def test_install_skips_present_component(project_dir, fake_claude_home, monkeypatch):
    """An OK component during install is reported current and not rewritten."""
    _install(project_dir, "lint-gates", "sha1")
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: "sha1")
    target = project_dir / "scripts" / "lint_specs.py"
    mtime_before = target.stat().st_mtime_ns

    # Reader that would fail if prompted for the OK component; only plugins/others prompt "s".
    answers = iter(["s"] * 20)
    reader = lambda _prompt: next(answers)
    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=reader, out=out)
    assert "lint-gates — OK" in out.getvalue()
    assert target.stat().st_mtime_ns == mtime_before


def test_install_diff_option(project_dir, fake_claude_home, monkeypatch):
    """The diff option shows a unified diff before any write."""
    _install(project_dir, "lint-gates", "sha_old")
    (project_dir / "scripts" / "lint_specs.py").write_text("local edit\n", encoding="utf-8")
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: "sha_new")
    # Skip config-baseline, schema-clone, enforcement-hooks, cost-tracker;
    # then for the modified lint-gates: diff, then skip. Plugins: skip.
    answers = iter(["s", "s", "s", "s", "d", "s", "s", "s"])
    reader = lambda _prompt: next(answers)
    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=reader, out=out)
    assert "--- a/scripts/lint_specs.py" in out.getvalue()
