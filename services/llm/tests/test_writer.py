from __future__ import annotations

import json

from llm.render import petition_view, render_arastirma, render_belge
from llm.writer import write_belge, write_module
from llm.formats import load_belge


def test_render_arastirma_keeps_citations() -> None:
    text = render_arastirma(
        {
            "ozet": "Nitelikli dolandırıcılık TCK m.158’dedir [1].",
            "ana_kaynak_n": 1,
            "gerekce": [{"n": 1, "cumle": "Madde 158 nitelikli hâlleri sayar."}],
            "ilgili": [{"n": 3, "neden": "Temel şekil TCK m.157’dedir."}],
            "kaynak_uyari": "Bu metin yalnızca yukarıdaki resmi kaynaklara dayanır.",
        }
    )
    assert text.startswith("Sonuç")
    assert "Hukuki dayanak" in text
    assert "1. " in text
    assert "İlgili hükümler" in text
    assert "Kaynak" in text
    assert "[1]" in text
    assert "TCK m.158" in text or "nitelikli" in text.lower()
    assert "Gerekçe" not in text.split("\n")[0]


def test_short_ozet_is_padded_to_five_sentences() -> None:
    from llm.render import count_sonuc_sentences

    text = render_arastirma(
        {
            "ozet": "Trafik güvenliğini tehlikeye sokma TCK m.179’de düzenlenir [1]. Sorudaki kavram bu hükmün konusuna girer [1].",
            "ana_kaynak_n": 1,
            "gerekce": [{"n": 1, "cumle": "Madde 179 işaretlerin bozulmasını cezalandırır [1]."}],
            "kaynak_uyari": "Bu metin yalnızca yukarıdaki resmi kaynaklara dayanır.",
        }
    )
    parts = text.split("\n\n")
    assert parts[0] == "Sonuç"
    assert count_sonuc_sentences(parts[1]) >= 5



def test_compact_engine_keeps_span_not_full_article() -> None:
    from llm.writer import compact_engine

    blob = "Madde 158- " + ("nitelikli dolandırıcılık. " * 80)
    out = compact_engine(
        {
            "user_text": "x" * 4000,
            "related": [{"n": 1, "title": "TCK 158", "article_no": "158", "law_no": "5237", "content": blob}],
            "evidence": [{"n": 1, "title": "TCK 158", "content": blob, "extra": "drop me"}],
            "classification": {"label": "Mahkeme kararı", "document_type": "mahkeme_karari"},
        }
    )
    assert len(out["user_text"]) <= 800
    assert "content" not in out["related"][0]
    assert len(out["related"][0]["span"]) <= 280
    assert len(out["evidence"][0]["span"]) <= 720
    assert len(out["evidence"][0]["span"]) < len(blob)
    assert "extra" not in out["evidence"][0]
    assert out["classification"]["label"] == "Mahkeme kararı"


def test_write_module_uses_chat_and_skips_ping(monkeypatch) -> None:
    from llm import writer as writer_mod

    monkeypatch.setattr(writer_mod, "ollama_enabled", lambda: True)
    monkeypatch.setattr(writer_mod, "ping", lambda: True)

    def fake_chat(messages, **kwargs):
        assert "Araştırma" in messages[0]["content"]
        return json.dumps(
            {
                "ozet": "Özet [1].",
                "ana_kaynak_n": 1,
                "gerekce": [{"n": 1, "cumle": "Kaynak cümle [1]."}],
                "kaynak_uyari": "Bu metin yalnızca yukarıdaki resmi kaynaklara dayanır.",
            },
            ensure_ascii=False,
        )

    text = write_module("arastirma", {"query": "dolandırıcılık", "evidence": []}, chat_fn=fake_chat)
    assert text is not None
    assert "Özet" in text


def test_write_belge_istinaf_section_order(monkeypatch) -> None:
    from llm import writer as writer_mod

    monkeypatch.setattr(writer_mod, "ollama_enabled", lambda: True)
    monkeypatch.setattr(writer_mod, "ping", lambda: True)
    spec = load_belge("istinaf")
    example = spec["example"]

    text = write_belge("istinaf", {"action": "istinaf"}, chat_fn=lambda messages, **k: json.dumps(example, ensure_ascii=False))
    assert text.lstrip().startswith("T.C.")
    assert "CMK m.273" in text
    rendered = render_belge(spec, example)
    assert rendered.lstrip().startswith("T.C.")
    assert "aracılığıyla" in rendered.lower()
    assert "CMK m.273" in rendered
    assert "Gereğini arz ederim." in rendered
    assert "(imza)" in rendered
    assert "EKLER:" in rendered
    assert "Adres:" in rendered
    assert "İSTİNAF DİLEKÇESİDİR" not in rendered


