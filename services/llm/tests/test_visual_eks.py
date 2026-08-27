from __future__ import annotations

from llm.formats import load_belge
from llm.prompt import user_prompt
from llm.render import petition_view
from llm.writer import compact_engine, extractive_parsed


def test_compact_engine_keeps_visual_eks() -> None:
    out = compact_engine(
        {
            "user_text": "kaza yaptık şikayet etmek istiyorum",
            "visual_eks": [
                {
                    "caption": "Hasarlı araç görüntüsü",
                    "scene": "Ön tampon ezik, plaka okunmuyor.",
                    "secret": "drop",
                }
            ],
        }
    )
    assert out["visual_eks"][0]["caption"] == "Hasarlı araç görüntüsü"
    assert "tampon" in out["visual_eks"][0]["scene"]
    assert "secret" not in out["visual_eks"][0]


def test_user_prompt_asks_llm_to_cite_annex_visuals() -> None:
    text = user_prompt(
        "sikayet",
        {
            "user_text": "kaza",
            "visual_eks": [{"caption": "Kaza görüntüsü", "scene": "Hasarlı araç."}],
            "related": [],
            "evidence": [],
            "gaps": [],
        },
    )
    lowered = text.lower()
    assert "visual_eks" in text
    assert "ekte" in lowered or "ekler" in lowered
    assert "görsel" in lowered or "gorsel" in lowered


def test_extractive_sikayet_puts_photo_in_ekler_and_mentions_annex() -> None:
    spec = load_belge("sikayet")
    parsed = extractive_parsed(
        spec,
        {
            "action": "sikayet",
            "user_text": "Bankada paramı çektiler, savcılığa şikayet etmek istiyorum.",
            "visual_eks": [
                {
                    "caption": "ATM önü güvenlik kamerası karesi",
                    "scene": "ATM önünde bir kişi durmaktadır; yüz ayırt edilememektedir.",
                }
            ],
        },
    )
    view = petition_view(spec, parsed)
    assert any("ATM" in item for item in view["ekler"])
    blob = str(parsed.get("olay") or "").lower()
    assert "ekte" in blob or "ekler" in blob
