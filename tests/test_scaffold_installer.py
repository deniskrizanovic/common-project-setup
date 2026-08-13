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


def test_install_diff_option(project_dir, fake_claude_home, openspec_root, monkeypatch):
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


def test_install_offers_interview_on_ok_component(project_dir, fake_claude_home, openspec_root, monkeypatch):
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
    """Blank fields must not write; sentinel survives so status stays MISSING."""
    cfg = _write_template_config(project_dir)
    before = cfg.read_text(encoding="utf-8")
    out = io.StringIO()
    # All fields blank (as pressing Enter through the prompts would yield).
    s._config_interview_filler(project_dir, reader=lambda _p: "", out=out)
    assert "every field is required" in out.getvalue()
    assert cfg.read_text(encoding="utf-8") == before
    assert s.CONFIG_CONTEXT_SENTINEL in cfg.read_text(encoding="utf-8")
    assert not s._context_is_customized(project_dir)


def test_interview_blank_non_purpose_field_aborts(project_dir):
    """A blank in any field (not just Purpose) aborts without writing."""
    cfg = _write_template_config(project_dir)
    before = cfg.read_text(encoding="utf-8")
    out = io.StringIO()
    # Purpose filled, Data store left blank.
    answers = iter(["A billing service", "Python", "FastAPI", "", "pytest"])
    s._config_interview_filler(project_dir, reader=lambda _p: next(answers), out=out)
    assert "every field is required" in out.getvalue()
    assert "Data store" in out.getvalue()
    assert cfg.read_text(encoding="utf-8") == before
    assert s.CONFIG_CONTEXT_SENTINEL in cfg.read_text(encoding="utf-8")
    assert not s._context_is_customized(project_dir)


def test_context_absent_block_is_missing_not_ok(project_dir, fake_claude_home, monkeypatch):
    """A config with no context block classifies MISSING, not a false OK (review #1).

    Whole-file sentinel scan would report OK (sentinel absent everywhere), but the
    interview can't rewrite an absent block, so status must under-claim MISSING.
    """
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    cfg = project_dir / "openspec" / "config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("schema: spec-driven\nrules:\n  specs: []\n", encoding="utf-8")
    assert s.CONFIG_CONTEXT_SENTINEL not in cfg.read_text(encoding="utf-8")
    assert not s._context_is_customized(project_dir)
    registry = s.build_registry()
    comp = next(c for c in registry if c.id == "config-interview")
    manifest = s.read_manifest(project_dir)
    assert s.classify_file_component(project_dir, comp, manifest, None) == s.MISSING


def test_locate_context_block_accepts_scalar_indicators(project_dir):
    """`|-`, `|+`, `|2`, and a trailing comment on the key are all locatable (review #3)."""
    for key in ("context: |", "context: |-", "context: |+", "context: |2", "context: |  # notes"):
        text = f"schema: spec-driven\n{key}\n  Purpose: {s.CONFIG_CONTEXT_SENTINEL}\nrules:\n  specs: []\n"
        located = s._locate_context_block(text)
        assert located is not None, f"failed to locate for key {key!r}"
        _, start, end, _ = located
        assert (end - start) == 2  # key line + one body line


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


def test_compute_status_reads_config_once(project_dir, fake_claude_home, monkeypatch):
    """compute_status reads config.yaml once, shared by both config predicates (review #6)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    _write_template_config(project_dir)
    calls = {"n": 0}
    real = s._config_yaml_text

    def counting(project_root):
        calls["n"] += 1
        return real(project_root)

    monkeypatch.setattr(s, "_config_yaml_text", counting)
    s.compute_status(project_dir, s.build_registry(), fetch=False)
    assert calls["n"] == 1


def test_update_truly_unknown_component_still_errors(project_dir):
    """A genuinely unknown id still reports Unknown component with rc=1."""
    out = io.StringIO()
    rc = s.cmd_update(project_dir, s.build_registry(), component="nope-nope", out=out)
    assert rc == 1
    assert "Unknown component: nope-nope" in out.getvalue()


# --------------------------------------------------------------------------- #
# OpenSpec-root precondition (BLOCKED)
# --------------------------------------------------------------------------- #
OPENSPEC_COMPONENTS = ("config-baseline", "config-interview", "schema-clone")


def test_openspec_initialized_true_when_changes_dir_exists(project_dir):
    """`openspec/changes/` present (real `openspec init`) → True (4.1)."""
    (project_dir / "openspec" / "changes").mkdir(parents=True)
    assert s.openspec_initialized(project_dir) is True


def test_openspec_initialized_false_on_empty_project(project_dir):
    """No `openspec/` at all → False (4.1)."""
    assert s.openspec_initialized(project_dir) is False


def test_openspec_initialized_false_on_config_only(project_dir):
    """`openspec/config.yaml` but no `changes/` (partial scaffold run) → False.

    The scaffold's own config-baseline writes config.yaml; that must NOT
    self-satisfy the gate. Only a real init's `changes/` dir counts.
    """
    (project_dir / "openspec").mkdir()
    (project_dir / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
    assert s.openspec_initialized(project_dir) is False


def test_openspec_initialized_ignores_cli_and_ancestor(project_dir, monkeypatch):
    """Disk-based: never shells out, and an initialized ANCESTOR does not leak.

    Guards the version-skew bug where `openspec list --json` (v1.8.x) reports
    the cwd as root for any directory. The probe must read disk, not the CLI.
    """
    def boom(*a, **k):
        raise AssertionError("openspec_initialized must not shell out")

    monkeypatch.setattr(s.subprocess, "run", boom)
    # An initialized parent must not make an uninitialized child pass.
    (project_dir.parent / "openspec" / "changes").mkdir(parents=True, exist_ok=True)
    assert s.openspec_initialized(project_dir) is False


def test_install_blocks_openspec_components_without_root(
    project_dir, fake_claude_home, no_openspec_root, monkeypatch
):
    """No root → the three components are BLOCKED, nothing written under openspec/,
    and the init remedy is printed (4.2)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    reader = lambda _prompt: "s"
    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=reader, out=out)
    text = out.getvalue()
    for cid in OPENSPEC_COMPONENTS:
        assert f"{cid} — BLOCKED" in text
    assert "openspec init . --tools claude" in text
    # No openspec/ tree fabricated for the blocked components.
    assert not (project_dir / "openspec").exists()
    # Manifest records none of the blocked components.
    manifest = s.read_manifest(project_dir)
    for cid in OPENSPEC_COMPONENTS:
        assert cid not in manifest["components"]


