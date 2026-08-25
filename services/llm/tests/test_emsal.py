from __future__ import annotations

import json

from llm.emsal import emsal_atif_or_drop, emsal_search_query, pick_emsal
from llm.formats import load_belge
from llm.writer import compact_engine, compose_belge, extractive_parsed


COURT_HIT = {
    "n": 1,
    "document_type": "court_decision",
    "court": "Yargıtay 11. Ceza Dairesi",
    "esas_no": "2018/334",
    "karar_no": "2018/891",
    "content": "Hükmün bozulmasına karar verilmiştir.",
}


def test_pick_emsal_from_court_hit() -> None:
    hit = {
        **COURT_HIT,
        "content": "Nitelikli dolandırıcılık suçundan hükmün bozulmasına karar verilmiştir.",
    }
    rows = pick_emsal(
        {
            "user_text": "Nitelikli dolandırıcılıktan temyiz",
            "related": [hit],
        }
    )
    assert len(rows) == 1
    assert "2018/334" in rows[0]["atif"]
    assert "2018/891" in rows[0]["atif"]


def test_pick_emsal_omits_unrelated_court_hit() -> None:
    """Konu dolandırıcılık, ilamda yok → künye basılmaz (rastgele gerçek ilam emsal değil)."""
    rows = pick_emsal(
        {
            "action": "temyiz",
            "user_text": "Nitelikli dolandırıcılıktan mahkûmiyet hükmünü temyiz ediyorum.",
            "related": [COURT_HIT],
        },
        action="temyiz",
    )
    assert rows == []


def test_pick_emsal_keeps_court_hit_on_same_offence() -> None:
    hit = {
        **COURT_HIT,
        "content": "Nitelikli dolandırıcılık suçundan kurulan hükmün bozulmasına.",
    }
    rows = pick_emsal(
        {
            "action": "temyiz",
            "user_text": "Nitelikli dolandırıcılıktan mahkûmiyet hükmünü temyiz ediyorum.",
            "related": [hit],
        },
        action="temyiz",
    )
    assert len(rows) == 1
    assert "2018/334" in rows[0]["atif"]
    assert rows[0]["uyum"] is True


def test_pick_emsal_uses_law_title_as_topic() -> None:
    """Kullanıcı 'BAM temyiz' dese bile TCK m.158 başlığı konuyu verir."""
    rows = pick_emsal(
        {
            "action": "temyiz",
            "user_text": "BAM onama kararını temyiz ediyorum.",
            "related": [
                {
                    "document_type": "law",
                    "law_no": "5237",
                    "article_no": "158",
                    "title": "Nitelikli dolandırıcılık",
                },
                {
                    **COURT_HIT,
                    "content": "Nitelikli dolandırıcılık suçundan bozma.",
                },
            ],
        },
        action="temyiz",
    )
    assert rows
    assert "2018/334" in rows[0]["atif"]


def test_emsal_search_query_names_the_offence() -> None:
    query = emsal_search_query(
        {
            "user_text": "BAM onama kararını temyiz ediyorum.",
            "related": [
                {
                    "document_type": "law",
                    "law_no": "5237",
                    "article_no": "158",
                    "title": "Nitelikli dolandırıcılık",
                }
            ],
        }
    )
    assert "dolandırıcılık" in query.casefold()
    assert "yargıtay" in query.casefold() or "yargitay" in query.casefold()


def test_pick_emsal_drops_ticaret() -> None:
    rows = pick_emsal(
        {
            "related": [
                {
                    "document_type": "court_decision",
                    "court": "İstanbul 15. Asliye Ticaret Mahkemesi",
                    "esas_no": "2020/1",
                    "atif": "ticaret 2020/1",
                }
            ]
        }
    )
    assert rows == []


def test_pick_emsal_from_searchhit_decision_id() -> None:
    """API related hits often lack document_type; chunk_id decision:… yeter."""
    rows = pick_emsal(
        {
            "user_text": "Nitelikli dolandırıcılıktan temyiz",
            "related": [
                {
                    "n": 1,
                    "document_id": "decision:yargitay:2026:2022/13957:2024/2429",
                    "title": "1. Ceza Dairesi — 2022/13957 E. — 2024/2429 K.",
                    "article_no": "2024/2429",
                    "content": "Nitelikli dolandırıcılık suçundan hükmün bozulmasına.",
                }
            ],
        }
    )
    assert rows
    assert "2024/2429" in rows[0]["atif"]
    assert "1997/186" not in rows[0]["atif"]


def test_pick_emsal_skips_law_articles() -> None:
    rows = pick_emsal(
        {
            "related": [
                {
                    "n": 1,
                    "document_type": "law",
                    "law_no": "5237",
                    "article_no": "158",
                    "title": "Nitelikli dolandırıcılık",
                }
            ]
        }
    )
    assert rows == []


