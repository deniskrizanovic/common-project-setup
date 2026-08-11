"""Tests for the plugin-management spec.

Base-only vs override composition; MISSING/STALE/EXTRA classification;
CLI-absent prints commands; EXTRA never removed.
"""
from __future__ import annotations

import io
import json

import pytest

import scaffold as s


def _patch_base_plugins(tmp_path, monkeypatch, plugins):
    base = tmp_path / "plugins.json"
    base.write_text(json.dumps({"plugins": plugins}), encoding="utf-8")
    monkeypatch.setattr(s, "BASE_PLUGINS", base)


def _write_installed(home, plugins):
    (home / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": plugins}), encoding="utf-8"
    )


def test_base_wishlist_applies(project_dir):
    """No .scaffold/plugins.json -> base wishlist alone is the desired set."""
    desired = s.compose_wishlist(project_dir)
    ids = {p["id"] for p in desired}
    assert "caveman@caveman" in ids
    assert "superpowers@claude-plugins-official" in ids


def test_override_composes(project_dir):
    """Override replaces same-id and extends with new ids."""
    scaffold_dir = project_dir / ".scaffold"
    scaffold_dir.mkdir()
    (scaffold_dir / "plugins.json").write_text(
        json.dumps(
            {
                "plugins": [
                    {"id": "caveman@caveman", "marketplaceSource": "custom/fork"},
                    {"id": "newplugin@mkt", "marketplaceSource": "acme/newplugin"},
                ]
            }
        ),
        encoding="utf-8",
    )
    by_id = {p["id"]: p for p in s.compose_wishlist(project_dir)}
    assert by_id["caveman@caveman"]["marketplaceSource"] == "custom/fork"
    assert "newplugin@mkt" in by_id


def test_classify_missing(fake_claude_home):
    desired = [{"id": "caveman@caveman"}]
    installed = s.read_installed_plugins()
    assert s.classify_plugins(desired, installed)["caveman@caveman"] == s.MISSING


def test_classify_stale(fake_claude_home):
    _write_installed(
        fake_claude_home,
        {"caveman@caveman": [{"scope": "user", "gitCommitSha": "old"}]},
    )
    desired = [{"id": "caveman@caveman", "gitCommitSha": "new"}]
    installed = s.read_installed_plugins()
    assert s.classify_plugins(desired, installed)["caveman@caveman"] == s.STALE


def test_classify_ok(fake_claude_home):
    _write_installed(
        fake_claude_home,
        {"caveman@caveman": [{"scope": "user", "gitCommitSha": "same"}]},
    )
    desired = [{"id": "caveman@caveman", "gitCommitSha": "same"}]
    installed = s.read_installed_plugins()
    assert s.classify_plugins(desired, installed)["caveman@caveman"] == s.OK


def test_classify_extra_never_removed(fake_claude_home):
    _write_installed(
        fake_claude_home,
        {"someplugin@mkt": [{"scope": "user", "gitCommitSha": "x"}]},
    )
    desired = [{"id": "caveman@caveman"}]
    installed = s.read_installed_plugins()
    result = s.classify_plugins(desired, installed)
    assert result["someplugin@mkt"] == s.EXTRA
    # Reconciliation is pure classification — the installed file is untouched.
    reread = s.read_installed_plugins()
    assert "someplugin@mkt" in reread["plugins"]


def test_registry_plugin_ids_match_wishlist(project_dir):
    """Every PluginComponent.id must be a composed name@marketplace id that the
    wishlist/classifier keys on — else cmd_list/cmd_install look up the wrong
    key and every plugin reads MISSING forever."""
    wishlist_ids = {p["id"] for p in s.compose_wishlist(project_dir)}
    plugin_ids = {c.id for c in s.build_registry() if isinstance(c, s.PluginComponent)}
    assert plugin_ids <= wishlist_ids


def test_cmd_list_shows_installed_plugin_ok(project_dir, fake_claude_home, monkeypatch):
    """An installed, up-to-date plugin reads OK through cmd_list — not MISSING."""
    _write_installed(
        fake_claude_home,
        {"caveman@caveman": [{"scope": "user"}],
         "superpowers@claude-plugins-official": [{"scope": "user"}]},
    )
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)
    out = io.StringIO()
    s.cmd_list(project_dir, s.build_registry(), out=out)
    text = out.getvalue()
    assert "[OK" in text
    assert "caveman@caveman" in text
    assert "MISSING         caveman@caveman" not in text


def test_plugin_components_synthesizes_optional_defaults(tmp_path, monkeypatch):
    """version/description are optional -> default to 1 and a synthesized label."""
    _patch_base_plugins(
        tmp_path,
        monkeypatch,
        [{"id": "caveman@caveman", "marketplaceSource": "dk/caveman"}],
    )
    comp = s._plugin_components()[0]
    assert comp.version == 1
    assert comp.description == "caveman plugin"
    assert comp.marketplace_source == "dk/caveman"


def test_plugin_components_missing_required_field_raises(tmp_path, monkeypatch):
    """A required field (marketplaceSource) absent -> clear SystemExit naming it."""
    _patch_base_plugins(
        tmp_path, monkeypatch, [{"id": "caveman@caveman"}]
    )
    with pytest.raises(SystemExit) as exc:
        s._plugin_components()
    msg = str(exc.value)
    assert "caveman@caveman" in msg
    assert "marketplaceSource" in msg


def test_plugin_components_missing_id_names_entry(tmp_path, monkeypatch):
    """An entry with no id is identified by index, not a KeyError traceback."""
    _patch_base_plugins(
        tmp_path, monkeypatch, [{"marketplaceSource": "dk/x"}]
    )
    with pytest.raises(SystemExit) as exc:
        s._plugin_components()
    assert "entry #0" in str(exc.value)
    assert "id" in str(exc.value)


def test_install_shells_out(stub_claude_cli):
    plugin = {"id": "caveman@caveman", "marketplaceSource": "dk/caveman"}
    assert s.install_plugin(plugin) is True
    calls = stub_claude_cli.read_text(encoding="utf-8")
    assert "plugin marketplace add dk/caveman" in calls
    assert "plugin install caveman@caveman" in calls


def test_cli_absent_prints_commands(no_claude_cli):
    plugin = {"id": "caveman@caveman", "marketplaceSource": "dk/caveman"}
    assert s.install_plugin(plugin) is False
    cmds = s.plugin_install_commands(plugin)
    assert cmds == [
        "claude plugin marketplace add dk/caveman",
        "claude plugin install caveman@caveman",
    ]


# --------------------------------------------------------------------------- #
# Generated-plugins.json path: plugins.json is now derived from manifest.yaml
# --------------------------------------------------------------------------- #
def test_committed_plugins_json_equals_generator_output():
    """The committed base plugins.json must equal what the manifest generates."""
    manifest = s.read_manifest_file()
    generated = s.generate_plugins_json(manifest)
    committed = json.loads(s.BASE_PLUGINS.read_text(encoding="utf-8"))
    assert committed == generated


def test_generated_plugins_feed_wishlist_and_registry(project_dir):
    """Plugins generated from the manifest still drive compose_wishlist/registry.

    The manifest source flows through the same plugins.json consumers untouched:
    every PluginComponent id is a composed wishlist id."""
    wishlist_ids = {p["id"] for p in s.compose_wishlist(project_dir)}
    plugin_ids = {c.id for c in s.build_registry() if isinstance(c, s.PluginComponent)}
    assert plugin_ids <= wishlist_ids
    # and those ids match the manifest's plugin ids
    manifest_ids = {p["id"] for p in s.read_manifest_file()["plugins"]}
    assert plugin_ids == manifest_ids
