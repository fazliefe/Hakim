"""Bootstrap sys.path so `uv run python eval/run_bench.py` works without PYTHONPATH."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in ("eval", "services"):
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from hakim_bench.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
