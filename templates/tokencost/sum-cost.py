#!/usr/bin/env python3
import csv
import os
import subprocess
from collections import defaultdict
from pathlib import Path

# Resolve project root via git, falling back to CLAUDE_PROJECT_DIR or CWD
try:
    repo_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    )
except subprocess.CalledProcessError:
    repo_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))

csv_path = repo_root / "tokencost" / "cost.csv"

if not csv_path.is_file():
    print(f"no cost data yet: {csv_path} not found")
    raise SystemExit(0)

total = 0.0
by_branch = defaultdict(lambda: {"cost": 0.0, "sessions": 0})

with csv_path.open() as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            cost = float(row["total_cost_usd"])
        except ValueError:
            continue
        branch = row["git_branch"] or "(none)"
        total += cost
        by_branch[branch]["cost"] += cost
        by_branch[branch]["sessions"] += 1

rows = sorted(by_branch.items(), key=lambda kv: kv[1]["cost"], reverse=True)
if not rows:
    print("no cost data yet: cost.csv has no rows")
    raise SystemExit(0)
branch_w = max(len("branch"), max(len(b) for b, _ in rows))

print(f"{'branch':<{branch_w}}  {'sessions':>8}  {'cost':>10}")
print(f"{'-' * branch_w}  {'-' * 8}  {'-' * 10}")
for branch, stats in rows:
    print(f"{branch:<{branch_w}}  {stats['sessions']:>8}  ${stats['cost']:>9.2f}")
print(f"{'-' * branch_w}  {'-' * 8}  {'-' * 10}")
print(f"{'TOTAL':<{branch_w}}  {sum(s['sessions'] for s in by_branch.values()):>8}  ${total:>9.2f}")