def test_render_belge_maps_sure_cumlesi_into_sure_section() -> None:
    spec = load_belge("istinaf")
    text = render_belge(
        spec,
        {
            "makam": "Bölge Adliye Mahkemesi ilgili ceza dairesi",
            "hukum": "Mahkûmiyet hükmü",
            "sure_cumlesi": "İstinaf süresi CMK m.273 uyarınca tebliğden itibaren iki hafta içindedir.",
            "sebepler": ["Hükmün hukuka aykırılığı"],
            "talep": "Hükmün kaldırılması talep olunur.",
        },
    )
    assert text.lstrip().startswith("T.C.")
    assert "Süre (CMK m.273)" not in text
    assert "İSTİNAF SEBEPLERİ" not in text
    assert "İSTİNAF DİLEKÇESİDİR" not in text
    assert "CMK m.273" in text or "CMK M.273" in text
    assert "Gereğini arz ederim." in text
    assert "Adres:" in text
    assert "(imza)" in text
    assert "EKLER:" in text
    assert "EK-1" in text


def test_extractive_sikayet_uses_savcilik_not_generic_unit(monkeypatch) -> None:
    from llm import writer as writer_mod
    from llm.writer import write_belge

    monkeypatch.setattr(writer_mod, "api_configured", lambda: False)
    monkeypatch.setattr(writer_mod, "ollama_enabled", lambda: False)
    text = write_belge(
        "sikayet",
        {"user_text": "Bankadan paramı aldılar, savcılığa şikayet etmek istiyorum.", "action": "sikayet"},
    )
    assert text is not None
    assert "savcılı" in text.lower()
    assert "ŞİKAYET DİLEKÇESİDİR" not in text
    assert text.lstrip().startswith("T.C.")
    assert "(imza)" in text
    assert "EKLER:" in text
    assert "İLGİLİ BİRİM BELİRLENEMEDİ" not in text
    assert "Bankadan paramı aldılar" in text
    assert "158" not in text


def test_write_module_merges_example_when_keys_missing(monkeypatch) -> None:
    from llm import writer as writer_mod

    monkeypatch.setattr(writer_mod, "ollama_enabled", lambda: True)
    monkeypatch.setattr(writer_mod, "ping", lambda: True)

    text = write_module(
        "arastirma",
        {"query": "dolandırıcılık", "evidence": []},
        chat_fn=lambda messages, **k: json.dumps({"ozet": "Kısa özet [1]."}, ensure_ascii=False),
    )
    assert text is not None
    assert "Kısa özet" in text
    assert "kaynak" in text.lower()


def test_resolve_writer_prefers_api(monkeypatch) -> None:
    from llm import writer as writer_mod
    from llm.writer import resolve_writer, writer_name

    monkeypatch.setattr(writer_mod, "api_configured", lambda: True)
    monkeypatch.setattr(writer_mod, "ollama_enabled", lambda: True)
    monkeypatch.setattr(writer_mod, "ping", lambda: True)
    assert resolve_writer(allow_ollama=False) is writer_mod.api_chat
    assert writer_name(allow_ollama=False) == "api"


def test_resolve_writer_skips_ollama_when_disallowed(monkeypatch) -> None:
    from llm import writer as writer_mod
    from llm.writer import resolve_writer, writer_name

    monkeypatch.setattr(writer_mod, "api_configured", lambda: False)
    monkeypatch.setattr(writer_mod, "ollama_enabled", lambda: True)
    monkeypatch.setattr(writer_mod, "ping", lambda: True)
    assert resolve_writer(allow_ollama=False) is None
    assert writer_name(allow_ollama=False) == "extractive"


def test_write_surec_keeps_engine_last_day() -> None:
    engine = {
        "classification": {
            "stage": "kovusturma",
            "remedies": ["istinaf", "itiraz"],
            "label": "Mahkeme kararı",
        },
        "deadlines": [
            {
                "rule_id": "deadline:istinaf:cmk273",
                "name": "İstinaf",
                "trigger": "2026-08-20",
                "last_day": "2026-08-27",
                "legal_basis": ["CMK m.273"],
                "missing": None,
            }
        ],
    }

    def fake_chat(messages, **kwargs):
        return json.dumps(
            {
                "asama_cumlesi": "Kovuşturma aşamasındadır.",
                "kanun_yollari": [],
                "sureler": [
                    {
                        "rule_id": "cmk-istinaf",
                        "anlatim": "İstinaf süresi tebliğ yoksa son gün üretilemez (CMK m.273).",
                    }
                ],
                "uyari": "Süreler kural motoruyla hesaplanmıştır; model tahmin etmez.",
            },
            ensure_ascii=False,
        )

    text = write_module("surec", engine, chat_fn=fake_chat)
    assert text is not None
    assert "27.08.2026" in text
    assert "üretilemez" not in text
    assert "cmk-istinaf" not in text
    assert "Kovuşturma" in text or "kovuşturma" in text.lower()