def test_install_installs_independent_components_without_root(
    project_dir, fake_claude_home, no_openspec_root, monkeypatch
):
    """OpenSpec-independent components still install with no root (4.3).

    With no root the OpenSpec-dependent components are BLOCKED, but
    enforcement-hooks / cost-tracker / lint-gates are unaffected and classify
    normally (MISSING here) — install writes them on a plain `i`.
    """
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: "sha1")
    # Keep the run hermetic: no real plugin/skill CLI shell-outs.
    monkeypatch.setattr(s, "install_plugin", lambda plugin: True)
    monkeypatch.setattr(s, "install_skill", lambda skill_id, project_root: True)
    status = s.compute_status(project_dir, s.build_registry(), fetch=False)
    for cid in ("enforcement-hooks", "cost-tracker", "lint-gates"):
        assert status.file_statuses[cid] == s.MISSING

    # Install every offered file component; blocked ones self-skip (no prompt),
    # so a constant "i" installs the independent ones.
    out = io.StringIO()
    s.cmd_install(project_dir, s.build_registry(), reader=lambda _p: "i", out=out)
    assert (project_dir / "scripts" / "lint_specs.py").is_file()
    assert (project_dir / "scripts" / "branch_guard.py").is_file()
    assert (project_dir / "tokencost" / "cost-tracker.py").is_file()
    # The blocked components wrote nothing.
    assert not (project_dir / "openspec").exists()


def test_check_reports_blocked_read_only(
    project_dir, fake_claude_home, no_openspec_root, monkeypatch
):
    """`check` reports BLOCKED without writing (4.4)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    before = sorted(p.name for p in project_dir.iterdir())
    out = io.StringIO()
    s.cmd_check(project_dir, s.build_registry(), out=out)
    after = sorted(p.name for p in project_dir.iterdir())
    assert before == after
    assert not s.manifest_path(project_dir).exists()
    text = out.getvalue()
    for cid in OPENSPEC_COMPONENTS:
        assert f"{s.BLOCKED:<14} {cid}" in text


def test_list_reports_blocked_without_prompting(
    project_dir, fake_claude_home, no_openspec_root, monkeypatch
):
    """`list` prints BLOCKED and never prompts (4.4)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)

    def boom(*a, **k):
        raise AssertionError("list must not prompt")

    monkeypatch.setattr("builtins.input", boom)
    out = io.StringIO()
    assert s.cmd_list(project_dir, s.build_registry(), out=out) == 0
    text = out.getvalue()
    for cid in OPENSPEC_COMPONENTS:
        assert f"[{s.BLOCKED:<14}] {cid}" in text


def test_present_root_follows_normal_flow(
    project_dir, fake_claude_home, openspec_root, monkeypatch
):
    """With a present root the three components follow MISSING/OK/MODIFIED (4.5)."""
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: "sha1")
    status = s.compute_status(project_dir, s.build_registry())
    # Nothing installed yet → MISSING, not BLOCKED.
    for cid in OPENSPEC_COMPONENTS:
        assert status.file_statuses[cid] == s.MISSING
    # Install schema-clone, then it reads OK.
    _install(project_dir, "schema-clone", "sha1")
    status = s.compute_status(project_dir, s.build_registry())
    assert status.file_statuses["schema-clone"] == s.OK
    # Tamper → MODIFIED.
    (project_dir / "openspec" / "schemas" / "spec-driven" / "schema.yaml").write_text(
        "tampered", encoding="utf-8"
    )
    status = s.compute_status(project_dir, s.build_registry())
    assert status.file_statuses["schema-clone"] == s.MODIFIED
