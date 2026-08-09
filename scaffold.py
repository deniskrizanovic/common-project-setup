#!/usr/bin/env python3
"""Interactive scaffold installer with drift detection.

One script, four subcommands:

  install   interactive per-component picker (install / update / skip, with diff)
  check     read-only drift report; writes nothing
  update    apply pending updates; --force to overwrite MODIFIED
  list      registry + status, no prompts

Two component classes behind one registry:
  - file components   : copied from this checkout's `templates/`, tracked by
                        content hash; the resolved source SHA is recorded so
                        STALE can be reported when the source ref advances
  - plugin components : reconciled against ~/.claude/plugins/installed_plugins.json,
                        installed via the `claude plugin install` CLI

Drift is recorded in `.scaffold/manifest.json` (component version, installed
source SHA, per-file sha256) and classified MISSING / STALE / MODIFIED /
MODIFIED+STALE / OK. STALE means the source ref moved past the recorded SHA;
`update` then re-copies this checkout's `templates/` bytes (pull the checkout
to the wanted ref first). Offline: falls back to disk-vs-manifest only and
says so.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# --------------------------------------------------------------------------- #
# Status constants
# --------------------------------------------------------------------------- #
MISSING = "MISSING"
STALE = "STALE"
MODIFIED = "MODIFIED"
MODIFIED_STALE = "MODIFIED+STALE"
OK = "OK"
EXTRA = "EXTRA"

# Where this script and its payloads live (canonical source in the repo).
REPO_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = REPO_ROOT / "templates"
BASE_PLUGINS = REPO_ROOT / "scaffold_base" / "plugins.json"

DEFAULT_SOURCE_REF = "main"


# --------------------------------------------------------------------------- #
# Component registry
# --------------------------------------------------------------------------- #
@dataclass
class FileComponent:
    """A component installed by copying tracked files from this checkout's templates/."""

    id: str
    version: int
    description: str
    # (source_path relative to TEMPLATES_DIR, dest_path relative to project root)
    files: list[tuple[str, str]]
    # optional predicate: given project root, is the component satisfied beyond
    # file presence? Used by config-baseline to reject the empty template.
    satisfied: Optional[Callable[[Path], bool]] = None
    kind: str = "file"


@dataclass
class PluginComponent:
    """A component reconciled against installed_plugins.json via the claude CLI."""

    id: str
    version: int
    description: str
    marketplace: str
    marketplace_source: str
    kind: str = "plugin"


def _config_is_real(project_root: Path) -> bool:
    """True when openspec/config.yaml has a real (uncommented) context block."""
    cfg = project_root / "openspec" / "config.yaml"
    if not cfg.is_file():
        return False
    text = cfg.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        # An uncommented top-level `context:` key means real content.
        if stripped.startswith("context:") and not stripped.startswith("#"):
            return True
    return False


def _plugin_components() -> list[PluginComponent]:
    """PluginComponents built from scaffold_base/plugins.json (no hardcoding).

    Each entry needs id/marketplace/marketplaceSource; version and description
    are optional and default to 1 and a synthesized label.
    """
    components = []
    for p in load_base_wishlist():
        components.append(
            PluginComponent(
                id=p["id"],
                version=p.get("version", 1),
                description=p.get("description", f"{p['id'].split('@')[0]} plugin"),
                marketplace=p["marketplace"],
                marketplace_source=p["marketplaceSource"],
            )
        )
    return components