def test_each_belge_has_its_own_layout() -> None:
    from llm.formats import load_belge
    from llm.layouts import belge_layout, petition_view
    from llm.render import render_belge

    markers = {
        "sikayet": "Cumhuriyet Başsavcılığı",
        "suc_duyurusu": "Cumhuriyet Başsavcılığı",
        "cevap": "Görevli ceza mahkemesi",
        "itiraz": "Kararı veren merci",
        "istinaf": "Bölge Adliye Mahkemesi",
        "temyiz": "Yargıtay",
        "katilma": "ceza mahkemesi",
        "tahliye": "Tutuklamaya karar veren mahkeme",
        "bireysel_basvuru": "Anayasa Mahkemesi",
        "idari_dava": "idare mahkemesi",
        "adli_kontrol_itiraz": "İtiraz mercii",
    }
    seen_layouts: set[str] = set()
    for belge_id, marker in markers.items():
        spec = load_belge(belge_id)
        text = render_belge(spec, spec["example"])
        view = petition_view(spec, spec["example"])
        assert marker.casefold() in text.casefold(), belge_id
        assert text.lstrip().startswith("T.C."), belge_id
        assert "Adres:" in text, belge_id
        assert "(imza)" in text, belge_id
        assert "EKLER:" in text, belge_id
        assert "EK-1" in text, belge_id
        assert "Gereğini arz ederim." in text, belge_id
        assert "DİLEKÇESİDİR" not in text, belge_id
        assert view["layout"] != "dilekce", belge_id
        assert view.get("form") == "dilekce", belge_id
        seen_layouts.add(view["layout"])
        assert "Tür belirsiz hk" not in text
    assert belge_layout(load_belge("ust_yazi")) == "resmi"
    resmi = render_belge(load_belge("ust_yazi"), load_belge("ust_yazi")["example"])
    assert "Sayı" in resmi
    assert "ŞİKAYET DİLEKÇESİDİR" not in resmi
    assert "savcilik" in seen_layouts
    assert "istinaf" in seen_layouts
    assert "aym" in seen_layouts
    assert "idari" in seen_layouts


def test_incomplete_sikayet_rewrites_with_placeholders() -> None:
    from llm.writer import compose_belge

    engine = {
        "action": "sikayet",
        "user_text": "paramı aldılar şikayet etmek istiyorum",
        "related": [],
        "fields": {},
        "dates": {},
        "deadlines": [],
    }

    def fake_chat(messages, **kwargs):
        return json.dumps(
            {
                "makam": "Cumhuriyet Başsavcılığı",
                "sikayetci": "Ahmet Yılmaz",
                "sikayet_edilen": "Mehmet Demir",
                "olay": "paramı aldılar şikayet etmek istiyorum",
                "hukuki_nitelendirme": [
                    {"cumle": "Mevzuat aramasında eşleşen madde yok; taslağa TCK maddesi yazılmadı."}
                ],
                "deliller": ["Uydurma dekont"],
                "talep": "Soruşturma açılması talep olunur.",
            },
            ensure_ascii=False,
        )

    text, view = compose_belge("sikayet", engine, chat_fn=fake_chat)
    assert "Ahmet Yılmaz" not in text
    assert "Mehmet Demir" not in text
    assert "«[şikayetçi" in text
    assert "paramı aldılar" in text
    assert not any(section.get("id") == "eksikler" for section in view.get("sections") or [])
    assert "EKSİK HUSUSLAR" not in text
    assert "şurada eksikliğin var" not in text.lower()


