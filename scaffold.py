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
import re
import shutil
import subprocess
import sys
import tempfile
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
# Precondition unmet: an OpenSpec-dependent component with no initialized root.
# Distinct from MISSING ("installable now"); install refuses it, check/list
# report it read-only.
BLOCKED = "BLOCKED"

# Where this script and its payloads live (canonical source in the repo).
REPO_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = REPO_ROOT / "templates"
SCAFFOLD_BASE = REPO_ROOT / "scaffold_base"
BASE_MANIFEST = SCAFFOLD_BASE / "manifest.yaml"
BASE_PLUGINS = SCAFFOLD_BASE / "plugins.json"
BASE_SKILLS_LOCK = SCAFFOLD_BASE / "skills-lock.json"

DEFAULT_SOURCE_REF = "main"

# A skill identifier in the manifest: "owner/repo:skill-path".
SKILL_ID_RE = re.compile(r"^[^/\s]+/[^/\s:]+:[^\s:]+$")


# --------------------------------------------------------------------------- #
# Component registry
# --------------------------------------------------------------------------- #
# Remedy printed when a `needs_openspec` component is BLOCKED. Kept as a module
# constant so it is one instance of the generalized precondition shape below.
OPENSPEC_REMEDY = (
    "OpenSpec is not initialized. Run `openspec init . --tools claude` first, "
    "then re-run install."
)

# Remedy printed when a `needs_git` component is BLOCKED — mirrors OPENSPEC_REMEDY
# but for the git-repository gate (github-init needs a work tree to have a remote).
GIT_REMEDY = (
    "Not a git repository. Run `git init` and make an initial commit first, "
    "then re-run install."
)


@dataclass
class Precondition:
    """A per-component runtime gate. When `check` is unmet the component is
    classified BLOCKED and `remedy` is the actionable message reported to the
    user. `needs_openspec` is a second, root-probe-threaded instance of the same
    shape (see `unmet_precondition`)."""

    check: Callable[[Path], bool]
    remedy: str


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
    # optional interview callable: given (project_root, reader, out), fill the
    # component in place instead of copying a template. Used by config-interview.
    # A filler-bearing component has no tracked source hash: it classifies
    # MISSING/OK only (via `satisfied`), never STALE/MODIFIED.
    filler: Optional[Callable[[Path, Callable, object], None]] = None
    # True when the component reads/writes inside openspec/ and therefore
    # requires an initialized OpenSpec root. Absent a root, such a component is
    # classified BLOCKED (precondition unmet) instead of MISSING, and install
    # refuses it rather than fabricating an unrecognized openspec/ tree.
    needs_openspec: bool = False
    # True when the component requires the project root to be a git work tree
    # (e.g. github-init detects a git remote). Absent a repo, such a component is
    # classified BLOCKED, mirroring needs_openspec. Install prints how to init git
    # and takes no outward action.
    needs_git: bool = False
    # optional runtime precondition (predicate + remedy). When unmet the
    # component is BLOCKED, mirroring needs_openspec but for a general dependency
    # (e.g. cost-tracker requires `pnpm` to provision ccusage).
    precondition: Optional[Precondition] = None
    # optional post-copy step: given (project_root, out), run after the tracked
    # files are installed. Used by cost-tracker to provision the ccusage CLI.
    post_install: Optional[Callable[[Path, object], None]] = None
    # optional print-only installer: given (project_root, out), print advisory
    # commands instead of copying anything. A printer-bearing component tracks no
    # files, records no hash, and takes no outward action — its drift is
    # satisfied()-only (BLOCKED/MISSING/OK). Used by github-init to nag the user
    # to create a GitHub repo without running the command itself.
    printer: Optional[Callable[[Path, object], None]] = None
    kind: str = "file"


@dataclass
class PluginComponent:
    """A component reconciled against installed_plugins.json via the claude CLI."""

    id: str
    version: int
    description: str
    marketplace_source: str
    kind: str = "plugin"


@dataclass
class SkillComponent:
    """A github-sourced skill reconciled against skills-lock.json via `npx skills`.

    `id` is the manifest identifier "owner/repo:skill-path"; `name` is the last
    path segment used as the skills-lock.json key and the `--skill` argument;
    `source` is the "owner/repo" the CLI clones from.
    """

    id: str
    version: int
    description: str
    source: str
    name: str
    kind: str = "skill"


# --------------------------------------------------------------------------- #
# Manifest reader (single source of truth)
# --------------------------------------------------------------------------- #
def parse_manifest(text: str) -> dict:
    """Parse the constrained manifest.yaml into {"plugins": [...], "skills": [...]}.

    Deliberately a small stdlib parser (not PyYAML): scaffold.py runs as a
    standalone `python3 scaffold.py` with zero third-party dependencies. The
    manifest format is a fixed, documented shape — two typed top-level sections
    of list items — so a full YAML engine is unwarranted.

    Supported shape:
        plugins:
          - id: name@marketplace
            source: owner/repo
        skills:
          - owner/repo:skill-path
    """
    plugins: list[dict] = []
    skills: list[str] = []
    section: Optional[str] = None
    current: Optional[dict] = None

    for raw in text.splitlines():
        # Strip comments and trailing whitespace; ignore blank lines.
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # Top-level section header: `plugins:` / `skills:` (no indent).
        # Accepts both a block form (`plugins:`) and an inline empty list
        # (`plugins: []`); a non-empty inline list is not supported.
        if indent == 0 and not stripped.startswith("- "):
            head, sep, rest = stripped.partition(":")
            if sep == ":" and ":" not in head:
                key = head.strip()
                if key not in ("plugins", "skills"):
                    raise SystemExit(f"manifest.yaml: unknown top-level section '{key}'")
                rest = rest.strip()
                if rest not in ("", "[]"):
                    raise SystemExit(
                        f"manifest.yaml: section '{key}' must use block list form "
                        f"or '[]', got: {rest!r}"
                    )
                section = key
                current = None
                continue

        if section is None:
            raise SystemExit(f"manifest.yaml: content outside any section: {stripped!r}")

        # List item.
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if section == "skills":
                skills.append(item)
                current = None
                continue
            # plugins: item is either "key: value" (inline start of a mapping)
            current = {}
            plugins.append(current)
            k, _, v = item.partition(":")
            if _ != "":
                current[k.strip()] = v.strip()
            continue

        # Continuation of the current plugin mapping (`  key: value`).
        if section == "plugins" and current is not None and ":" in stripped:
            k, _, v = stripped.partition(":")
            current[k.strip()] = v.strip()
            continue

        raise SystemExit(f"manifest.yaml: could not parse line: {stripped!r}")

    return {"plugins": plugins, "skills": skills}


