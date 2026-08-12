"""Tests for the skill-management spec.

Classification (MISSING/STALE/EXTRA/OK, EXTRA never removed); CLI-absent
fallback prints commands and does not fail; per-item prompt (one per non-OK
skill, OK skipped); per-project override composition.
"""
from __future__ import annotations

import io
import json

import scaffold as s

BASE_MANIFEST_TEXT = """\
plugins: []
skills:
  - mattpocock/skills:grill-me
  - deniskrizanovic/dk-skills:diff-org-changes
"""


def _patch_base_manifest(tmp_path, monkeypatch, text=BASE_MANIFEST_TEXT):
    m = tmp_path / "manifest.yaml"
    m.write_text(text, encoding="utf-8")
    monkeypatch.setattr(s, "BASE_MANIFEST", m)


def _patch_no_plugins(tmp_path, monkeypatch):
    """Empty the plugin wishlist so only skills use the two-option prompt."""
    empty = tmp_path / "plugins.json"
    empty.write_text(json.dumps({"plugins": []}), encoding="utf-8")
    monkeypatch.setattr(s, "BASE_PLUGINS", empty)


def _write_lock(project_dir, skills):
    (project_dir / "skills-lock.json").write_text(
        json.dumps({"version": 1, "skills": skills}), encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# 4.3 Classification
# --------------------------------------------------------------------------- #
def test_classify_missing():
    desired = ["mattpocock/skills:grill-me"]
    result = s.classify_skills(desired, {"skills": {}})
    assert result["grill-me"] == s.MISSING


def test_classify_ok():
    desired = ["mattpocock/skills:grill-me"]
    lock = {"skills": {"grill-me": {"source": "mattpocock/skills"}}}
    assert s.classify_skills(desired, lock)["grill-me"] == s.OK


def test_classify_stale():
    desired = ["mattpocock/skills:grill-me"]
    lock = {"skills": {"grill-me": {"source": "mattpocock/skills"}}}
    result = s.classify_skills(desired, lock, stale={"grill-me"})
    assert result["grill-me"] == s.STALE


def test_classify_extra_never_removed(project_dir):
    desired = ["mattpocock/skills:grill-me"]
    lock = {"skills": {
        "grill-me": {"source": "mattpocock/skills"},
        "some-other": {"source": "x/y"},
    }}
    _write_lock(project_dir, lock["skills"])
    result = s.classify_skills(desired, lock)
    assert result["some-other"] == s.EXTRA
    # pure classification: the lock file on disk is untouched
    reread = s.read_skills_lock(project_dir)
    assert "some-other" in reread["skills"]


# --------------------------------------------------------------------------- #
# 4.5 CLI-absent fallback
# --------------------------------------------------------------------------- #
def test_install_skill_cli_absent_returns_false(no_claude_cli):
    """Empty PATH -> npx unavailable -> install_skill returns False, no raise."""
    assert s.install_skill("mattpocock/skills:grill-me", no_claude_cli) is False


def test_skill_install_commands():
    cmds = s.skill_install_commands("mattpocock/skills:grill-me")
    assert cmds == [
        "npx --yes skills@latest add mattpocock/skills --skill grill-me --yes"
    ]
    # The printed command is exactly the argv install_skill executes.
    assert cmds[0] == " ".join(s.skills_add_argv("mattpocock/skills:grill-me"))


def test_cli_absent_run_prints_commands_and_does_not_fail(
    project_dir, fake_claude_home, no_claude_cli, tmp_path, monkeypatch
):
    _patch_base_manifest(tmp_path, monkeypatch)
    _patch_no_plugins(tmp_path, monkeypatch)
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    registry = s.build_registry()
    answers = iter(["i"] * 50)  # accept everything offered (incl. interview fields)
    out = io.StringIO()
    rc = s.cmd_install(project_dir, registry, reader=lambda p: next(answers), out=out)
    text = out.getvalue()
    assert rc == 0
    assert "npx skills CLI not found" in text
    assert "npx --yes skills@latest add mattpocock/skills --skill grill-me --yes" in text


# --------------------------------------------------------------------------- #
# 4.7 Per-item prompt
# --------------------------------------------------------------------------- #
def test_one_prompt_per_non_ok_skill(
    project_dir, fake_claude_home, no_claude_cli, tmp_path, monkeypatch
):
    """grill-me OK (in lock) is skipped without prompt; diff-org-changes MISSING prompts."""
    _patch_base_manifest(tmp_path, monkeypatch)
    _patch_no_plugins(tmp_path, monkeypatch)
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    monkeypatch.setattr(s, "skill_stale_names", lambda desired, lock: set())
    _write_lock(project_dir, {"grill-me": {"source": "mattpocock/skills"}})

    registry = s.build_registry()
    prompts = []

    def reader(p):
        prompts.append(p)
        return "s"  # skip

    out = io.StringIO()
    s.cmd_install(project_dir, registry, reader=reader, out=out)
    text = out.getvalue()

    # grill-me is OK -> no prompt, reported current
    assert "grill-me — OK" in text
    # Skill/plugin prompts use the two-option form (no [d]iff); file components
    # use the three-option form. With plugins: [] only skills prompt this way,
    # and grill-me (OK) is skipped -> exactly one prompt (diff-org-changes MISSING).
    two_option = "  [i]nstall/update, [s]kip? "
    assert prompts.count(two_option) == 1


def test_no_batch_install_option(
    project_dir, fake_claude_home, no_claude_cli, tmp_path, monkeypatch
):
    """The prompt offers only [i]/[s], never a batch/all option."""
    _patch_base_manifest(tmp_path, monkeypatch)
    _patch_no_plugins(tmp_path, monkeypatch)
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    monkeypatch.setattr(s, "skill_stale_names", lambda desired, lock: set())
    registry = s.build_registry()
    seen = []

    def reader(p):
        seen.append(p)
        return "s"

    s.cmd_install(project_dir, registry, reader=reader, out=io.StringIO())
    # Skill/plugin prompts are exactly the per-item two-option form; no batch.
    skill_prompts = [p for p in seen if p == "  [i]nstall/update, [s]kip? "]
    file_prompts = [p for p in seen if p == "  [i]nstall/update, [d]iff, [s]kip? "]
    interview_prompts = [p for p in seen if p == "  [i]nterview, [s]kip? "]
    assert skill_prompts  # skills did prompt
    # every prompt is one of the known per-item forms; none offer a batch/all
    known = {
        *([skill_prompts[0]] if skill_prompts else []),
        *([file_prompts[0]] if file_prompts else []),
        *([interview_prompts[0]] if interview_prompts else []),
    }
    assert set(seen) <= known
    for p in seen:
        assert "batch" not in p.lower()


# --------------------------------------------------------------------------- #
# 4.9 Per-project override composition
# --------------------------------------------------------------------------- #
def test_base_skill_wishlist_applies(tmp_path, monkeypatch, project_dir):
    _patch_base_manifest(tmp_path, monkeypatch)
    desired = s.compose_skill_wishlist(project_dir)
    names = {s.skill_name_from_id(d) for d in desired}
    assert names == {"grill-me", "diff-org-changes"}


def test_override_extends_wishlist(tmp_path, monkeypatch, project_dir):
    _patch_base_manifest(tmp_path, monkeypatch)
    (project_dir / ".scaffold").mkdir()
    (project_dir / ".scaffold" / "skills.yaml").write_text(
        "skills:\n  - acme/extra:new-skill\n", encoding="utf-8"
    )
    desired = s.compose_skill_wishlist(project_dir)
    names = {s.skill_name_from_id(d) for d in desired}
    assert names == {"grill-me", "diff-org-changes", "new-skill"}


def test_override_replaces_same_name(tmp_path, monkeypatch, project_dir):
    _patch_base_manifest(tmp_path, monkeypatch)
    (project_dir / ".scaffold").mkdir()
    (project_dir / ".scaffold" / "skills.yaml").write_text(
        "skills:\n  - myfork/skills:grill-me\n", encoding="utf-8"
    )
    by_name = {s.skill_name_from_id(d): d for d in s.compose_skill_wishlist(project_dir)}
    assert by_name["grill-me"] == "myfork/skills:grill-me"


# --------------------------------------------------------------------------- #
# Skill name-collision guard
# --------------------------------------------------------------------------- #
def test_manifest_rejects_colliding_skill_names(tmp_path):
    """Two distinct ids reducing to the same lock key must be rejected."""
    import pytest

    m = tmp_path / "manifest.yaml"
    m.write_text(
        "plugins: []\n"
        "skills:\n"
        "  - ownerA/repo1:foo\n"
        "  - ownerB/repo2:foo\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        s.read_manifest_file(m)
    assert "foo" in str(exc.value)


def test_manifest_allows_duplicate_identical_ids(tmp_path):
    """The same id twice is a harmless duplicate, not a collision."""
    m = tmp_path / "manifest.yaml"
    m.write_text(
        "plugins: []\n"
        "skills:\n"
        "  - ownerA/repo1:foo\n"
        "  - ownerA/repo1:foo\n",
        encoding="utf-8",
    )
    assert s.read_manifest_file(m)["skills"] == [
        "ownerA/repo1:foo",
        "ownerA/repo1:foo",
    ]


# --------------------------------------------------------------------------- #
# Staleness by upstream-hash comparison (CLI has no non-mutating check command)
# --------------------------------------------------------------------------- #
def _fake_resolver(hashes):
    def resolve(skill_id):
        name = s.skill_name_from_id(skill_id)
        if name not in hashes:
            raise RuntimeError(f"unresolvable: {skill_id}")
        return {"computedHash": hashes[name]}
    return resolve


def test_stale_when_upstream_hash_differs(no_claude_cli, monkeypatch):
    # Force CLI-available so the function does not early-return.
    monkeypatch.setattr(s, "skills_cli_available", lambda: True)
    desired = ["mattpocock/skills:grill-me"]
    lock = {"skills": {"grill-me": {"computedHash": "old"}}}
    stale = s.skill_stale_names(
        desired, lock, resolver=_fake_resolver({"grill-me": "new"})
    )
    assert stale == {"grill-me"}


def test_not_stale_when_hash_matches(monkeypatch):
    monkeypatch.setattr(s, "skills_cli_available", lambda: True)
    desired = ["mattpocock/skills:grill-me"]
    lock = {"skills": {"grill-me": {"computedHash": "same"}}}
    stale = s.skill_stale_names(
        desired, lock, resolver=_fake_resolver({"grill-me": "same"})
    )
    assert stale == set()


def test_missing_skill_not_stale(monkeypatch):
    """A desired skill absent from the lock is MISSING, never STALE."""
    monkeypatch.setattr(s, "skills_cli_available", lambda: True)
    desired = ["mattpocock/skills:grill-me"]
    stale = s.skill_stale_names(
        desired, {"skills": {}}, resolver=_fake_resolver({"grill-me": "x"})
    )
    assert stale == set()


def test_unresolvable_skill_treated_current_and_logged(monkeypatch):
    monkeypatch.setattr(s, "skills_cli_available", lambda: True)
    desired = ["mattpocock/skills:grill-me"]
    lock = {"skills": {"grill-me": {"computedHash": "old"}}}
    out = io.StringIO()
    stale = s.skill_stale_names(
        desired, lock, resolver=_fake_resolver({}), out=out
    )
    assert stale == set()
    assert "grill-me" in out.getvalue()  # failure is visible, not swallowed


def test_stale_check_skipped_when_cli_absent(no_claude_cli, monkeypatch):
    monkeypatch.setattr(s, "skills_cli_available", lambda: False)
    desired = ["mattpocock/skills:grill-me"]
    lock = {"skills": {"grill-me": {"computedHash": "old"}}}
    # resolver must never be called when the CLI is absent.
    def boom(_):
        raise AssertionError("resolver called despite CLI absent")
    assert s.skill_stale_names(desired, lock, resolver=boom) == set()
