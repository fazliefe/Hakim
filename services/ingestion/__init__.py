"""Ingestion workers: raw archive → parser → PostgreSQL."""

from ingestion.mevzuat_pipeline import ingest_mevzuat_law
from ingestion.postgres_writer import write_parsed_law

__all__ = ["ingest_mevzuat_law", "write_parsed_law"]