def read_manifest_file(path: Path = BASE_MANIFEST) -> dict:
    """Read + validate manifest.yaml. Raises SystemExit on any malformed entry."""
    if not path.is_file():
        raise SystemExit(f"manifest not found: {path}")
    data = parse_manifest(path.read_text(encoding="utf-8"))

    for i, p in enumerate(data["plugins"]):
        pid = p.get("id")
        src = p.get("source")
        missing = [k for k, v in (("id", pid), ("source", src)) if not v]
        if missing:
            label = f"'{pid}'" if pid else f"entry #{i}"
            raise SystemExit(
                f"manifest.yaml: plugin {label} is missing required "
                f"field(s): {', '.join(missing)}"
            )

    seen_names: dict[str, str] = {}
    for s in data["skills"]:
        if not SKILL_ID_RE.match(s):
            raise SystemExit(
                f"manifest.yaml: skill entry {s!r} is not a valid "
                f"'owner/repo:skill-path' string"
            )
        # Two distinct ids that reduce to the same skills-lock.json key would
        # silently clobber one another during generation. Reject at parse time.
        name = skill_name_from_id(s)
        if name in seen_names and seen_names[name] != s:
            raise SystemExit(
                f"manifest.yaml: skill name {name!r} is claimed by two "
                f"entries ({seen_names[name]!r} and {s!r}); skill names must "
                f"be unique across the manifest"
            )
        seen_names[name] = s

    return data


def skill_name_from_id(skill_id: str) -> str:
    """The skills-lock.json key / `--skill` name: the last path segment."""
    path = skill_id.split(":", 1)[1]
    return path.rstrip("/").split("/")[-1]


def skill_source_from_id(skill_id: str) -> str:
    """The 'owner/repo' the CLI clones from."""
    return skill_id.split(":", 1)[0]


# The pinned CLI package spec used for every `npx skills` invocation, so the
# resolver, the installer and the staleness check all run the same version.
SKILLS_CLI_PKG = "skills@latest"


def skills_add_argv(skill_id: str) -> list[str]:
    """The single canonical `npx skills add` argv used by every call site.

    `--copy` was previously passed only by the hash resolver; the CLI's
    computedHash is identical with or without it (it only changes whether agent
    dirs get symlinks or copies), so the flag is dropped to keep the resolved
    hash and the real install describing the same command.
    """
    return [
        "npx", "--yes", SKILLS_CLI_PKG, "add",
        skill_source_from_id(skill_id),
        "--skill", skill_name_from_id(skill_id),
        "--yes",
    ]


# The placeholder line the template ships in its `context:` block. Its presence
# marks an un-customized config. Shared by _config_is_real (config-baseline) and
# _context_is_customized (config-interview) so the two predicates never drift on
# what "the placeholder" is. If the template's placeholder wording changes, this
# single constant must change with it.
CONFIG_CONTEXT_SENTINEL = "describe what this project does in 1-3 sentences"


def _config_yaml_text(project_root: Path) -> Optional[str]:
    """Contents of openspec/config.yaml, or None when absent."""
    cfg = project_root / "openspec" / "config.yaml"
    if not cfg.is_file():
        return None
    return cfg.read_text(encoding="utf-8")


def _config_is_real(project_root: Path, text: Optional[str] = None) -> bool:
    """True when openspec/config.yaml has a real (uncommented) context block.

    Baseline is satisfied by the shipped template even while it still carries the
    `CONFIG_CONTEXT_SENTINEL` placeholder — baseline only rejects the fully
    commented-out empty template. Customization is config-interview's concern
    (see _context_is_customized), which keys off the same sentinel.

    `text` lets a caller pass config.yaml's contents that it already read, so a
    single status pass need not re-read the file for each config predicate.
    """
    if text is None:
        text = _config_yaml_text(project_root)
    if text is None:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        # An uncommented top-level `context:` key means real content.
        if stripped.startswith("context:") and not stripped.startswith("#"):
            return True
    return False


def _context_is_customized(project_root: Path, text: Optional[str] = None) -> bool:
    """True when the `context:` block no longer carries the template placeholder.

    config-interview has no tracked source hash, so this predicate is its whole
    drift model: OK once CONFIG_CONTEXT_SENTINEL is gone from the *context block*,
    MISSING while it survives there. The sentinel is matched only inside the
    block, so the phrase quoted elsewhere in the file (a rule, a comment) neither
    masks a real fill nor blocks one. `text` shares a caller's read (see
    _config_is_real).
    """
    if text is None:
        text = _config_yaml_text(project_root)
    if text is None:
        return False
    block = _context_block_text(text)
    # Unlocatable block (absent, malformed, or ambiguous): classify MISSING, not
    # customized. A whole-file scan here would report OK for a file whose context
    # block was deleted (the sentinel is then absent everywhere), yet the
    # interview can't rewrite an absent block, so status would be stuck at a false
    # OK. MISSING is the safe under-claim: install re-offers the interview.
    if block is None:
        return False
    return CONFIG_CONTEXT_SENTINEL not in block


# The interview fields, in prompt order. Each is (prompt label, answer key).
CONFIG_INTERVIEW_FIELDS = [
    ("Purpose (what this project does, 1-3 sentences)", "purpose"),
    ("Language / runtime", "language"),
    ("Frameworks / libraries", "frameworks"),
    ("Data store", "data_store"),
    ("Testing", "testing"),
]

