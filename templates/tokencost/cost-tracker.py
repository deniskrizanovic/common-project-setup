#!/usr/bin/env python3
"""Per-project Claude Code token cost tracker.

Modes:
  finalize          - SessionEnd hook: write/upsert row for the ending session.
  backfill          - SessionStart hook: spawn detached worker and return
                      immediately so Claude Code startup is not blocked.
  backfill-worker   - Internal: actual backfill work, logs failures to
                      <CLAUDE_PROJECT_DIR>/tokencost/backfill.log.

CSV: <CLAUDE_PROJECT_DIR>/tokencost/cost.csv
"""
from __future__ import annotations

import csv
import datetime
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

LOCK_TIMEOUT_SEC = 10
LOCK_RETRY_SLEEP = 0.2

CSV_HEADER = [
    "session_id",
    "started_at",
    "ended_at",
    "end_reason",
    "total_cost_usd",
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "total_tokens",
    "models",
    "git_branch",
]


def project_root() -> Path | None:
    p = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(p) if p else None


def csv_path(root: Path) -> Path:
    return root / "tokencost" / "cost.csv"


def transcripts_dir_for(root: Path) -> Path:
    encoded = str(root).replace("/", "-")
    return Path.home() / ".claude" / "projects" / encoded


def parse_jsonl(path: Path) -> dict:
    """Walk JSONL, return aggregated session info."""
    info = {
        "session_id": None,
        "started_at": "",
        "ended_at": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "models": set(),
        "git_branch": "",
    }
    try:
        with open(path) as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if info["session_id"] is None:
                    info["session_id"] = d.get("sessionId")
                ts = d.get("timestamp")
                if ts:
                    if not info["started_at"]:
                        info["started_at"] = ts
                    info["ended_at"] = ts
                if not info["git_branch"]:
                    gb = d.get("gitBranch")
                    if gb:
                        info["git_branch"] = gb
                if d.get("type") == "assistant":
                    msg = d.get("message") or {}
                    model = msg.get("model")
                    if model:
                        info["models"].add(model)
                    usage = msg.get("usage") or {}
                    info["input_tokens"] += usage.get("input_tokens") or 0
                    info["output_tokens"] += usage.get("output_tokens") or 0
                    info["cache_creation_tokens"] += (
                        usage.get("cache_creation_input_tokens") or 0
                    )
                    info["cache_read_tokens"] += (
                        usage.get("cache_read_input_tokens") or 0
                    )
    except FileNotFoundError:
        pass
    return info


