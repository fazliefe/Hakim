from __future__ import annotations

from llm.prompt import (
    belge_system_prompt,
    missing_citation_answer,
    refuse_answer,
    system_prompt,
    user_prompt,
)


def test_arastirma_system_prompt_is_professional_and_source_bound() -> None:
    text = system_prompt("arastirma")
    lowered = text.lower()
    assert "HÂKİM" in text or "Hakim" in text
    assert "JSON" in text
    assert "ozet" in text
    assert "uydur" in lowered or "yasak" in lowered
    assert "[n]" in text or "[1]" in text
    assert "ilk cümle" in lowered or "soruyu cevapla" in lowered
    assert "parafraz" in lowered or "yapıştırma" in lowered
    assert "6 ila 10" in text or "6–10" in text
    assert "5 ila 8" in text or "en az 5" in text
    assert "CMK" in text and "TCK" in text


def test_arastirma_user_prompt_lists_sources_not_raw_dump() -> None:
    compact = {
        "query": "nitelikli dolandırıcılıkta banka hesabının kullanılması",
        "evidence": [
            {
                "n": 1,
                "law_no": "5237",
                "article_no": "158",
                "title": "Nitelikli dolandırıcılık",
                "span": "Banka veya kredi kurumlarının araç olarak kullanılması.",
            }
        ],
        "related": [],
        "gaps": [],
    }
    text = user_prompt("arastirma", compact)
    assert "nitelikli dolandırıcılıkta banka" in text
    assert "[1]" in text
    assert "TCK" in text or "158" in text
    assert "Banka veya kredi kurumlarının" in text
    assert text.strip().startswith("Soru:")


def test_arastirma_user_prompt_forbids_articles_without_sources() -> None:
    text = user_prompt("arastirma", {"query": "şikayet süresi", "evidence": [], "related": [], "gaps": []})
    assert "madde" in text.lower()
    assert "yazma" in text.lower() or "uydurma" in text.lower()


def test_sikayet_belge_prompt_keeps_catalog_rules() -> None:
    prompt = belge_system_prompt("sikayet")
    assert "Şikayet dilekçesi" in prompt
    assert "TCK m.73" in prompt
    assert "İddianame" in prompt or "iddianame" in prompt.lower()


def test_refuse_and_missing_citation_copy() -> None:
    refuse = refuse_answer()
    assert "hukuk" in refuse.lower()
    assert "TCK" not in refuse
    assert "spor" not in refuse.lower()
    assert "cevap üretilmez" in refuse.lower() or "cevap verilmez" in refuse.lower()
    missing = missing_citation_answer("5237", "158")
    assert "m.158" in missing
    assert "TCK" in missing
