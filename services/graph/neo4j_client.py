from __future__ import annotations

import os
from typing import Any

from neo4j import GraphDatabase

DEFAULT_NEO4J_URI = os.environ.get("HAKIM_NEO4J_URI", "bolt://127.0.0.1:7687")
DEFAULT_NEO4J_USER = os.environ.get("HAKIM_NEO4J_USER", "neo4j")
DEFAULT_NEO4J_PASSWORD = os.environ.get("HAKIM_NEO4J_PASSWORD", "hakim-graph")


def create_neo4j_driver(
    uri: str = DEFAULT_NEO4J_URI,
    user: str = DEFAULT_NEO4J_USER,
    password: str = DEFAULT_NEO4J_PASSWORD,
) -> Any:
    return GraphDatabase.driver(uri, auth=(user, password))


CONSTRAINTS = [
    "CREATE CONSTRAINT law_id IF NOT EXISTS FOR (n:Law) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (n:Decision) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT court_id IF NOT EXISTS FOR (n:Court) REQUIRE n.id IS UNIQUE",
]


def ensure_schema(driver: Any) -> None:
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)
