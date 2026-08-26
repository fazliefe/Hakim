from __future__ import annotations

import math
from functools import lru_cache

from hakim_config import get_models
from retrieval.embeddings import Embedder, create_embedder

# Kural motorunun (bkz. classify.py::_TYPE_RULES) hiçbir needle'a çarpmadığı
# ("belirsiz") azınlık vakalarda devreye giren İKİNCİL, embedding-tabanlı bir
# öneri katmanı — kural motorunun YERİNE değil YANINA. Kural motoru
# deterministik/denetlenebilir kalmaya devam ediyor; bu yalnızca "hiçbir
# kural tutmadı" durumunda bir tahmin sunuyor. Her kategori için birkaç
# kısa, temsilî örnek metin; girdi belgeyle kosinüs benzerliği hesaplanır,
# eşiği geçen en yakın kategori önerilir — geçmezse None (kural motorunun
# "belirsiz" kararına saygı duyulur).
PROTOTYPES: dict[str, tuple[str, ...]] = {
    "tebligat": (
        "İşbu tebliğ mazbatası 7201 sayılı Tebligat Kanunu uyarınca muhataba tebliğ edilmek üzere düzenlenmiştir.",
        "Karar örneği muhataba tebliğ edilmiş olup tebligat mazbatası dosyasına eklenmiştir.",
    ),
    "olur": (
        "Yukarıda arz edilen hususun makamın oluruna sunulması arz olunur. Olurunuza arz ederim.",
        "İşin olur'a arz edilmesini ve gereğinin yapılmasını arz ederim.",
    ),
    "genelge": (
        "Bu genelge tüm birimlere tebliğ edilmek üzere yayımlanmıştır; genelgenin gereğinin yerine getirilmesi rica olunur.",
    ),
    "tutanak": (
        "İşbu tutanaktır. Yapılan tespitler aşağıda kayıt altına alınmış ve taraflarca imza altına alınmıştır.",
    ),
    "rapor": (
        "İşbu inceleme raporu yapılan faaliyetlerin sonuçlarını özetlemektedir. Faaliyet raporudur.",
    ),
    "cevap_yazisi": (
        "İlgi yazınıza cevaben, aşağıdaki hususların bilgilerinize sunulduğu arz ederiz.",
        "Yazınıza cevaben gerekli açıklamalar bu yazı ile iletilmektedir.",
    ),
    "bilgi_yazisi": (
        "Konuya ilişkin gelişmeler bilgi için sunulmuştur; bilgilerinize arz olunur.",
    ),
    "ust_yazi": (
        "Sayı ve konu başlığını taşıyan üst yazı, ek listesi ve dağıtım listesiyle birlikte havale olunur.",
    ),
    "iddianame": (
        "Şüpheli hakkında kamu davası açılmıştır. İşbu iddianame ile sanığın cezalandırılması talep edilmektedir.",
    ),
    "mahkeme_karari": (
        "Mahkememizce yapılan yargılama sonunda gerekçeli karar ile sanığın mahkûmiyetine karar verilmiştir.",
        "Davanın reddine, hükmün taraflara tebliğine karar verildi.",
    ),
    "dilekce": (
        "Şikayetçidir; müvekkilim adına arz ve izah olunan hususların dikkate alınmasını saygıyla arz ederim.",
    ),
}

# Kosinüs benzerliği bu eşiğin altındaysa hiçbir kategori önerilmez — kural
# motorunun "belirsiz" kararı korunur (yanlış ama kendinden emin bir tahmin,
# hiç tahmin vermemekten daha kötüdür).
SIMILARITY_THRESHOLD = 0.42


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


class PrototypeClassifier:
    """Her kategorinin prototip metinleri kurulumda TEK SEFERLİK
    vektörleştirilip önbelleğe alınır; `classify()` sonrasında yalnızca
    girdi belgeyi vektörleştirip kosinüs benzerliği hesaplar."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._vectors: dict[str, list[list[float]]] = {
            label: embedder.embed(list(texts)) for label, texts in PROTOTYPES.items()
        }

    def classify(self, text: str) -> tuple[str, float] | None:
        query = self._embedder.embed([text])[0]
        best_label = ""
        best_score = 0.0
        for label, vectors in self._vectors.items():
            for vector in vectors:
                score = _cosine(query, vector)
                if score > best_score:
                    best_score = score
                    best_label = label
        if best_label and best_score >= SIMILARITY_THRESHOLD:
            return best_label, round(best_score, 3)
        return None


@lru_cache(maxsize=1)
def create_prototype_classifier(*, prefer_neural: bool = True) -> PrototypeClassifier | None:
    """`retrieval/cross_encoder.py::create_reranker` ile AYNI zarif-düşüş
    deseni: `classification_fallback.enabled` kapalıysa (varsayılan — bkz.
    config/models.yaml) veya yerel model kurulamazsa (offline,
    sentence-transformers kurulu değil, ilk kurulumda internet yok, vb.)
    sessizce None döner; çağıran taraf (`classify.py`) bunu "bu özelliği pas
    geç, kural motorunun 'belirsiz' kararına güven" diye yorumlar.
    `lru_cache` ile tekil örnek — model her "belirsiz" belgede yeniden
    yüklenmez."""
    if not get_models().classification_fallback_enabled:
        return None
    try:
        embedder = create_embedder(prefer_neural=prefer_neural)
        return PrototypeClassifier(embedder)
    except Exception:
        return None
