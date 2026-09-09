"""Print passed/collected for named workflow tests; exit 1 if the rate is under 0.95."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THRESHOLD = 0.95


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True)


def _collected_count(output: str) -> int:
    match = re.search(r"(\d+)/\d+ tests? collected", output)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+) tests? collected", output)
    if match:
        return int(match.group(1))
    if re.search(r"no tests collected", output, re.I):
        return 0
    return 0


def _passed_count(output: str) -> int:
    match = re.search(r"(\d+) passed", output)
    return int(match.group(1)) if match else 0


def main() -> int:
    collect = _run(
        [sys.executable, "-m", "pytest", "-m", "workflow", "--collect-only", "-q"]
    )
    collected = _collected_count(collect.stdout + collect.stderr)
    if collected == 0:
        print("0/0")
        return 1

    run = _run([sys.executable, "-m", "pytest", "-m", "workflow", "-q", "--tb=no"])
    passed = _passed_count(run.stdout + run.stderr)
    print(f"{passed}/{collected}")
    return 0 if passed / collected >= THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(main())