def build_registry() -> list:
    """The single iterable registry both install and check walk."""
    return [
        FileComponent(
            id="config-baseline",
            version=1,
            description="Filled openspec/config.yaml (context + traceability rules)",
            files=[("openspec/config.yaml", "openspec/config.yaml")],
            satisfied=_config_is_real,
        ),
        FileComponent(
            id="schema-clone",
            version=1,
            description="Local spec-driven schema clone with traceability instructions",
            files=[
                ("openspec/schemas/spec-driven/schema.yaml",
                 "openspec/schemas/spec-driven/schema.yaml"),
                ("openspec/schemas/spec-driven/templates/proposal.md",
                 "openspec/schemas/spec-driven/templates/proposal.md"),
                ("openspec/schemas/spec-driven/templates/spec.md",
                 "openspec/schemas/spec-driven/templates/spec.md"),
                ("openspec/schemas/spec-driven/templates/design.md",
                 "openspec/schemas/spec-driven/templates/design.md"),
                ("openspec/schemas/spec-driven/templates/tasks.md",
                 "openspec/schemas/spec-driven/templates/tasks.md"),
            ],
        ),
        FileComponent(
            id="enforcement-hooks",
            version=1,
            description="branch-guard + commit-gate hook scripts (wired idempotently)",
            files=[
                ("scripts/branch_guard.py", "scripts/branch_guard.py"),
                ("scripts/commit_gate.py", "scripts/commit_gate.py"),
            ],
        ),
        FileComponent(
            id="cost-tracker",
            version=1,
            description="Project-local tokencost/ session cost tracker",
            files=[
                ("tokencost/cost-tracker.py", "tokencost/cost-tracker.py"),
                ("tokencost/sum-cost.py", "tokencost/sum-cost.py"),
                ("tokencost/.provenance", "tokencost/.provenance"),
            ],
        ),
        FileComponent(
            id="lint-gates",
            version=1,
            description="lint:specs and lint:given traceability gates",
            files=[
                ("scripts/lint_specs.py", "scripts/lint_specs.py"),
                ("scripts/lint_given.py", "scripts/lint_given.py"),
            ],
        ),
        *_plugin_components(),
    ]


# --------------------------------------------------------------------------- #
# Manifest read/write
# --------------------------------------------------------------------------- #
def manifest_path(project_root: Path) -> Path:
    return project_root / ".scaffold" / "manifest.json"


def read_manifest(project_root: Path) -> dict:
    path = manifest_path(project_root)
    if not path.is_file():
        return {"components": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"components": {}}
    data.setdefault("components", {})
    return data


def write_manifest(project_root: Path, manifest: dict) -> None:
    path = manifest_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- #
# Git source
# --------------------------------------------------------------------------- #
def source_config(project_root: Path) -> dict:
    """Resolve source url+ref: .scaffold/source.json, then env, then defaults."""
    url = os.environ.get("SCAFFOLD_SOURCE_URL")
    ref = os.environ.get("SCAFFOLD_SOURCE_REF")
    cfg = project_root / ".scaffold" / "source.json"
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            url = url or data.get("url")
            ref = ref or data.get("ref")
        except (json.JSONDecodeError, OSError):
            pass
    return {"url": url or str(REPO_ROOT), "ref": ref or DEFAULT_SOURCE_REF}


