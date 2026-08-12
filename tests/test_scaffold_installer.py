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
    # Skip config-baseline, config-interview, schema-clone, enforcement-hooks,
    # cost-tracker; then for the modified lint-gates: diff, then skip. Everything
    # after (plugins, skills) defaults to skip, robust to registry growth.
    answers = iter(["s", "s", "s", "s", "s", "d"])
    reader = lambda _prompt: next(answers, "s")
    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=reader, out=out)
    assert "--- a/scripts/lint_specs.py" in out.getvalue()


# --------------------------------------------------------------------------- #
# config-interview
# --------------------------------------------------------------------------- #
def _write_template_config(project_dir):
    """Copy the shipped template config (with its placeholder) into the project."""
    cfg = project_dir / "openspec" / "config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    src = s.TEMPLATES_DIR / "openspec" / "config.yaml"
    cfg.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return cfg


def test_interview_fills_block_and_clears_sentinel(project_dir):
    """Scripted answers fill the context block; the sentinel is gone (2.3)."""
    cfg = _write_template_config(project_dir)
    assert s.CONFIG_CONTEXT_SENTINEL in cfg.read_text(encoding="utf-8")
    answers = iter(["A billing service", "Python 3.12", "FastAPI", "Postgres", "pytest"])
    reader = lambda _prompt: next(answers)
    out = io.StringIO()
    s._config_interview_filler(project_dir, reader=reader, out=out)
    text = cfg.read_text(encoding="utf-8")
    assert s.CONFIG_CONTEXT_SENTINEL not in text
    assert "Purpose: A billing service" in text
    assert "Language / runtime: Python 3.12" in text
    assert "Frameworks / libraries: FastAPI" in text
    assert "Data store: Postgres" in text
    assert "Testing: pytest" in text


def test_interview_preserves_rules_schema_comments(project_dir):
    """rules:, schema:, and comments survive the rewrite (2.5)."""
    cfg = _write_template_config(project_dir)
    answers = iter(["p", "l", "f", "d", "t"])
    reader = lambda _prompt: next(answers)
    s._config_interview_filler(project_dir, reader=reader, out=io.StringIO())
    text = cfg.read_text(encoding="utf-8")
    assert text.startswith("schema: spec-driven")
    assert "# Per-artifact rules." in text
    assert "rules:" in text
    assert "specs:" in text
    # The `> **Tests:**` traceability rule text is part of the rules: block.
    assert "traceability gate" in text


def test_interview_missing_config_is_noop(project_dir):
    """No config on disk -> filler prints and writes nothing."""
    out = io.StringIO()
    s._config_interview_filler(project_dir, reader=lambda _p: "x", out=out)
    assert "not found" in out.getvalue()
    assert not (project_dir / "openspec" / "config.yaml").exists()


def test_interview_drift_missing_then_ok(project_dir, fake_claude_home, monkeypatch):
    """Placeholder -> MISSING; customized -> OK (3.4)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _write_template_config(project_dir)
    registry = s.build_registry()
    comp = next(c for c in registry if c.id == "config-interview")
    manifest = s.read_manifest(project_dir)
    assert s.classify_file_component(project_dir, comp, manifest, None) == s.MISSING
    answers = iter(["p", "l", "f", "d", "t"])
    s._config_interview_filler(project_dir, reader=lambda _p: next(answers), out=io.StringIO())
    assert s.classify_file_component(project_dir, comp, manifest, None) == s.OK


def test_install_offers_interview_on_ok_component(project_dir, fake_claude_home, monkeypatch):
    """Even customized (OK), install re-offers the interview (3.4)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _write_template_config(project_dir)
    # First fill so config-interview classifies OK.
    seed = iter(["orig", "l", "f", "d", "t"])
    s._config_interview_filler(project_dir, reader=lambda _p: next(seed), out=io.StringIO())
    cfg = project_dir / "openspec" / "config.yaml"
    assert s._context_is_customized(project_dir)

    # Re-run install: interview the OK component and change the purpose.
    # Reader yields answers when prompted with "  <label>: " and menu choices
    # otherwise; config-interview is offered despite being OK ("customized").
    field_answers = iter(["revised purpose", "l2", "f2", "d2", "t2"])

    def reader(prompt):
        if prompt.strip().startswith("Purpose") or prompt.strip().rstrip(":") in (
            "Language / runtime", "Frameworks / libraries", "Data store", "Testing",
        ):
            return next(field_answers)
        if "[i]nterview, [s]kip" in prompt:
            return "i"
        if "overwrite?" in prompt:  # confirm re-interview over a customized block
            return "y"
        return "s"

    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=reader, out=out)
    assert "config-interview — customized" in out.getvalue()
    assert "Purpose: revised purpose" in cfg.read_text(encoding="utf-8")


