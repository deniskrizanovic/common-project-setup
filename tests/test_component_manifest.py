"""Tests for the component-manifest spec.

Manifest parsing (both sections, malformed rejection); artifact generation for
plugins.json and skills-lock.json; drift guard in-sync vs drifted.
"""
from __future__ import annotations

import json

import pytest

import scaffold as s

VALID_MANIFEST = """\
plugins:
  - id: caveman@caveman
    source: dk-krizanovic/caveman
  - id: superpowers@claude-plugins-official
    source: anthropics/claude-plugins

skills:
  - mattpocock/skills:grill-me
  - deniskrizanovic/dk-skills:diff-org-changes
"""


# --------------------------------------------------------------------------- #
# 2.3 Manifest parsing
# --------------------------------------------------------------------------- #
def test_parse_both_sections():
    data = s.parse_manifest(VALID_MANIFEST)
    assert [p["id"] for p in data["plugins"]] == [
        "caveman@caveman",
        "superpowers@claude-plugins-official",
    ]
    assert data["plugins"][0]["source"] == "dk-krizanovic/caveman"
    assert data["skills"] == [
        "mattpocock/skills:grill-me",
        "deniskrizanovic/dk-skills:diff-org-changes",
    ]


def test_read_manifest_file_valid(tmp_path):
    m = tmp_path / "manifest.yaml"
    m.write_text(VALID_MANIFEST, encoding="utf-8")
    data = s.read_manifest_file(m)
    assert len(data["plugins"]) == 2
    assert len(data["skills"]) == 2


