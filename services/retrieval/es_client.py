from __future__ import annotations

import os
from typing import Any

from elasticsearch import Elasticsearch

DEFAULT_ES_URL = os.environ.get("HAKIM_ELASTICSEARCH_URL", "http://127.0.0.1:9200")


def create_es_client(url: str = DEFAULT_ES_URL) -> Elasticsearch:
    return Elasticsearch(url, request_timeout=60)
