"""Tests for the file-component-sourcing spec.

Source SHA recorded; disk-hash MODIFIED detection; offline check reports
honestly and never claims current on an unreachable source.
"""
from __future__ import annotations

import io
import json

import scaffold as s


def test_source_sha_recorded(project_dir):
    """Installed manifest entry records the source SHA and per-file hashes."""
    registry = s.build_registry()
    comp = next(c for c in registry if c.id == "cost-tracker")
    manifest = s.read_manifest(project_dir)
    s.install_file_component(project_dir, comp, manifest, "deadbeef")
    entry = manifest["components"]["cost-tracker"]
    assert entry["source_sha"] == "deadbeef"
    assert "tokencost/cost-tracker.py" in entry["files"]
    assert all(len(h) == 64 for h in entry["files"].values())


def test_resolve_source_sha_local_repo(stub_git_source):
    """A local git source resolves its HEAD SHA."""
    src, sha = stub_git_source
    resolved = s.resolve_source_sha({"url": str(src), "ref": "main"})
    assert resolved == sha


def test_resolve_source_sha_unreachable():
    """An unreachable source returns None (offline)."""
    assert s.resolve_source_sha({"url": "/no/such/repo", "ref": "main"}) is None


def test_disk_hash_modified_detection(project_dir):
    registry = s.build_registry()
    comp = next(c for c in registry if c.id == "cost-tracker")
    manifest = s.read_manifest(project_dir)
    s.install_file_component(project_dir, comp, manifest, "sha1")
    (project_dir / "tokencost" / "sum-cost.py").write_text("edited", encoding="utf-8")
    assert s.classify_file_component(project_dir, comp, manifest, "sha1") == s.MODIFIED


def test_offline_check_reports_honestly(project_dir, fake_claude_home, monkeypatch):
    """Offline: reports the offline note and never returns STALE/false-current."""
    registry = s.build_registry()
    comp = next(c for c in registry if c.id == "cost-tracker")
    manifest = s.read_manifest(project_dir)
    # Install pinned to an old sha, then go offline.
    s.install_file_component(project_dir, comp, manifest, "sha_old")
    s.write_manifest(project_dir, manifest)
    monkeypatch.setattr(s, "resolve_source_sha", lambda src: None)

    status = s.compute_status(project_dir, registry)
    assert status.offline is True
    # cost-tracker unmodified on disk but source unreachable -> OK by disk, but
    # never STALE (cannot be judged); classification must not be STALE.
    assert status.file_statuses["cost-tracker"] != s.STALE

    out = io.StringIO()
    s.cmd_check(project_dir, registry, out=out)
    text = out.getvalue()
    assert "STALE could not be evaluated" in text