def ccusage_all_costs() -> dict[str, float]:
    """Run ccusage once; return {session_id: totalCost}. Empty dict on failure."""
    if not shutil.which("ccusage"):
        return {}
    try:
        proc = subprocess.run(
            ["ccusage", "session", "--json", "--offline"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return {}
        data = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return {}
    out: dict[str, float] = {}
    for s in data.get("session") or []:
        sid = s.get("period")
        cost = s.get("totalCost")
        if sid and cost is not None:
            out[sid] = float(cost)
    return out


def build_row(
    jsonl_path: Path,
    end_reason: str,
    costs: dict[str, float] | None = None,
) -> list | None:
    """Build CSV row for one session. Returns None if no session_id found.

    `costs` is an optional pre-fetched {sid: cost} map (batch mode). If omitted,
    falls back to one ccusage call for this session only.
    """
    info = parse_jsonl(jsonl_path)
    if not info["session_id"]:
        return None

    cost = "ERROR"
    if costs is None:
        costs = ccusage_all_costs()
    cost_val = costs.get(info["session_id"])
    if cost_val is not None:
        cost = f"{float(cost_val):.6f}"

    total_tokens = (
        info["input_tokens"]
        + info["output_tokens"]
        + info["cache_creation_tokens"]
        + info["cache_read_tokens"]
    )
    return [
        info["session_id"],
        info["started_at"],
        info["ended_at"],
        end_reason,
        cost,
        info["input_tokens"],
        info["output_tokens"],
        info["cache_creation_tokens"],
        info["cache_read_tokens"],
        total_tokens,
        ",".join(sorted(info["models"])),
        info["git_branch"],
    ]


def upsert_row(path: Path, row: list) -> None:
    """Upsert row by session_id under flock. Creates file + header if missing.

    Uses non-blocking flock with bounded retry so a stuck holder (e.g. editor
    with the file open) cannot pile up indefinite worker processes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    with open(path, "r+", newline="") as fh:
        deadline = time.monotonic() + LOCK_TIMEOUT_SEC
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"could not acquire flock on {path} within "
                        f"{LOCK_TIMEOUT_SEC}s"
                    )
                time.sleep(LOCK_RETRY_SLEEP)
        try:
            content = fh.read()
            rows: list[list[str]] = []
            if content:
                reader = csv.reader(content.splitlines())
                rows = list(reader)
            if not rows or rows[0] != CSV_HEADER:
                rows = [CSV_HEADER]
            sid = row[0]
            replaced = False
            for i in range(1, len(rows)):
                if rows[i] and rows[i][0] == sid:
                    rows[i] = [str(x) for x in row]
                    replaced = True
                    break
            if not replaced:
                rows.append([str(x) for x in row])
            fh.seek(0)
            fh.truncate()
            writer = csv.writer(fh)
            writer.writerows(rows)
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def existing_session_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    with open(path, newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header != CSV_HEADER:
            return set()
        for r in reader:
            if r:
                ids.add(r[0])
    return ids


def read_stdin_payload() -> dict:
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def finalize() -> None:
    payload = read_stdin_payload()
    root = project_root()
    if not root:
        return
    session_id = payload.get("session_id")
    transcript = payload.get("transcript_path")
    if not session_id:
        return
    jsonl = Path(transcript) if transcript else (
        transcripts_dir_for(root) / f"{session_id}.jsonl"
    )
    end_reason = payload.get("reason") or "other"
    row = build_row(jsonl, end_reason)
    if row is None:
        return
    upsert_row(csv_path(root), row)


def log_path(root: Path) -> Path:
    return root / "tokencost" / "backfill.log"


def log_error(root: Path, msg: str) -> None:
    try:
        path = log_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(path, "a") as fh:
            fh.write(f"[{ts}] {msg}\n")
    except OSError:
        pass


def backfill() -> None:
    """SessionStart hook: spawn detached worker, return immediately."""
    root = project_root()
    if not root:
        return
    payload_raw = ""
    try:
        payload_raw = sys.stdin.read()
    except OSError:
        pass
    try:
        log_dir = root / "tokencost"
        log_dir.mkdir(parents=True, exist_ok=True)
        devnull = open(os.devnull, "rb")
        out = open(log_dir / "backfill.log", "ab")
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "backfill-worker"],
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=out,
            start_new_session=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)},
        )
        if proc.stdin:
            try:
                proc.stdin.write(payload_raw.encode())
            finally:
                proc.stdin.close()
        devnull.close()
    except OSError as e:
        log_error(root, f"backfill spawn failed: {e}")


def backfill_worker() -> None:
    """Detached worker: do the actual backfill; log any failure."""
    root = project_root()
    if not root:
        return
    try:
        payload = read_stdin_payload()
        starting_id = payload.get("session_id")
        tdir = transcripts_dir_for(root)
        if not tdir.is_dir():
            return
        csv_file = csv_path(root)
        seen = existing_session_ids(csv_file)
        pending = [
            j for j in tdir.glob("*.jsonl")
            if j.stem != starting_id and j.stem not in seen
        ]
        if not pending:
            return
        costs = ccusage_all_costs()
        for jsonl in pending:
            try:
                row = build_row(jsonl, "backfill", costs=costs)
                if row is None:
                    continue
                upsert_row(csv_file, row)
            except Exception as e:
                log_error(root, f"backfill row {jsonl.name} failed: {e}")
    except Exception:
        log_error(root, "backfill-worker crashed:\n" + traceback.format_exc())


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if mode == "finalize":
            finalize()
        elif mode == "backfill":
            backfill()
        elif mode == "backfill-worker":
            backfill_worker()
    except Exception as e:
        root = project_root()
        if root:
            log_error(root, f"{mode} top-level failed: {e}\n{traceback.format_exc()}")
        print(f"cost-tracker {mode} failed: {e}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
