#!/usr/bin/env python3
"""Mål importtiden for core_logic i isolerede Python-processer."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path


IMPORT_LINE = re.compile(r"import time:\s+\d+\s+\|\s+(\d+)\s+\|\s+core_logic\s*$")


def measure_once() -> int:
    environment = dict(os.environ)
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", "import core_logic"],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or "Import af core_logic fejlede")
    for line in reversed(result.stderr.splitlines()):
        match = IMPORT_LINE.match(line)
        if match:
            return int(match.group(1))
    raise RuntimeError("Python rapporterede ikke en samlet importtid for core_logic")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--write-baseline", type=Path)
    parser.add_argument("--max-factor", type=float)
    args = parser.parse_args()
    samples = [measure_once() for _ in range(max(1, args.samples))]
    median = int(statistics.median(samples))
    result = {
        "captured": date.today().isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "samples_microseconds": samples,
        "cumulative_microseconds": median,
        "enforced": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.write_baseline:
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Baseline gemt: {args.write_baseline}")
    if args.baseline and args.baseline.exists():
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        reference = int(baseline.get("cumulative_microseconds", 0) or 0)
        if reference:
            factor = median / reference
            print(f"Forhold til reference: {factor:.2f}×")
            if args.max_factor is not None and factor > args.max_factor:
                print(f"Importtiden overstiger den tilladte faktor {args.max_factor:.2f}×", file=sys.stderr)
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