def test_pick_emsal_no_gold_when_archive_empty() -> None:
    assert pick_emsal({"related": [], "evidence": []}, action="temyiz") == []


def test_pick_emsal_no_gold_istinaf() -> None:
    assert pick_emsal({"related": []}, action="istinaf") == []


def test_emsal_atif_or_drop_replaces_invented() -> None:
    emsal = [
        {
            "atif": "Yargıtay CGK, 1997/1 E., 1997/2 K.",
            "esas_no": "1997/1",
            "karar_no": "1997/2",
        }
    ]
    dropped = emsal_atif_or_drop("Yargıtay 2024/999 E., 2024/1 K.", emsal)
    assert "2024/999" not in dropped
    assert "1997/1" in dropped
    kept = emsal_atif_or_drop("Yargıtay 1997/1 E.", emsal)
    assert "1997/1" in kept


def test_compact_engine_keeps_live_emsal() -> None:
    hit = {
        **COURT_HIT,
        "content": "Nitelikli dolandırıcılık suçundan hükmün bozulmasına.",
    }
    out = compact_engine(
        {
            "action": "istinaf",
            "user_text": "Nitelikli dolandırıcılıktan istinaf",
            "related": [hit],
            "evidence": [],
        }
    )
    assert out["emsal"]
    assert "2018/334" in out["emsal"][0]["atif"]
    assert out["related"][0]["document_type"] == "court_decision"


def test_extractive_istinaf_cites_live_emsal() -> None:
    spec = load_belge("istinaf")
    hit = {
        **COURT_HIT,
        "content": "Nitelikli dolandırıcılık suçundan hükmün bozulmasına.",
    }
    engine = {
        "action": "istinaf",
        "user_text": "Nitelikli dolandırıcılıktan mahkûmiyet hükmüne istinaf",
        "related": [hit],
        "evidence": [],
        "fields": {},
        "dates": {},
        "deadlines": [],
    }
    parsed = extractive_parsed(spec, engine)
    assert "2018/334" in str(parsed.get("emsal_atif") or "")
    assert any("2018/334" in str(item) for item in parsed.get("sebepler") or [])
    blob = " ".join(str(item) for item in parsed.get("sebepler") or [])
    assert "bu yönde" not in blob
    assert "aynı emsale dayanır" not in blob
    assert "somut uyum bu taslakta doğrulanmadı" not in blob


def test_compose_belge_strips_invented_esas() -> None:
    spec = load_belge("istinaf")
    hit = {
        **COURT_HIT,
        "content": "Nitelikli dolandırıcılık suçundan hükmün bozulmasına.",
    }
    engine = {
        "action": "istinaf",
        "user_text": "Nitelikli dolandırıcılıktan mahkûmiyet hükmüne istinaf",
        "related": [hit],
        "evidence": [],
        "fields": {},
        "dates": {},
        "deadlines": [],
    }

    def fake_chat(messages, **kwargs):
        last = messages[-1]["content"]
        assert "2018/334" in last
        assert "yalnızca listedeki künye" in last or "emsal_atif" in last
        return json.dumps(
            {
                **spec["example"],
                "emsal_atif": "Yargıtay 2024/999 E., 2024/1 K.",
            },
            ensure_ascii=False,
        )

    text, view = compose_belge("istinaf", engine, chat_fn=fake_chat)
    assert "2024/999" not in text
    assert "2018/334" in text
    assert any(section.get("id") == "emsal_atif" for section in view.get("sections") or [])


def test_temyiz_without_related_does_not_invent_kunye() -> None:
    spec = load_belge("temyiz")
    engine = {
        "action": "temyiz",
        "user_text": "BAM kararını temyiz",
        "related": [],
        "evidence": [],
        "fields": {},
        "dates": {},
        "deadlines": [],
    }
    parsed = extractive_parsed(spec, engine)
    assert not parsed.get("emsal_atif")


def test_temyiz_does_not_cite_court_hit_as_tck_article() -> None:
    spec = load_belge("temyiz")
    engine = {
        "action": "temyiz",
        "user_text": "BAM kararını temyiz",
        "related": [
            {
                "n": 1,
                "document_id": "decision:yargitay:2026:2022/13957:2024/2429",
                "title": "1. Ceza Dairesi — 2022/13957 E. — 2024/2429 K.",
                "article_no": "2024/2429",
                "content": "Hükmün bozulmasına.",
            },
            {
                "n": 3,
                "document_type": "law",
                "law_no": "5271",
                "article_no": "142",
                "title": "Tazminat isteminin koşulları",
                "content": "Koruma tedbirleri nedeniyle tazminat.",
            },
        ],
        "evidence": [],
        "fields": {},
        "dates": {},
        "deadlines": [],
    }
    text, _ = compose_belge("temyiz", engine, chat_fn=None, allow_ollama=False)
    assert "2024/2429" not in text
    assert "TCK m.2024/2429" not in text
    assert "MURAT YILMAZ" not in text
    assert "CMK m.291" in text
    assert "CMK m.142" not in text
    assert "Tazminat" not in text
    assert "bu yönde" not in text
    assert "aynı emsale dayanır" not in text