def _local_head_sha(url: str) -> Optional[str]:
    """HEAD SHA of a local git checkout, or None if not a resolvable repo."""
    try:
        return subprocess.check_output(
            ["git", "-C", url, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def resolve_source_sha(source: dict) -> Optional[str]:
    """Resolve the source ref to a SHA. None when the source is unreachable."""
    try:
        out = subprocess.check_output(
            ["git", "ls-remote", source["url"], source["ref"]],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Local source dir: use its HEAD.
        return _local_head_sha(source["url"])
    if not out:
        # ls-remote succeeded but the ref is absent (common for a local repo on
        # a branch other than `ref`): fall back to the checkout's HEAD.
        return _local_head_sha(source["url"])
    return out.split()[0]


# --------------------------------------------------------------------------- #
# Drift classification (file components)
# --------------------------------------------------------------------------- #
def classify_file_component(
    project_root: Path,
    comp: FileComponent,
    manifest: dict,
    source_sha: Optional[str],
) -> str:
    """Classify a file component using disk, manifest, and source SHA.

    `source_sha` is None when the source is unreachable (offline): STALE cannot
    be evaluated, so we never return STALE and never claim OK on that basis.
    """
    entry = manifest["components"].get(comp.id)
    dest_paths = [project_root / dest for _, dest in comp.files]

    if entry is None:
        # No manifest record: MISSING unless a satisfied() predicate says
        # otherwise is impossible — with no record it is MISSING.
        return MISSING

    # Files gone from disk => treat as MISSING.
    if any(not p.is_file() for p in dest_paths):
        return MISSING

    # Optional satisfaction predicate (e.g. empty-template detection).
    if comp.satisfied is not None and not comp.satisfied(project_root):
        return MISSING

    modified = False
    recorded = entry.get("files", {})
    for _, dest in comp.files:
        disk_hash = sha256_file(project_root / dest)
        if recorded.get(dest) != disk_hash:
            modified = True
            break

    stale = False
    if source_sha is not None:
        stale = entry.get("source_sha") not in (None, source_sha)

    if modified and stale:
        return MODIFIED_STALE
    if modified:
        return MODIFIED
    if stale:
        return STALE
    return OK


# --------------------------------------------------------------------------- #
# File component install / update
# --------------------------------------------------------------------------- #
def install_file_component(
    project_root: Path,
    comp: FileComponent,
    manifest: dict,
    source_sha: Optional[str],
) -> None:
    """Copy tracked files from templates and record hashes in the manifest."""
    files_hashes = {}
    for src, dest in comp.files:
        src_path = TEMPLATES_DIR / src
        dest_path = project_root / dest
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_path, dest_path)
        files_hashes[dest] = sha256_file(dest_path)
    manifest["components"][comp.id] = {
        "kind": "file",
        "version": comp.version,
        "source_sha": source_sha,
        "files": files_hashes,
    }


def component_diff(project_root: Path, comp: FileComponent) -> str:
    """Unified diff between on-disk files and the incoming template versions."""
    chunks = []
    for src, dest in comp.files:
        src_path = TEMPLATES_DIR / src
        dest_path = project_root / dest
        incoming = src_path.read_text(encoding="utf-8").splitlines(keepends=True)
        current = (
            dest_path.read_text(encoding="utf-8").splitlines(keepends=True)
            if dest_path.is_file()
            else []
        )
        diff = difflib.unified_diff(
            current, incoming, fromfile=f"a/{dest}", tofile=f"b/{dest}"
        )
        chunks.append("".join(diff))
    return "\n".join(c for c in chunks if c.strip())


# --------------------------------------------------------------------------- #
# Plugin reconciliation
# --------------------------------------------------------------------------- #
def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))


def read_installed_plugins() -> dict:
    path = claude_home() / "plugins" / "installed_plugins.json"
    if not path.is_file():
        return {"plugins": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"plugins": {}}
    data.setdefault("plugins", {})
    return data


def load_base_wishlist() -> list[dict]:
    if not BASE_PLUGINS.is_file():
        return []
    try:
        return json.loads(BASE_PLUGINS.read_text(encoding="utf-8")).get("plugins", [])
    except (json.JSONDecodeError, OSError):
        return []


def compose_wishlist(project_root: Path) -> list[dict]:
    """Base wishlist composed with the per-project .scaffold/plugins.json override.

    Override entries with the same id replace the base entry; new ids extend.
    """
    by_id = {p["id"]: dict(p) for p in load_base_wishlist()}
    override = project_root / ".scaffold" / "plugins.json"
    if override.is_file():
        try:
            entries = json.loads(override.read_text(encoding="utf-8")).get("plugins", [])
            for p in entries:
                by_id[p["id"]] = dict(p)
        except (json.JSONDecodeError, OSError):
            pass
    return list(by_id.values())


def _plugin_records(installed: dict, plugin_id: str) -> list[dict]:
    recs = installed["plugins"].get(plugin_id, [])
    return recs if isinstance(recs, list) else [recs]


def classify_plugins(desired: list[dict], installed: dict) -> dict:
    """Return {id: status} for desired + EXTRA installed-but-not-desired."""
    result = {}
    desired_ids = {p["id"] for p in desired}
    for p in desired:
        recs = _plugin_records(installed, p["id"])
        if not recs:
            result[p["id"]] = MISSING
            continue
        head = p.get("gitCommitSha")
        if head and all(r.get("gitCommitSha") != head for r in recs):
            result[p["id"]] = STALE
        else:
            result[p["id"]] = OK
    for installed_id in installed["plugins"]:
        if installed_id not in desired_ids:
            result[installed_id] = EXTRA
    return result


def claude_cli_available() -> bool:
    return shutil.which("claude") is not None


def plugin_install_commands(plugin: dict) -> list[str]:
    """The exact commands to register the marketplace and install the plugin."""
    cmds = []
    src = plugin.get("marketplaceSource")
    if src:
        cmds.append(f"claude plugin marketplace add {src}")
    cmds.append(f"claude plugin install {plugin['id']}")
    return cmds