# Convention lines carried over verbatim from the template so the interview
# keeps baseline's project conventions rather than dropping them.
_CONFIG_DEFAULT_CONVENTIONS = [
    "Validate inputs at boundaries; wrap I/O in error handling and log before",
    "  re-throwing.",
    "Keep shared domain rules in one module; do not duplicate them.",
    "Use conventional commit messages.",
]

# Matches a `context:` block-scalar key: the `|` literal indicator with optional
# chomping (`+`/`-`) and explicit-indent digit (`|2`), plus an optional trailing
# comment. Body re-indentation stays two spaces past the key regardless of an
# explicit indicator, which the block-boundary scan below tolerates.
_CONTEXT_BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t]*)context:[ \t]*\|[+-]?\d*[ \t]*(#.*)?$"
)


def _locate_context_block(text: str):
    """Locate the single `context: |` block scalar in config.yaml text.

    Returns (lines, start, end, key_indent) where `lines` are the keepends-split
    source lines, `start` is the key's line index, `end` is the index one past
    the block body (the next sibling key/comment), and `key_indent` is the key's
    leading-space count. Returns None when the block cannot be located
    unambiguously (zero or multiple `context: |` keys), so callers can treat a
    malformed file as unlocatable rather than corrupt it.
    """
    lines = text.splitlines(keepends=True)
    starts = [i for i, ln in enumerate(lines) if _CONTEXT_BLOCK_RE.match(ln.rstrip("\n"))]
    if len(starts) != 1:
        return None
    start = starts[0]
    key_indent = len(_CONTEXT_BLOCK_RE.match(lines[start].rstrip("\n")).group("indent"))

    # Body spans from the line after the key to the first non-blank line whose
    # indentation is <= the key's (the next sibling key/comment ends the block).
    end = start + 1
    while end < len(lines):
        raw = lines[end].rstrip("\n")
        if raw.strip() == "":
            end += 1
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent <= key_indent:
            break
        end += 1
    return lines, start, end, key_indent


def _context_block_text(text: str) -> Optional[str]:
    """The raw body lines of the `context: |` block, or None if unlocatable."""
    located = _locate_context_block(text)
    if located is None:
        return None
    lines, start, end, _ = located
    return "".join(lines[start + 1 : end])


def _render_context_body(answers: dict) -> list[str]:
    """The unindented lines of a filled `context:` block from interview answers.

    Answer values are flattened to a single line: any embedded newline (a pasted
    multi-line answer, or a non-input() reader) is collapsed to a space so it
    cannot break the block scalar's uniform indentation and corrupt the YAML.
    """
    def one_line(value: str) -> str:
        return " ".join(value.strip().split())

    lines = [
        f"Purpose: {one_line(answers.get('purpose', ''))}",
        "",
        "Tech stack:",
        f"- Language / runtime: {one_line(answers.get('language', ''))}",
        f"- Frameworks / libraries: {one_line(answers.get('frameworks', ''))}",
        f"- Data store: {one_line(answers.get('data_store', ''))}",
        f"- Testing: {one_line(answers.get('testing', ''))}",
        "",
        "Conventions:",
    ]
    for conv in _CONFIG_DEFAULT_CONVENTIONS:
        lines.append(conv if conv.startswith(" ") else f"- {conv}")
    return lines


def _rewrite_context_block(text: str, body: list[str]) -> str:
    """Replace only the `context: |` block body, preserving everything else.

    Replaces the located block span with `body` re-indented two spaces past the
    key. Raises ValueError if the block cannot be located unambiguously, so a
    malformed file is left untouched rather than corrupted.
    """
    located = _locate_context_block(text)
    if located is None:
        raise ValueError(
            "could not locate a single `context: |` block; "
            "leaving openspec/config.yaml untouched"
        )
    lines, start, end, key_indent = located

    pad = " " * (key_indent + 2)
    newline = "\n"
    rendered = [
        (pad + line + newline) if line else newline for line in body
    ]
    return "".join(lines[: start + 1] + rendered + lines[end:])


def _config_interview_filler(project_root: Path, reader=input, out=sys.stdout) -> None:
    """Prompt for project context and rewrite openspec/config.yaml's block.

    Reads answers through the injectable `reader` (same seam as the picker), so
    it is deterministic and unit-testable. On a locate failure the file is left
    untouched and a message is printed.

    Guards two ways: a blank in any field aborts without writing (a partial fill
    would erase the sentinel and falsely classify the component customized while
    leaving fields empty), and re-running over an already-customized block
    confirms before overwriting so a hand-edited context (extra conventions,
    tweaked tech stack) is not silently discarded.
    """
    text = _config_yaml_text(project_root)
    if text is None:
        print("  openspec/config.yaml not found; run config-baseline first.", file=out)
        return

    # Re-interview over an already-filled block would replace the whole body,
    # dropping any hand edits. Confirm first when the block is already customized.
    if _context_is_customized(project_root, text):
        print("  context block already customized; the interview replaces it "
              "entirely (hand edits will be lost).", file=out)
        if _prompt("  overwrite? [y]es, [n]o: ", ["y", "n"], reader) == "n":
            print("  left unchanged.", file=out)
            return

    answers = {key: reader(f"  {label}: ") for label, key in CONFIG_INTERVIEW_FIELDS}
    # Every field is required. A blank in any one clears the sentinel and would
    # falsely classify the component customized while leaving that field empty, so
    # abort without writing rather than persist a half-filled block.
    blank = [label for label, key in CONFIG_INTERVIEW_FIELDS
             if not answers.get(key, "").strip()]
    if blank:
        joined = ", ".join(blank)
        print(f"  every field is required; blank: {joined}. Nothing written.", file=out)
        return
    body = _render_context_body(answers)
    try:
        new_text = _rewrite_context_block(text, body)
    except ValueError as e:
        print(f"  {e}", file=out)
        return
    (project_root / "openspec" / "config.yaml").write_text(new_text, encoding="utf-8")
    print("  context block filled.", file=out)