def test_interview_blank_purpose_aborts(project_dir):
    """Blank Purpose must not write; sentinel survives so status stays MISSING."""
    cfg = _write_template_config(project_dir)
    before = cfg.read_text(encoding="utf-8")
    out = io.StringIO()
    # All fields blank (as pressing Enter through the prompts would yield).
    s._config_interview_filler(project_dir, reader=lambda _p: "", out=out)
    assert "Purpose is required" in out.getvalue()
    assert cfg.read_text(encoding="utf-8") == before
    assert s.CONFIG_CONTEXT_SENTINEL in cfg.read_text(encoding="utf-8")
    assert not s._context_is_customized(project_dir)


def test_interview_reinterview_confirms_before_overwrite(project_dir):
    """A customized block is preserved when the overwrite confirm is declined."""
    _write_template_config(project_dir)
    cfg = project_dir / "openspec" / "config.yaml"
    seed = iter(["orig purpose", "l", "f", "d", "t"])
    s._config_interview_filler(project_dir, reader=lambda _p: next(seed), out=io.StringIO())
    filled = cfg.read_text(encoding="utf-8")

    # Decline the overwrite: block is untouched, field prompts never reached.
    def reader(prompt):
        if "overwrite?" in prompt:
            return "n"
        raise AssertionError(f"unexpected prompt after decline: {prompt!r}")

    out = io.StringIO()
    s._config_interview_filler(project_dir, reader=reader, out=out)
    assert "left unchanged" in out.getvalue()
    assert cfg.read_text(encoding="utf-8") == filled


def test_context_customized_ignores_sentinel_outside_block(project_dir):
    """The sentinel quoted in rules:/comments doesn't mask a real fill (block-scoped)."""
    _write_template_config(project_dir)
    cfg = project_dir / "openspec" / "config.yaml"
    seed = iter(["real purpose", "l", "f", "d", "t"])
    s._config_interview_filler(project_dir, reader=lambda _p: next(seed), out=io.StringIO())
    # Append a comment quoting the placeholder phrase *outside* the context block.
    text = cfg.read_text(encoding="utf-8")
    cfg.write_text(text + f"\n# note: do not {s.CONFIG_CONTEXT_SENTINEL}\n", encoding="utf-8")
    assert s.CONFIG_CONTEXT_SENTINEL in cfg.read_text(encoding="utf-8")
    assert s._context_is_customized(project_dir)  # still customized: block is clean


def test_render_context_body_flattens_multiline_answer():
    """Embedded newlines collapse to a space so the block scalar stays valid YAML."""
    body = s._render_context_body({"purpose": "line one\nline two", "language": "py"})
    assert "Purpose: line one line two" in body
    assert all("\n" not in line for line in body)


def test_update_filler_component_reports_install_only(project_dir):
    """`update config-interview` is not 'Unknown component' — it's install-only."""
    out = io.StringIO()
    rc = s.cmd_update(project_dir, s.build_registry(), component="config-interview", out=out)
    assert rc == 0
    msg = out.getvalue()
    assert "install-only" in msg
    assert "Unknown component" not in msg


def test_update_truly_unknown_component_still_errors(project_dir):
    """A genuinely unknown id still reports Unknown component with rc=1."""
    out = io.StringIO()
    rc = s.cmd_update(project_dir, s.build_registry(), component="nope-nope", out=out)
    assert rc == 1
    assert "Unknown component: nope-nope" in out.getvalue()