def test_malformed_plugin_missing_id_rejected(tmp_path):
    m = tmp_path / "manifest.yaml"
    m.write_text("plugins:\n  - source: acme/x\nskills: []\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        s.read_manifest_file(m)
    assert "id" in str(exc.value)


def test_malformed_plugin_missing_source_rejected(tmp_path):
    m = tmp_path / "manifest.yaml"
    m.write_text("plugins:\n  - id: x@y\nskills: []\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        s.read_manifest_file(m)
    msg = str(exc.value)
    assert "x@y" in msg
    assert "source" in msg


def test_malformed_skill_rejected(tmp_path):
    m = tmp_path / "manifest.yaml"
    m.write_text("plugins: []\nskills:\n  - not-a-valid-skill\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        s.read_manifest_file(m)
    assert "not-a-valid-skill" in str(exc.value)


def test_unknown_section_rejected(tmp_path):
    m = tmp_path / "manifest.yaml"
    m.write_text("widgets:\n  - foo\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        s.read_manifest_file(m)
    assert "widgets" in str(exc.value)


def test_skill_name_and_source_helpers():
    assert s.skill_name_from_id("mattpocock/skills:grill-me") == "grill-me"
    assert s.skill_source_from_id("mattpocock/skills:grill-me") == "mattpocock/skills"
    # nested path segment -> last segment is the name
    assert s.skill_name_from_id("o/r:a/b/deep-skill") == "deep-skill"


# --------------------------------------------------------------------------- #
# 3.3 Generator output
# --------------------------------------------------------------------------- #
def test_generate_plugins_json_shape():
    manifest = s.parse_manifest(VALID_MANIFEST)
    out = s.generate_plugins_json(manifest)
    assert out == {
        "plugins": [
            {
                "id": "caveman@caveman",
                "marketplace": "caveman",
                "marketplaceSource": "dk-krizanovic/caveman",
            },
            {
                "id": "superpowers@claude-plugins-official",
                "marketplace": "claude-plugins-official",
                "marketplaceSource": "anthropics/claude-plugins",
            },
        ]
    }


def test_generate_skills_lock_with_stub_resolver():
    manifest = s.parse_manifest(VALID_MANIFEST)

    def fake_resolver(skill_id):
        name = s.skill_name_from_id(skill_id)
        return {
            "source": s.skill_source_from_id(skill_id),
            "sourceType": "github",
            "skillPath": f"{name}/SKILL.md",
            "computedHash": "a" * 64,
        }

    lock = s.generate_skills_lock(manifest, resolver=fake_resolver)
    assert lock["version"] == 1
    # sorted keys, one entry per skill
    assert list(lock["skills"].keys()) == ["diff-org-changes", "grill-me"]
    entry = lock["skills"]["grill-me"]
    assert entry["source"] == "mattpocock/skills"
    assert entry["sourceType"] == "github"
    assert entry["skillPath"] == "grill-me/SKILL.md"
    assert entry["computedHash"] == "a" * 64


# --------------------------------------------------------------------------- #
# 3.6 Drift guard
# --------------------------------------------------------------------------- #
def _write_artifacts(tmp_path, manifest_text, plugins, lock):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(manifest_text, encoding="utf-8")
    (tmp_path / "plugins.json").write_text(json.dumps(plugins, indent=2) + "\n", "utf-8")
    (tmp_path / "skills-lock.json").write_text(json.dumps(lock, indent=2) + "\n", "utf-8")
    return manifest


def _patch_bases(monkeypatch, tmp_path):
    monkeypatch.setattr(s, "BASE_PLUGINS", tmp_path / "plugins.json")
    monkeypatch.setattr(s, "BASE_SKILLS_LOCK", tmp_path / "skills-lock.json")


def test_drift_in_sync_passes(tmp_path, monkeypatch):
    manifest = s.parse_manifest(VALID_MANIFEST)
    plugins = s.generate_plugins_json(manifest)
    lock = {
        "version": 1,
        "skills": {
            "grill-me": {"source": "mattpocock/skills", "sourceType": "github",
                         "skillPath": "x", "computedHash": "y"},
            "diff-org-changes": {"source": "deniskrizanovic/dk-skills",
                                 "sourceType": "github", "skillPath": "x",
                                 "computedHash": "y"},
        },
    }
    m = _write_artifacts(tmp_path, VALID_MANIFEST, plugins, lock)
    _patch_bases(monkeypatch, tmp_path)
    assert s.check_drift(m) == []


def _pin(source):
    """A valid lock entry with non-empty pins (isolates non-pin drift dimensions)."""
    return {"source": source, "sourceType": "github",
            "skillPath": "x/SKILL.md", "computedHash": "h"}


def test_drift_plugins_out_of_sync_named(tmp_path, monkeypatch):
    manifest = s.parse_manifest(VALID_MANIFEST)
    lock = {
        "version": 1,
        "skills": {
            "grill-me": _pin("mattpocock/skills"),
            "diff-org-changes": _pin("deniskrizanovic/dk-skills"),
        },
    }
    # plugins.json missing an entry -> drift
    m = _write_artifacts(tmp_path, VALID_MANIFEST, {"plugins": []}, lock)
    _patch_bases(monkeypatch, tmp_path)
    problems = s.check_drift(m)
    assert len(problems) == 1
    assert "plugins.json" in problems[0]


def test_drift_skills_out_of_sync_named(tmp_path, monkeypatch):
    manifest = s.parse_manifest(VALID_MANIFEST)
    plugins = s.generate_plugins_json(manifest)
    # lock missing diff-org-changes -> skills drift
    lock = {"version": 1, "skills": {"grill-me": _pin("mattpocock/skills")}}
    m = _write_artifacts(tmp_path, VALID_MANIFEST, plugins, lock)
    _patch_bases(monkeypatch, tmp_path)
    problems = s.check_drift(m)
    assert len(problems) == 1
    assert "skills-lock.json" in problems[0]


def test_drift_skills_source_change_detected(tmp_path, monkeypatch):
    """A skill's source repo changing in the manifest is drift the guard catches."""
    manifest = s.parse_manifest(VALID_MANIFEST)
    plugins = s.generate_plugins_json(manifest)
    lock = {
        "version": 1,
        "skills": {
            "grill-me": {"source": "someoneelse/skills"},  # wrong source
            "diff-org-changes": {"source": "deniskrizanovic/dk-skills"},
        },
    }
    m = _write_artifacts(tmp_path, VALID_MANIFEST, plugins, lock)
    _patch_bases(monkeypatch, tmp_path)
    problems = s.check_drift(m)
    assert any("skills-lock.json" in p for p in problems)


def test_drift_empty_pin_detected(tmp_path, monkeypatch):
    """A locked skill whose skillPath/computedHash is blank is drift, even when
    names/sources match — catches a broken `gen` that wrote empty pins."""
    manifest = s.parse_manifest(VALID_MANIFEST)
    plugins = s.generate_plugins_json(manifest)
    lock = {
        "version": 1,
        "skills": {
            "grill-me": {"source": "mattpocock/skills", "sourceType": "github",
                         "skillPath": "", "computedHash": ""},  # blank pin
            "diff-org-changes": _pin("deniskrizanovic/dk-skills"),
        },
    }
    m = _write_artifacts(tmp_path, VALID_MANIFEST, plugins, lock)
    _patch_bases(monkeypatch, tmp_path)
    problems = s.check_drift(m)
    assert any("empty skillPath/computedHash" in p and "grill-me" in p for p in problems)


def test_committed_artifacts_in_sync():
    """The repo's committed artifacts must not drift from manifest.yaml."""
    assert s.check_drift() == []