def install_plugin(plugin: dict) -> bool:
    """Shell out to the claude CLI. Returns True on success, False if CLI absent."""
    if not claude_cli_available():
        return False
    for cmd in plugin_install_commands(plugin):
        subprocess.run(cmd.split(), check=False)
    return True


# --------------------------------------------------------------------------- #
# Status computation shared by list / check / install
# --------------------------------------------------------------------------- #
@dataclass
class Status:
    file_statuses: dict = field(default_factory=dict)
    plugin_statuses: dict = field(default_factory=dict)
    source_sha: Optional[str] = None
    offline: bool = False


def compute_status(project_root: Path, registry: list, *, fetch: bool = True) -> Status:
    manifest = read_manifest(project_root)
    source = source_config(project_root)
    source_sha = resolve_source_sha(source) if fetch else None
    offline = source_sha is None

    file_statuses = {}
    for comp in registry:
        if isinstance(comp, FileComponent):
            file_statuses[comp.id] = classify_file_component(
                project_root, comp, manifest, source_sha
            )

    desired = compose_wishlist(project_root)
    plugin_statuses = classify_plugins(desired, read_installed_plugins())

    return Status(
        file_statuses=file_statuses,
        plugin_statuses=plugin_statuses,
        source_sha=source_sha,
        offline=offline,
    )


# --------------------------------------------------------------------------- #
# Subcommands
# --------------------------------------------------------------------------- #
def cmd_list(project_root: Path, registry: list, out=sys.stdout) -> int:
    status = compute_status(project_root, registry)
    print("Components:", file=out)
    for comp in registry:
        if isinstance(comp, FileComponent):
            st = status.file_statuses[comp.id]
            print(f"  [{st:<14}] {comp.id}  (file)  — {comp.description}", file=out)
    for comp in registry:
        if isinstance(comp, PluginComponent):
            st = status.plugin_statuses.get(comp.id, MISSING)
            print(f"  [{st:<14}] {comp.id}  (plugin) — {comp.description}", file=out)
    for pid, st in status.plugin_statuses.items():
        if st == EXTRA:
            print(f"  [{EXTRA:<14}] {pid}  (plugin, not in wishlist)", file=out)
    return 0


def cmd_check(project_root: Path, registry: list, out=sys.stdout) -> int:
    status = compute_status(project_root, registry)
    if status.offline:
        print(
            "! source unreachable — STALE could not be evaluated; "
            "reporting disk-vs-manifest (MODIFIED) only.",
            file=out,
        )
    print("File components:", file=out)
    for comp in registry:
        if isinstance(comp, FileComponent):
            print(f"  {status.file_statuses[comp.id]:<14} {comp.id}", file=out)
    print("Plugins:", file=out)
    for pid, st in status.plugin_statuses.items():
        print(f"  {st:<14} {pid}", file=out)
    return 0


def _prompt(prompt: str, valid: list[str], reader=input) -> str:
    while True:
        ans = reader(prompt).strip().lower()
        if ans in valid:
            return ans


def cmd_install(
    project_root: Path,
    registry: list,
    reader=input,
    out=sys.stdout,
) -> int:
    manifest = read_manifest(project_root)
    status = compute_status(project_root, registry)
    source_sha = status.source_sha

    for comp in registry:
        if isinstance(comp, FileComponent):
            st = status.file_statuses[comp.id]
            print(f"\n{comp.id} — {st}: {comp.description}", file=out)
            if st == OK:
                print("  current; skipping.", file=out)
                continue
            while True:
                choice = _prompt(
                    "  [i]nstall/update, [d]iff, [s]kip? ",
                    ["i", "d", "s"],
                    reader,
                )
                if choice == "d":
                    print(component_diff(project_root, comp) or "  (no diff)", file=out)
                    continue
                if choice == "s":
                    break
                install_file_component(project_root, comp, manifest, source_sha)
                write_manifest(project_root, manifest)
                print("  installed.", file=out)
                break
        else:
            st = status.plugin_statuses.get(comp.id, MISSING)
            print(f"\n{comp.id} — {st}: {comp.description}", file=out)
            if st == OK:
                print("  current; skipping.", file=out)
                continue
            choice = _prompt("  [i]nstall/update, [s]kip? ", ["i", "s"], reader)
            if choice == "s":
                continue
            plugin = {
                "id": comp.id,
                "marketplaceSource": comp.marketplace_source,
            }
            if not install_plugin(plugin):
                print("  claude CLI not found. Run these commands manually:", file=out)
                for cmd in plugin_install_commands(plugin):
                    print(f"    {cmd}", file=out)

    # Wire hooks idempotently once enforcement-hooks/cost-tracker present.
    wire_hooks(project_root)
    return 0


