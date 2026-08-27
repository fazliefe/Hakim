"""Paylaşılan retry yardımcısı: urllib tabanlı LLM/embedding çağrıları için.

Evren/Groq (services/llm/api_client.py) ve emsal karar embedder'ı
(services/retrieval/embeddings.py) aynı urllib.request.urlopen deseniyle
HTTP çağrısı yapıyor; ikisi de tek noktadan (Evren'in H200 uç noktası)
geçici bir 5xx/timeout ile karşılaşabilir. Bu modül o retry mantığını
tek yerde tutar.
"""

from __future__ import annotations

import logging
import time
import urllib.error
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 429 (rate limit) ve 5xx (sunucu tarafı, geçici) tekrar denenir. 4xx'in
# geri kalanı (400 bozuk istek, 401 yanlış API key, 404 vb.) istemci
# hatasıdır — beklemek/tekrar denemek sorunu çözmez, hemen pes edilir.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def call_with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
    label: str = "http",
) -> T:
    """`fn`'i çağırır; 5xx/429/bağlantı hatasında üstel geri çekilmeyle
    (0.5s, 1s, 2s, ...) toplam `attempts` kez dener. Retry edilemeyen bir
    hata (4xx) veya son deneme de başarısız olursa orijinal exception'ı
    olduğu gibi fırlatır — çağıran taraf bugünkü hata mesajlarını (ör.
    `exc.code`, `exc.read()`) değişmeden kullanmaya devam edebilir.
    """
    for attempt in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_STATUS or attempt == attempts - 1:
                raise
        except urllib.error.URLError as exc:
            if attempt == attempts - 1:
                raise
        delay = min(max_delay, base_delay * (2**attempt))
        logger.warning(
            "%s isteği başarısız (deneme %d/%d), %.1fs sonra yeniden denenecek",
            label,
            attempt + 1,
            attempts,
            delay,
        )
        time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
