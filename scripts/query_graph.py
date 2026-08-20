#!/usr/bin/env python3
"""Inspect article neighborhood in the Neo4j legal graph."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services"), str(ROOT / "packages" / "legal-schema" / "src")]

from graph.neo4j_client import create_neo4j_driver
from graph.projector import neighborhood
from hakim_legal_schema.ids import article_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--law-no", default="5237")
    parser.add_argument("--article-no", required=True)
    args = parser.parse_args()

    node_id = article_id(args.law_no, args.article_no)
    driver = create_neo4j_driver()
    try:
        data = neighborhood(driver, node_id)
    finally:
        driver.close()
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