# --------------------------------------------------------------------------- #
# Artifact generation (manifest.yaml -> plugins.json + skills-lock.json)
# --------------------------------------------------------------------------- #
def generate_plugins_json(manifest: dict) -> dict:
    """manifest -> the { "plugins": [ { id, marketplace, marketplaceSource } ] }
    shape that plugins.json consumers (compose_wishlist, classify_plugins) read."""
    plugins = []
    for p in manifest["plugins"]:
        pid = p["id"]
        src = p["source"]
        # marketplace is the segment after '@' in the id; existing consumers
        # only key on id/marketplaceSource, but the field is preserved for
        # continuity with the prior hand-authored file.
        marketplace = pid.split("@", 1)[1] if "@" in pid else src
        plugins.append(
            {
                "id": pid,
                "marketplace": marketplace,
                "marketplaceSource": src,
            }
        )
    return {"plugins": plugins}


def resolve_skill_lock_entry(skill_id: str) -> dict:
    """Resolve a skill's lock entry (skillPath + computedHash) from its source.

    `skillPath` and `computedHash` depend on the real upstream repo layout and
    content (e.g. grill-me lives at skills/productivity/grill-me/SKILL.md), so
    they cannot be derived from the manifest string. This shells out to the
    `npx skills` CLI to install the skill into a throwaway project and reads
    back the lock entry it wrote. Raises RuntimeError if the CLI is unavailable
    or the skill does not resolve.
    """
    if not skills_cli_available():
        raise RuntimeError("npx skills CLI unavailable; cannot resolve skill hashes")
    name = skill_name_from_id(skill_id)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            skills_add_argv(skill_id),
            cwd=tmp,
            check=False,
            capture_output=True,
            text=True,
        )
        lock_path = Path(tmp) / "skills-lock.json"
        if not lock_path.is_file():
            raise RuntimeError(f"skill {skill_id!r} did not resolve (no lock written)")
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        entry = lock.get("skills", {}).get(name)
        if entry is None:
            raise RuntimeError(f"skill {skill_id!r} did not resolve (absent from lock)")
        return entry


def generate_skills_lock(manifest: dict, resolver=resolve_skill_lock_entry) -> dict:
    """manifest -> skills-lock.json.

    `resolver(skill_id) -> entry` supplies the CLI-derived skillPath/computedHash
    (injectable for tests). Entries are keyed by skill name and sorted, matching
    the CLI's on-disk format.
    """
    skills: dict[str, dict] = {}
    for skill_id in manifest["skills"]:
        name = skill_name_from_id(skill_id)
        entry = resolver(skill_id)
        skills[name] = {
            "source": entry.get("source", skill_source_from_id(skill_id)),
            "sourceType": entry.get("sourceType", "github"),
            "skillPath": entry["skillPath"],
            "computedHash": entry["computedHash"],
        }
    return {"version": 1, "skills": dict(sorted(skills.items()))}


def _json_text(data: dict) -> str:
    return json.dumps(data, indent=2) + "\n"


# --------------------------------------------------------------------------- #
# Drift guard (committed artifacts vs manifest)
# --------------------------------------------------------------------------- #
def _plugins_projection(plugins_json: dict) -> list[dict]:
    """The manifest-derivable slice of plugins.json (order-preserving)."""
    return [
        {
            "id": p.get("id"),
            "marketplace": p.get("marketplace"),
            "marketplaceSource": p.get("marketplaceSource"),
        }
        for p in plugins_json.get("plugins", [])
    ]


def _skills_projection(lock: dict) -> dict:
    """The manifest-derivable slice of skills-lock.json: name -> source.

    skillPath/computedHash depend on upstream repo content and are not derivable
    from the manifest alone, so the drift guard compares only what the manifest
    determines: the set of skill names and their source repo."""
    return {name: e.get("source") for name, e in lock.get("skills", {}).items()}


def check_drift(manifest_path: Path = BASE_MANIFEST) -> list[str]:
    """Return a list of drift messages (empty when artifacts are in sync).

    plugins.json is compared in full (fully manifest-derivable). skills-lock.json
    is compared on its manifest-derivable projection (name -> source), since
    hashes require the upstream repo and would false-positive on a pure re-read.
    """
    manifest = read_manifest_file(manifest_path)
    problems: list[str] = []

    want_plugins = generate_plugins_json(manifest)
    have_plugins = (
        json.loads(BASE_PLUGINS.read_text(encoding="utf-8"))
        if BASE_PLUGINS.is_file()
        else {}
    )
    if want_plugins != have_plugins:
        problems.append(
            "scaffold_base/plugins.json is out of sync with manifest.yaml "
            "(run `python3 scaffold.py gen`)"
        )

    want_skill_names = {skill_name_from_id(s): skill_source_from_id(s)
                        for s in manifest["skills"]}
    have_lock = (
        json.loads(BASE_SKILLS_LOCK.read_text(encoding="utf-8"))
        if BASE_SKILLS_LOCK.is_file()
        else {}
    )
    if want_skill_names != _skills_projection(have_lock):
        problems.append(
            "scaffold_base/skills-lock.json is out of sync with manifest.yaml "
            "(run `python3 scaffold.py gen`)"
        )

    # skillPath/computedHash can't be derived from the manifest, so the
    # name->source check above can't tell whether a pin is actually valid.
    # A bad `gen` run (CLI hiccup, empty resolver output) can still write blank
    # pins that silently pass the sync check. Catch that manifest-independent
    # corruption here so a broken lock never reads as "in sync".
    for name in want_skill_names:
        entry = have_lock.get("skills", {}).get(name)
        if entry and (not entry.get("skillPath") or not entry.get("computedHash")):
            problems.append(
                f"scaffold_base/skills-lock.json: skill {name!r} has an empty "
                f"skillPath/computedHash pin (re-run `python3 scaffold.py gen`)"
            )

    return problems