def test_pick_emsal_temyiz_drops_aym_person_title() -> None:
    rows = pick_emsal(
        {
            "action": "temyiz",
            "related": [
                {
                    "n": 1,
                    "document_id": "decision:aym:2024:murat",
                    "title": "MURAT YILMAZ",
                    "content": "Başvuru reddedilmiştir.",
                },
                {
                    "n": 2,
                    "document_id": "decision:istinafhukuk:adana:9",
                    "title": "Adana BAM 9. Hukuk Dairesi — 2021/10 E. — 2022/11 K.",
                    "content": "İstinaf talebinin reddine.",
                },
            ],
        },
        action="temyiz",
    )
    assert rows == []


def test_pick_emsal_ranks_overlap_and_labels_ibk() -> None:
    generic = {
        "n": 1,
        "document_type": "court_decision",
        "court": "Yargıtay 1. Ceza Dairesi",
        "esas_no": "2022/13957",
        "karar_no": "2024/2429",
        "title": "1. Ceza Dairesi — 2022/13957 E. — 2024/2429 K.",
        "content": "Hükmün bozulmasına karar verilmiştir.",
    }
    matching = {
        "n": 2,
        "document_type": "court_decision",
        "court": "Yargıtay İçtihadı Birleştirme Kurulu",
        "esas_no": "2019/1",
        "karar_no": "2020/3",
        "title": "İBK — 2019/1 E. — 2020/3 K.",
        "content": "Nitelikli dolandırıcılık suçunda içtihadı birleştirme.",
    }
    rows = pick_emsal(
        {
            "action": "temyiz",
            "user_text": "Nitelikli dolandırıcılıktan mahkûmiyet hükmünü temyiz ediyorum.",
            "related": [generic, matching],
        },
        action="temyiz",
    )
    assert rows
    assert rows[0]["esas_no"] == "2019/1"
    assert rows[0]["kind"] == "ibk"
    assert rows[0]["uyum"] is True
    assert rows[0]["atif"].startswith("İBK")
    assert all(item["esas_no"] != "2022/13957" for item in rows)


def test_temyiz_prints_teblig_date() -> None:
    spec = load_belge("temyiz")
    engine = {
        "action": "temyiz",
        "user_text": (
            "T.C. ANKARA BÖLGE ADLİYE MAHKEMESİ 2. CEZA DAİRESİ KARAR "
            "İlk derece mahkemesinin nitelikli dolandırıcılıktan kurduğu mahkûmiyet hükmü "
            "istinaf incelemesi sonucunda onanmıştır. Karar tarihi: 01.08.2026 "
            "Tebliğ tarihi: 14.08.2026 Hükmün hukuka aykırılığı nedeniyle temyiz yoluna "
            "başvurmak istiyorum."
        ),
        "related": [
            {
                "n": 1,
                "document_id": "decision:yargitay:2026:2022/13957:2024/2429",
                "title": "1. Ceza Dairesi — 2022/13957 E. — 2024/2429 K.",
                "article_no": "2024/2429",
                "content": "Hükmün bozulmasına.",
            }
        ],
        "evidence": [],
        "fields": {},
        "dates": {"teblig": "2026-08-14", "karar": "2026-08-01"},
        "deadlines": [],
    }
    parsed = extractive_parsed(spec, engine)
    assert "14.08.2026" in str(parsed.get("sure_cumlesi") or "")
    assert not parsed.get("emsal_atif")
    blob = " ".join(str(item) for item in parsed.get("sebepler") or [])
    assert "bu yönde" not in blob
    assert "2024/2429" not in blob


def test_temyiz_prints_teblig_date_from_inline_label() -> None:
    spec = load_belge("temyiz")
    engine = {
        "action": "temyiz",
        "user_text": "BAM onama kararını temyiz ediyorum. Tebliğ tarihi: 14.08.2026",
        "related": [],
        "evidence": [],
        "fields": {},
        "dates": {},
        "deadlines": [],
    }
    parsed = extractive_parsed(spec, engine)
    assert "14.08.2026" in str(parsed.get("sure_cumlesi") or "")