def test_sikayet_does_not_cite_article_without_related_hits() -> None:
    from llm.writer import compose_belge

    engine = {
        "action": "sikayet",
        "user_text": "Paramı aldılar, savcılığa şikayet etmek istiyorum.",
        "related": [],
        "evidence": [],
        "fields": {},
        "dates": {},
        "deadlines": [],
    }

    def fake_chat(messages, **kwargs):
        return json.dumps(
            {
                "makam": "Cumhuriyet Başsavcılığı",
                "sikayetci": "«[şikayetçi adı-soyadı]»",
                "sikayet_edilen": "Kimliği belirsiz şüpheli",
                "olay": "Paramı aldılar, savcılığa şikayet etmek istiyorum.",
                "hukuki_nitelendirme": [
                    {
                        "n": 1,
                        "madde": "158",
                        "cumle": "Fiil, TCK m.158’de düzenlenen nitelikli dolandırıcılık kapsamında değerlendirilebilir [1].",
                    }
                ],
                "deliller": ["«[deliller — dekont, yazışma, tanık]»"],
                "talep": (
                    "Şikayet edilen hakkında soruşturma açılması, delillerin toplanması "
                    "ve kamu davası açılması talep olunur. Mahkûmiyet cümlesi talep edilir."
                ),
            },
            ensure_ascii=False,
        )

    text, _view = compose_belge("sikayet", engine, chat_fn=fake_chat)
    assert "158" not in text
    assert "nitelikli dolandırıcılık" not in text.lower()
    assert "yazılmadı" not in text
    assert "Mahkûmiyet" not in text and "mahkûmiyet" not in text.lower()
    assert "kamu davası" in text.lower()


def test_istinaf_format_is_formal() -> None:
    from llm.formats import load_belge
    from llm.writer import compose_belge, extractive_parsed

    user = "Mahkeme beni mahkum etti, üst mahkemeye gitmek istiyorum"
    spec = load_belge("istinaf")
    engine = {
        "action": "istinaf",
        "user_text": user,
        "related": [],
        "evidence": [],
        "fields": {},
        "dates": {},
        "deadlines": [],
    }
    parsed = extractive_parsed(spec, engine)
    assert user not in str(parsed.get("hukum") or "")
    assert "mahkûmiyet hükmü" in str(parsed.get("hukum") or "").lower() or "mahkumiyet" in str(
        parsed.get("hukum") or ""
    ).lower()

    def fake_chat(messages, **kwargs):
        return json.dumps(
            {
                "makam": spec["example"]["makam"],
                "hukum": user,
                "sure_cumlesi": spec["example"]["sure_cumlesi"],
                "sebepler": [user],
                "hukuki_nitelendirme": [
                    {"cumle": "Mevzuat aramasında eşleşen madde yok; taslağa TCK maddesi yazılmadı."}
                ],
                "talep": spec["example"]["talep"],
            },
            ensure_ascii=False,
        )

    text, view = compose_belge("istinaf", engine, chat_fn=fake_chat)
    assert user not in text
    assert "beni mahkum" not in text.lower()
    assert "EKSİK HUSUSLAR" not in text
    assert "eşleşen madde yok" not in text
    assert "yazılmadı" not in text
    assert "CMK m.273" in text or "CMK m.272" in text
    assert text.lstrip().startswith("T.C.")
    assert "Gereğini arz ederim." in text
    assert "Adres:" in text
    assert "(imza)" in text
    assert "EKLER:" in text
    assert "İSTİNAF DİLEKÇESİDİR" not in text
    assert not any(section.get("id") == "eksikler" for section in view.get("sections") or [])
    hukum = next((row["value"] for row in view.get("meta") or [] if "hüküm" in row["label"].lower()), "")
    assert user not in hukum
    assert any(section.get("id") == "sebepler" for section in view.get("sections") or [])
    assert view.get("form") == "dilekce"


def test_cite_line_keeps_cmk_not_tck() -> None:
    from llm.layouts import _cite_line

    line = _cite_line({"cumle": "Başvuru CMK m.272, CMK m.273 hükümlerine tabidir."})
    assert "TCK" not in line
    assert "CMK m.273" in line
    tck = _cite_line({"madde": "158", "kanun": "TCK", "cumle": "Nitelikli hâl.", "n": 1})
    assert tck.startswith("TCK m.158")
    assert "[1]" in tck


def test_petition_view_reports_which_related_n_was_actually_cited() -> None:
    """Madde 1/Kaynak grafiği: sanitizer kaynaksız maddeyi düşürüp yerine `n`
    taşımayan bir yer tutucu koyarsa, o kaynak taslakta gerçekten
    kullanılmamıştır — `cited_ns` bunu yansıtmalı (KISMEN VAR → VAR)."""
    spec = load_belge("istinaf")
    used = petition_view(
        spec,
        {
            **spec["example"],
            "hukuki_nitelendirme": [{"n": 2, "madde": "273", "kanun": "CMK", "cumle": "İstinaf usulü."}],
        },
    )
    assert used["cited_ns"] == [2]

    fallback = petition_view(
        spec,
        {**spec["example"], "hukuki_nitelendirme": [{"cumle": "Mevzuat aramasında eşleşen madde yok."}]},
    )
    assert fallback["cited_ns"] == []