def cmd_gen(out=sys.stdout) -> int:
    """Regenerate committed artifacts from manifest.yaml."""
    manifest = read_manifest_file()
    BASE_PLUGINS.write_text(_json_text(generate_plugins_json(manifest)), encoding="utf-8")
    print(f"wrote {BASE_PLUGINS}", file=out)
    try:
        lock = generate_skills_lock(manifest)
    except RuntimeError as e:
        print(f"! skills-lock.json not regenerated: {e}", file=out)
        print("  (kept existing committed lock)", file=out)
        return 0
    BASE_SKILLS_LOCK.write_text(_json_text(lock), encoding="utf-8")
    print(f"wrote {BASE_SKILLS_LOCK}", file=out)
    return 0


def _plugin_components() -> list[PluginComponent]:
    """PluginComponents built from scaffold_base/plugins.json (no hardcoding).

    Each entry needs id/marketplaceSource; version and description are optional
    and default to 1 and a synthesized label.
    """
    components: list[PluginComponent] = []
    for i, p in enumerate(load_base_wishlist()):
        pid = p.get("id")
        src = p.get("marketplaceSource")
        missing = [k for k, v in (("id", pid), ("marketplaceSource", src)) if not v]
        if missing:
            label = f"'{pid}'" if pid else f"entry #{i}"
            raise SystemExit(
                f"scaffold_base/plugins.json: plugin {label} is missing "
                f"required field(s): {', '.join(missing)}"
            )
        components.append(
            PluginComponent(
                id=pid,
                version=p.get("version", 1),
                description=p.get("description", f"{pid.split('@')[0]} plugin"),
                marketplace_source=src,
            )
        )
    return components


