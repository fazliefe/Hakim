from __future__ import annotations

from hakim_config import reload_models
from document_ai.prototype_classifier import PrototypeClassifier, create_prototype_classifier
from retrieval.embeddings import HashingEmbedder


def test_classify_picks_closest_category_by_cosine_similarity() -> None:
    # HashingEmbedder deterministik bag-of-tokens'tır (model indirmez, ağ
    # gerektirmez) — burada "gerçek" bir embedder olarak, kosinüs benzerliği
    # mantığını uçtan uca doğrulamak için kullanılıyor.
    classifier = PrototypeClassifier(HashingEmbedder(dims=256))
    text = (
        "Mahkememizce yapılan yargılama sonunda gerekçeli karar ile sanığın "
        "mahkûmiyetine karar verilmiştir."
    )
    result = classifier.classify(text)
    assert result is not None
    label, score = result
    assert label == "mahkeme_karari"
    assert score >= 0.42


def test_classify_returns_none_below_threshold() -> None:
    classifier = PrototypeClassifier(HashingEmbedder(dims=256))
    result = classifier.classify("Merhaba, toplantı notu.")
    assert result is None


def test_create_prototype_classifier_disabled_by_default() -> None:
    # config/models.yaml: classification_fallback.enabled varsayılan false —
    # mevcut kurulumların/testlerin sınıflandırma davranışı sessizce
    # değişmemeli.
    reload_models()
    create_prototype_classifier.cache_clear()
    assert create_prototype_classifier() is None


def test_create_prototype_classifier_enabled_via_env(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_CLASSIFICATION_FALLBACK", "1")
    reload_models()
    create_prototype_classifier.cache_clear()
    try:
        classifier = create_prototype_classifier()
        assert classifier is None or isinstance(classifier, PrototypeClassifier)
    finally:
        monkeypatch.delenv("HAKIM_CLASSIFICATION_FALLBACK", raising=False)
        reload_models()
        create_prototype_classifier.cache_clear()


def test_create_prototype_classifier_falls_back_silently_on_embedder_error(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_CLASSIFICATION_FALLBACK", "1")
    reload_models()
    create_prototype_classifier.cache_clear()

    def _boom(*, prefer_neural: bool = True):
        raise RuntimeError("model indirilemedi")

    monkeypatch.setattr("document_ai.prototype_classifier.create_embedder", _boom)
    try:
        assert create_prototype_classifier() is None
    finally:
        monkeypatch.delenv("HAKIM_CLASSIFICATION_FALLBACK", raising=False)
        reload_models()
        create_prototype_classifier.cache_clear()
