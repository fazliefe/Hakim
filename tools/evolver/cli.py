"""HÂKİM evolver sidecar CLI. @evomap/evolver apps/api içine girmez."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hakim_evolver.score import score_and_record


def main() -> int:
    parser = argparse.ArgumentParser(description="HÂKİM dilekçe taslağını puanla (sidecar).")
    parser.add_argument("--belge", default="", help="temyiz, istinaf, sikayet, …")
    parser.add_argument("--text-file", type=Path, help="Taslak dosyası; yoksa stdin")
    args = parser.parse_args()
    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    report = score_and_record(text, belge_id=args.belge)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