def _skill_components() -> list[SkillComponent]:
    """SkillComponents built from the effective skill wishlist (manifest + none).

    Mirrors _plugin_components. The base wishlist is manifest.yaml's `skills:`;
    per-project composition happens in compose_skill_wishlist at status time.
    """
    components: list[SkillComponent] = []
    for skill_id in load_base_skill_wishlist():
        name = skill_name_from_id(skill_id)
        components.append(
            SkillComponent(
                id=skill_id,
                version=1,
                description=f"{name} skill ({skill_source_from_id(skill_id)})",
                source=skill_source_from_id(skill_id),
                name=name,
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
            needs_openspec=True,
        ),
        FileComponent(
            id="config-interview",
            version=1,
            description="Guided fill of openspec/config.yaml's context block (MISSING until customized)",
            # No tracked files: the interview rewrites config.yaml in place.
            files=[],
            satisfied=_context_is_customized,
            filler=_config_interview_filler,
            needs_openspec=True,
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
            needs_openspec=True,
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
            # The tracker resolves per-session cost via the `ccusage` CLI, which
            # is provisioned globally with `pnpm`. Absent `pnpm` the tracker can
            # only log ERROR, so gate the component on `pnpm` being on PATH.
            precondition=Precondition(
                check=pnpm_available,
                remedy="`pnpm` is not on PATH. Install Node and pnpm "
                       "(https://pnpm.io/installation), then re-run install; "
                       "the scaffold provisions ccusage via `pnpm add -g ccusage`.",
            ),
            post_install=provision_ccusage,
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
        FileComponent(
            id="github-init",
            version=1,
            description="Nag to create a GitHub origin remote (print-only, needs_git)",
            # No tracked files: the component only prints advisory commands.
            files=[],
            # OK once an origin remote exists (any host); MISSING otherwise.
            satisfied=has_origin_remote,
            printer=print_github_init,
            needs_git=True,
        ),
        *_plugin_components(),
        *_skill_components(),
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
# Git repository / remote probes (github-init gate)
# --------------------------------------------------------------------------- #
def is_git_repo(project_root: Path) -> bool:
    """True when the project root is inside a git work tree.

    The `needs_git` gate for github-init: absent a work tree there is no place
    for a remote to live, so the component is BLOCKED. Shells out to
    `git rev-parse --is-inside-work-tree`; a missing git binary or a non-repo
    dir both fail closed to False so the gate blocks rather than nagging.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", str(project_root), "rev-parse", "--is-inside-work-tree"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False
    return out == "true"


def has_origin_remote(project_root: Path, _text: Optional[str] = None) -> bool:
    """True when the project root has an `origin` remote (on any host).

    The cheapest signal that a push target exists (`git remote get-url origin`).
    Any host counts — we only care that a remote is configured, not that it is
    github.com. The `_text` parameter matches the satisfied() predicate seam
    (project_root, text) and is ignored. Absent git / no origin → False.
    """
    try:
        out = subprocess.check_output(
            ["git", "-C", str(project_root), "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False
    return bool(out)


# --------------------------------------------------------------------------- #
# OpenSpec initialization probe
# --------------------------------------------------------------------------- #
def openspec_initialized(project_root: Path) -> bool:
    """True only when `openspec init` has really run at `project_root`.

    The scaffold's OpenSpec-dependent components (config-baseline,
    config-interview, schema-clone) write inside `openspec/`. Installing them
    on a repo that never ran `openspec init` fabricates a partial tree.

    The discriminator is the on-disk `openspec/changes/` directory, which
    `openspec init` always creates and the CLI itself keys detection on ("No
    OpenSpec changes directory found. Run 'openspec init' first."). We check
    disk directly rather than shelling out to `openspec list --json` because
    that command's `root` reporting is unreliable across CLI versions:

    - v1.4.x errors (exit 1) on an uninitialized dir.
    - v1.8.x reports `root: {path: <cwd>, source: "implicit"}` (exit 0) for ANY
      directory, even an empty one with no `openspec/` at all.

    So a version-skewed machine (multiple `openspec` binaries on PATH) would
    pass the gate on an uninitialized repo. The scaffold's own
    `config-baseline` writes `openspec/config.yaml` but NOT `changes/`, so
    keying on `config.yaml` would also self-satisfy after a partial run. The
    `changes/` directory is the only marker that means a real init happened.

    Fails closed — absent `openspec/` or absent `openspec/changes/` returns
    False so the gate blocks rather than fabricating a tree.
    """
    return (project_root / "openspec" / "changes").is_dir()


# --------------------------------------------------------------------------- #
# Drift classification (file components)
# --------------------------------------------------------------------------- #
def unmet_precondition(
    project_root: Path,
    comp: FileComponent,
    openspec_ready: bool = True,
    git_ready: bool = True,
) -> Optional[str]:
    """The remedy string for a component's first unmet precondition, or None.

    Unifies the precondition instances: the root-probe-threaded `needs_openspec`,
    the git-work-tree-probe-threaded `needs_git`, and the general `precondition`
    (predicate + remedy). A non-None result means the component is BLOCKED; the
    string is what install/check/list report so the user sees how to satisfy it.
    """
    if comp.needs_openspec and not openspec_ready:
        return OPENSPEC_REMEDY
    if comp.needs_git and not git_ready:
        return GIT_REMEDY
    if comp.precondition is not None and not comp.precondition.check(project_root):
        return comp.precondition.remedy
    return None


def classify_file_component(
    project_root: Path,
    comp: FileComponent,
    manifest: dict,
    source_sha: Optional[str],
    config_text: Optional[str] = None,
    openspec_ready: bool = True,
    git_ready: bool = True,
) -> str:
    """Classify a file component using disk, manifest, and source SHA.

    `source_sha` is None when the source is unreachable (offline): STALE cannot
    be evaluated, so we never return STALE and never claim OK on that basis.

    `config_text` is openspec/config.yaml's contents pre-read once by the caller
    and forwarded to the satisfied() predicate, so a status pass classifying both
    config-baseline and config-interview reads that file once, not per component.
    Every satisfied() predicate accepts (project_root, text=None); passing None
    (the default) makes it read the file itself.

    `openspec_ready` / `git_ready` are the single `openspec_initialized` /
    `is_git_repo` probe results threaded in by the caller. Any unmet precondition —
    `needs_openspec` when the root is absent, `needs_git` when not a repo, or a
    general `precondition` predicate — classifies BLOCKED, with precedence over
    MISSING/OK/STALE, so install refuses it and check/list report the unmet
    precondition rather than a fabricated tree.
    """
    if unmet_precondition(project_root, comp, openspec_ready, git_ready) is not None:
        return BLOCKED

    # Printer / filler components (github-init, config-interview) have no tracked
    # source hash and write nothing to the manifest: their whole drift model is
    # the satisfied() predicate — OK when satisfied, MISSING otherwise. They never
    # produce STALE/MODIFIED. github-init's satisfied() is has_origin_remote.
    if comp.filler is not None or comp.printer is not None:
        return OK if (comp.satisfied and comp.satisfied(project_root, config_text)) else MISSING

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
    if comp.satisfied is not None and not comp.satisfied(project_root, config_text):
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
# cost-tracker runtime provisioning (ccusage via pnpm)
# --------------------------------------------------------------------------- #
def pnpm_available(_project_root: Path) -> bool:
    """`pnpm` on PATH — the runtime the cost-tracker install step needs."""
    return shutil.which("pnpm") is not None


def provision_ccusage(project_root: Path, out=sys.stdout) -> None:
    """Install the ccusage CLI globally via `pnpm add -g ccusage`.

    The cost-tracker shells out to `ccusage` to resolve per-session cost; without
    it the tracker logs `total_cost_usd = "ERROR"`. This runs as the component's
    post-copy step (only when the `pnpm` precondition is satisfied). A non-zero
    exit or missing binary is surfaced as a warning, not fatal: the tracker still
    degrades to `ERROR`, so a failed provision must not abort the scaffold run.
    """
    try:
        result = subprocess.run(
            ["pnpm", "add", "-g", "ccusage"],
            check=False,
        )
    except (FileNotFoundError, OSError) as exc:
        print(f"  ! ccusage provisioning failed ({exc}); cost-tracker will log "
              "ERROR until `pnpm add -g ccusage` succeeds.", file=out)
        return
    if result.returncode != 0:
        print("  ! `pnpm add -g ccusage` exited non-zero; cost-tracker will log "
              "ERROR until it is installed.", file=out)
        return
    print("  provisioned ccusage via pnpm.", file=out)


# --------------------------------------------------------------------------- #
# github-init print-only installer
# --------------------------------------------------------------------------- #
def print_github_init(project_root: Path, out=sys.stdout) -> None:
    """Print (never run) the commands to create the GitHub repo and push.

    Consistent with the codebase's refusals to auto-run outward, hard-to-reverse
    actions (openspec init, claude plugin install, npx skills add): creating a
    public repo is the most outward of all, so it inherits the same treatment.
    Repo name defaults to the project directory basename (the
    `gh repo create --source=.` convention), so the primary line is copy-paste
    ready. A no-gh fallback is printed for when the CLI is absent. This mutates
    no local git config and no remote GitHub state.
    """
    basename = project_root.name
    print("  No GitHub `origin` remote. Create the repo and push with:", file=out)
    print(
        f"    gh repo create {basename} --public --source=. --remote=origin --push",
        file=out,
    )
    print("  Without the gh CLI: create the repository on github.com, then:", file=out)
    print(f"    git remote add origin git@github.com:<owner>/{basename}.git", file=out)
    print("    git push -u origin main", file=out)


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
# Skill reconciliation (github-sourced skills via the `npx skills` CLI)
# --------------------------------------------------------------------------- #
def load_base_skill_wishlist() -> list[str]:
    """The base `skills:` list from manifest.yaml (empty if absent/malformed)."""
    if not BASE_MANIFEST.is_file():
        return []
    try:
        return read_manifest_file(BASE_MANIFEST)["skills"]
    except SystemExit:
        return []


def compose_skill_wishlist(project_root: Path) -> list[str]:
    """Base skill wishlist composed with a per-project override.

    Mirrors compose_wishlist for plugins. The override is `.scaffold/skills.yaml`
    (a `skills:`-only manifest fragment). Same-name entries replace the base;
    new names extend. Order: base first, then override-only additions.
    """
    by_name: dict[str, str] = {
        skill_name_from_id(s): s for s in load_base_skill_wishlist()
    }
    override = project_root / ".scaffold" / "skills.yaml"
    if override.is_file():
        try:
            entries = parse_manifest(override.read_text(encoding="utf-8"))["skills"]
            for s in entries:
                if SKILL_ID_RE.match(s):
                    by_name[skill_name_from_id(s)] = s
        except (SystemExit, OSError):
            pass
    return list(by_name.values())


def read_skills_lock(project_root: Path) -> dict:
    """The project's skills-lock.json ({"skills": {}} if absent/malformed)."""
    path = project_root / "skills-lock.json"
    if not path.is_file():
        return {"skills": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"skills": {}}
    data.setdefault("skills", {})
    return data


def skills_cli_available() -> bool:
    return shutil.which("npx") is not None


def skill_stale_names(
    desired: list[str],
    lock: dict,
    resolver=resolve_skill_lock_entry,
    out=sys.stderr,
) -> set[str]:
    """Desired skills whose committed lock hash differs from the upstream hash.

    The installed `npx skills` CLI has no non-mutating staleness command
    (`update` only ever writes; there is no `--check`/`--json` mode), so
    staleness is computed directly: re-resolve each desired skill's upstream
    `computedHash` and compare it to the hash recorded in the project's
    skills-lock.json. `resolver(skill_id) -> entry` is injectable for tests and
    matches generate_skills_lock's seam.

    On CLI absence, or any per-skill resolution error, that skill is treated as
    current (never STALE) so staleness never blocks the run — but a resolution
    failure is logged rather than swallowed silently, so an unresolvable skill
    is visible instead of masquerading as "everything current".
    """
    if not skills_cli_available() or not desired:
        return set()
    locked = lock.get("skills", {})
    stale: set[str] = set()
    for skill_id in desired:
        name = skill_name_from_id(skill_id)
        locked_entry = locked.get(name)
        if not locked_entry:  # not installed -> MISSING, not STALE
            continue
        try:
            upstream = resolver(skill_id)
        except (RuntimeError, OSError) as e:
            print(
                f"! skill staleness check for {name!r} skipped "
                f"({type(e).__name__}); treating it as current",
                file=out,
            )
            continue
        if upstream.get("computedHash") != locked_entry.get("computedHash"):
            stale.add(name)
    return stale


def classify_skills(desired: list[str], lock: dict, stale: Optional[set] = None) -> dict:
    """Return {name: status} for desired + EXTRA installed-but-not-desired.

    MISSING  : desired skill absent from the lock.
    STALE    : desired skill present but named in `stale`.
    OK       : desired skill present and current.
    EXTRA    : locked skill not in the desired set (never removed).
    """
    stale = stale or set()
    result: dict[str, str] = {}
    locked = lock.get("skills", {})
    desired_names = {skill_name_from_id(s) for s in desired}
    for s in desired:
        name = skill_name_from_id(s)
        if name not in locked:
            result[name] = MISSING
        elif name in stale:
            result[name] = STALE
        else:
            result[name] = OK
    for name in locked:
        if name not in desired_names:
            result[name] = EXTRA
    return result


def skill_install_commands(skill_id: str) -> list[str]:
    """The exact command to install/update a skill via the skills CLI.

    A copy-pasteable rendering of the same argv install_skill executes.
    """
    return [" ".join(skills_add_argv(skill_id))]


def install_skill(skill_id: str, project_root: Path) -> bool:
    """Shell out to `npx skills add`. Returns True on success, False if CLI absent."""
    if not skills_cli_available():
        return False
    subprocess.run(
        skills_add_argv(skill_id),
        cwd=project_root,
        check=False,
    )
    return True


# --------------------------------------------------------------------------- #
# Status computation shared by list / check / install
# --------------------------------------------------------------------------- #
@dataclass
class Status:
    file_statuses: dict = field(default_factory=dict)
    plugin_statuses: dict = field(default_factory=dict)
    skill_statuses: dict = field(default_factory=dict)
    source_sha: Optional[str] = None
    offline: bool = False
    openspec_ready: bool = True
    git_ready: bool = True


def compute_status(project_root: Path, registry: list, *, fetch: bool = True) -> Status:
    manifest = read_manifest(project_root)
    source = source_config(project_root)
    source_sha = resolve_source_sha(source) if fetch else None
    offline = source_sha is None

    # Probe OpenSpec initialization once; the boolean is threaded into every
    # file-component classification so blocked components do not each re-invoke
    # the CLI. Only meaningful when some component needs a root.
    openspec_ready = (
        openspec_initialized(project_root)
        if any(isinstance(c, FileComponent) and c.needs_openspec for c in registry)
        else True
    )

    # Probe git-work-tree presence once, threaded into every `needs_git`
    # classification, mirroring the openspec probe. Only meaningful when some
    # component needs a repo (github-init).
    git_ready = (
        is_git_repo(project_root)
        if any(isinstance(c, FileComponent) and c.needs_git for c in registry)
        else True
    )

    # Read config.yaml once; the config-baseline and config-interview predicates
    # share this instead of each re-reading the file.
    config_text = _config_yaml_text(project_root)
    file_statuses = {}
    for comp in registry:
        if isinstance(comp, FileComponent):
            file_statuses[comp.id] = classify_file_component(
                project_root, comp, manifest, source_sha, config_text,
                openspec_ready, git_ready,
            )

    desired = compose_wishlist(project_root)
    plugin_statuses = classify_plugins(desired, read_installed_plugins())

    desired_skills = compose_skill_wishlist(project_root)
    lock = read_skills_lock(project_root)
    stale = skill_stale_names(desired_skills, lock) if fetch else set()
    skill_statuses = classify_skills(desired_skills, lock, stale)

    return Status(
        file_statuses=file_statuses,
        plugin_statuses=plugin_statuses,
        skill_statuses=skill_statuses,
        source_sha=source_sha,
        offline=offline,
        openspec_ready=openspec_ready,
        git_ready=git_ready,
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
            if st == BLOCKED:
                remedy = unmet_precondition(project_root, comp, status.openspec_ready, status.git_ready)
                print(f"       {remedy}", file=out)
    for comp in registry:
        if isinstance(comp, PluginComponent):
            st = status.plugin_statuses.get(comp.id, MISSING)
            print(f"  [{st:<14}] {comp.id}  (plugin) — {comp.description}", file=out)
    for pid, st in status.plugin_statuses.items():
        if st == EXTRA:
            print(f"  [{EXTRA:<14}] {pid}  (plugin, not in wishlist)", file=out)
    for comp in registry:
        if isinstance(comp, SkillComponent):
            st = status.skill_statuses.get(comp.name, MISSING)
            print(f"  [{st:<14}] {comp.name}  (skill)  — {comp.description}", file=out)
    desired_skill_names = {
        c.name for c in registry if isinstance(c, SkillComponent)
    }
    for name, st in status.skill_statuses.items():
        if st == EXTRA and name not in desired_skill_names:
            print(f"  [{EXTRA:<14}] {name}  (skill, not in wishlist)", file=out)
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
            st = status.file_statuses[comp.id]
            print(f"  {st:<14} {comp.id}", file=out)
            if st == BLOCKED:
                remedy = unmet_precondition(project_root, comp, status.openspec_ready, status.git_ready)
                print(f"    {remedy}", file=out)
    print("Plugins:", file=out)
    for pid, st in status.plugin_statuses.items():
        print(f"  {st:<14} {pid}", file=out)
    print("Skills:", file=out)
    for name, st in status.skill_statuses.items():
        print(f"  {st:<14} {name}", file=out)
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
        if isinstance(comp, FileComponent) and status.file_statuses[comp.id] == BLOCKED:
            # Precondition unmet: refuse and print the component-specific remedy;
            # write nothing (e.g. do not auto-run `openspec init` — it requires a
            # --tools choice the scaffold should not own).
            remedy = unmet_precondition(project_root, comp, status.openspec_ready, status.git_ready)
            print(f"\n{comp.id} — {BLOCKED}: {comp.description}", file=out)
            print(f"  {remedy}", file=out)
            continue
        if isinstance(comp, FileComponent) and comp.filler is not None:
            # Interview-style component: always offer [i]nterview / [s]kip, even
            # when OK/customized, so the context can be revised on a re-run.
            st = status.file_statuses[comp.id]
            label = "customized" if st == OK else st
            print(f"\n{comp.id} — {label}: {comp.description}", file=out)
            choice = _prompt("  [i]nterview, [s]kip? ", ["i", "s"], reader)
            if choice == "s":
                continue
            comp.filler(project_root, reader, out)
            continue
        if isinstance(comp, FileComponent) and comp.printer is not None:
            # Print-only component (github-init): no prompt, no write, no outward
            # action. On OK report satisfied; on MISSING print the advisory
            # commands. BLOCKED was handled above.
            st = status.file_statuses[comp.id]
            print(f"\n{comp.id} — {st}: {comp.description}", file=out)
            if st == OK:
                print("  satisfied; nothing to do.", file=out)
                continue
            comp.printer(project_root, out)
            continue
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
                if comp.post_install is not None:
                    comp.post_install(project_root, out)
                break
        elif isinstance(comp, PluginComponent):
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
        else:  # SkillComponent
            st = status.skill_statuses.get(comp.name, MISSING)
            print(f"\n{comp.name} — {st}: {comp.description}", file=out)
            if st == OK:
                print("  current; skipping.", file=out)
                continue
            choice = _prompt("  [i]nstall/update, [s]kip? ", ["i", "s"], reader)
            if choice == "s":
                continue
            if not install_skill(comp.id, project_root):
                print("  npx skills CLI not found. Run these commands manually:", file=out)
                for cmd in skill_install_commands(comp.id):
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
        if isinstance(c, FileComponent)
        # interview (filler) and print-only (printer) components have no tracked
        # files to re-copy, so `update` is a no-op for them: install-only.
        and c.filler is None
        and c.printer is None
        and (component is None or c.id == component)
    ]
    if component is not None and not targets:
        # Distinguish a real-but-install-only component (a filler like
        # config-interview, or a printer like github-init) from an unknown id.
        named = next((c for c in registry if getattr(c, "id", None) == component), None)
        if isinstance(named, FileComponent) and named.filler is not None:
            print(
                f"{component}: install-only (guided interview); "
                f"run `install` to (re)fill it.",
                file=out,
            )
            return 0
        if isinstance(named, FileComponent) and named.printer is not None:
            print(
                f"{component}: install-only (print-only advisory); "
                f"run `install` to see the commands.",
                file=out,
            )
            return 0
        print(f"Unknown component: {component}", file=out)
        return 1

    for comp in targets:
        st = status.file_statuses[comp.id]
        if st == BLOCKED:
            remedy = unmet_precondition(project_root, comp, status.openspec_ready, status.git_ready)
            print(f"{comp.id}: {BLOCKED} — {remedy}", file=out)
            continue
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
        if comp.post_install is not None:
            comp.post_install(project_root, out)
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
    sub.add_parser("gen", help="regenerate plugins.json + skills-lock.json from manifest.yaml")
    sub.add_parser("drift", help="fail if committed artifacts drift from manifest.yaml")
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
    if args.command == "gen":
        return cmd_gen()
    if args.command == "drift":
        problems = check_drift()
        for p in problems:
            print(p, file=sys.stderr)
        # The guard verifies names/sources and that pins are non-empty, but it
        # does NOT re-hash upstream skill content — a skill whose upstream files
        # changed still reads as in-sync here. Say so, so a clean drift check is
        # not mistaken for a verified lock.
        print(
            "note: skill content hashes are not re-verified against upstream; "
            "run `python3 scaffold.py gen` to refresh pins",
            file=sys.stderr,
        )
        return 1 if problems else 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