def cmd_update(
    project_root: Path,
    registry: list,
    component: Optional[str] = None,
    force: bool = False,
    out=sys.stdout,
) -> int:
    manifest = read_manifest(project_root)
    status = compute_status(project_root, registry)
    source_sha = status.source_sha

    targets = [
        c
        for c in registry
        if isinstance(c, FileComponent) and (component is None or c.id == component)
    ]
    if component is not None and not targets:
        print(f"Unknown component: {component}", file=out)
        return 1

    for comp in targets:
        st = status.file_statuses[comp.id]
        if st in (MODIFIED, MODIFIED_STALE) and not force:
            print(
                f"{comp.id}: {st} — refusing to overwrite local edits without "
                "--force; leaving unchanged.",
                file=out,
            )
            continue
        if st == OK:
            print(f"{comp.id}: current; nothing to do.", file=out)
            continue
        install_file_component(project_root, comp, manifest, source_sha)
        write_manifest(project_root, manifest)
        print(f"{comp.id}: updated.", file=out)
    return 0


# --------------------------------------------------------------------------- #
# Idempotent hook wiring
# --------------------------------------------------------------------------- #
def _hook_command_exists(hooks_block: list, command: str) -> bool:
    for group in hooks_block:
        for hook in group.get("hooks", []):
            if hook.get("command") == command:
                return True
    return False


def wire_hooks(project_root: Path) -> None:
    """Add branch-guard, commit-gate, and cost-tracker hooks idempotently.

    Dedupes by exact command string and preserves unrelated existing hooks.
    """
    settings_path = project_root / ".claude" / "settings.json"
    settings = {}
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            settings = {}
    hooks = settings.setdefault("hooks", {})

    branch_guard_cmd = 'python3 "$CLAUDE_PROJECT_DIR/scripts/branch_guard.py" "$CLAUDE_PROJECT_DIR"'
    commit_gate_cmd = 'python3 "$CLAUDE_PROJECT_DIR/scripts/commit_gate.py" "$CLAUDE_PROJECT_DIR"'
    cost_start_cmd = 'python3 "$CLAUDE_PROJECT_DIR/tokencost/cost-tracker.py" backfill'
    cost_end_cmd = 'python3 "$CLAUDE_PROJECT_DIR/tokencost/cost-tracker.py" finalize'

    # commit-gate uses a broad `Bash` matcher and self-filters to `git commit`
    # via commit_gate.is_git_commit — Claude Code hook entries have no per-hook
    # conditional field, so scoping is by matcher + the script's own guard.
    wanted = [
        ("PreToolUse", "Edit|Write|NotebookEdit", branch_guard_cmd),
        ("PreToolUse", "Bash", commit_gate_cmd),
        ("SessionStart", "", cost_start_cmd),
        ("SessionEnd", "", cost_end_cmd),
    ]

    for event, matcher, command in wanted:
        block = hooks.setdefault(event, [])
        if _hook_command_exists(block, command):
            continue
        entry = {"type": "command", "command": command}
        block.append({"matcher": matcher, "hooks": [entry]})

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", default=".", help="Target project root (default: cwd)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("check")
    sub.add_parser("install")
    up = sub.add_parser("update")
    up.add_argument("component", nargs="?", default=None)
    up.add_argument("--force", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project).resolve()
    registry = build_registry()

    if args.command == "list":
        return cmd_list(project_root, registry)
    if args.command == "check":
        return cmd_check(project_root, registry)
    if args.command == "install":
        return cmd_install(project_root, registry)
    if args.command == "update":
        return cmd_update(project_root, registry, args.component, args.force)
    return 1


if __name__ == "__main__":
    sys.exit(main())
