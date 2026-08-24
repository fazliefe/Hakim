from retrieval.research import EvidenceItem, _build_extractive_answer, _official_span
import re


def _item(**kwargs) -> EvidenceItem:
    base = dict(
        chunk_id="law:5237:article:158:v1",
        document_id="law:5237",
        law_no="5237",
        article_no="158",
        title="Nitelikli dolandırıcılık",
        content="Madde 158- (1) Dolandırıcılık suçunun;",
        authority="official",
        bm25_rank=1,
        semantic_rank=1,
        rrf_rank=1,
        rrf_score=0.03,
        retrievers=["bm25", "semantic"],
        used_in_answer=True,
    )
    base.update(kwargs)
    return EvidenceItem(n=kwargs.get("n", 1), **{k: v for k, v in base.items() if k != "n"})


def test_extractive_answer_includes_citation_markers() -> None:
    evidence = [
        _item(
            content=(
                "Madde 158- (1) Dolandırıcılık suçunun; f) Bilişim sistemlerinin, "
                "banka veya kredi kurumlarının araç olarak kullanılması suretiyle,"
            )
        )
    ]
    answer = _build_extractive_answer("nitelikli dolandırıcılıkta banka hesabı", evidence)
    assert "Sonuç" in answer
    assert "Hukuki dayanak" in answer
    assert "Kaynak" in answer
    assert "TCK m.158" in answer
    assert "[1]" in answer
    assert "banka" in answer.lower()
    assert "extractive" not in answer.lower()
    assert "**Cevap.**" not in answer
    assert "en yakın resmi" not in answer.lower()
    assert "birlikte değerlendirilir" not in answer
    parts = answer.split("\n\n")
    assert parts[0] == "Sonuç"
    assert parts[1].strip().startswith("Evet:")
    assert "kapsamında" in parts[1]
    assert "[1]" in parts[1]
    assert not parts[1].strip().startswith("“")
    assert "suretiyle, e)" not in answer
    assert "«ası" not in answer


def _sonuc_block(answer: str) -> str:
    parts = answer.split("\n\n")
    assert parts[0] == "Sonuç"
    return parts[1].strip()


def _sentence_count(text: str) -> int:
    return len([part for part in re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜÂÊÎÔÛ«\"])", text.strip()) if part.strip()])


def test_extractive_sonuc_has_at_least_five_sentences() -> None:
    answer = _build_extractive_answer(
        "trafik güvenliğini tehlikeye sokma",
        [
            _item(
                n=1,
                chunk_id="law:5237:article:179:v1",
                article_no="179",
                title="Trafik güvenliğini tehlikeye sokma",
                content=(
                    "Madde 179- (1) Kara, deniz, hava veya demiryolu ulaşımının "
                    "güven içinde akışını sağlamak için konulmuş her türlü işareti değiştirerek,"
                ),
            )
        ],
    )
    assert _sentence_count(_sonuc_block(answer)) >= 5


def test_extractive_answer_explains_the_holding() -> None:
    content = (
        "Madde 158- (1) Dolandırıcılık suçunun; "
        "f) Bilişim sistemlerinin, banka veya kredi kurumlarının araç olarak kullanılması suretiyle,"
    )
    answer = _build_extractive_answer(
        "nitelikli dolandırıcılıkta banka hesabının kullanılması",
        [
            _item(content=content),
            _item(
                n=3,
                chunk_id="law:5237:article:157:v1",
                article_no="157",
                title="Dolandırıcılık",
                content="Madde 157- (1) Hileli davranışlarla bir kimseyi aldatıp,",
            ),
        ],
    )
    body = answer.split("\n\nKaynak\n\n")[0]
    assert body.startswith("Sonuç")
    assert "Evet:" in body
    assert "TCK m.158" in body
    assert "banka" in body.lower()
    assert "TCK m.157" in body
    assert "temel" in body.lower()
    assert len(body) >= 700
    assert body.count("\n\n") >= 3
    assert "[1]" in body
    assert "m.245" not in body


def test_banka_query_quotes_banka_clause_not_kamu() -> None:
    from retrieval.research import _clause_for_query

    content = (
        "Madde 158- (1) Dolandırıcılık suçunun; "
        "d) Kamu kurum ve kuruluşlarının araç olarak kullanılması suretiyle, "
        "e) Kamu kurum ve kuruluşlarının zararına olarak, "
        "f) Bilişim sistemlerinin, banka veya kredi kurumlarının araç olarak kullanılması suretiyle,"
    )
    clause = _clause_for_query("nitelikli dolandırıcılıkta banka hesabının kullanılması", content)
    assert clause
    assert "banka" in clause.lower()
    assert "siyasi parti" not in clause.lower()
    answer = _build_extractive_answer(
        "nitelikli dolandırıcılıkta banka hesabının kullanılması",
        [_item(content=content)],
    )
    assert "banka" in answer.lower()
    assert "kamu meslek" not in answer.lower()
    assert "m.245" not in answer


def test_official_span_starts_at_madde_not_mid_clause() -> None:
    content = (
        "Madde 158- (1) Dolandırıcılık suçunun; "
        "a) Dinî inanç ve duyguların istismar edilmesi suretiyle, "
        "b) Kişinin içinde bulunduğu tehlikeli durum veya zor şartlardan yararlanmak suretiyle, "
        "c) Kişinin algılama yeteneğinin zayıflığından yararlanmak suretiyle, "
        "d) Kamu kurum ve kuruluşlarının araç olarak kullanılması suretiyle, "
        "e) Kamu kurum ve kuruluşlarının zararına olarak, "
        "f) Bilişim sistemlerinin, banka veya kredi kurumlarının araç olarak kullanılması suretiyle,"
    )
    span = _official_span(
        _item(content=content),
        "kamu zararına nitelikli dolandırıcılık",
    )
    assert span.startswith("Madde 158")
    assert not span.lower().startswith("ası")
    assert "suretiyle, e)" not in span[:40]


def test_extractive_skips_unrelated_neighbors() -> None:
    evidence = [
        _item(n=1),
        _item(
            n=2,
            chunk_id="law:5237:article:245:v1",
            article_no="245",
            title="Banka veya kredi kartlarının kötüye kullanılması",
            content="Madde 245- (1) Başkasına ait bir banka veya kredi kartını,",
        ),
        _item(
            n=3,
            chunk_id="law:5237:article:157:v1",
            article_no="157",
            title="Dolandırıcılık",
            content="Madde 157- (1) Hileli davranışlarla bir kimseyi aldatıp,",
        ),
        _item(
            n=4,
            chunk_id="law:5237:article:268:v1",
            article_no="268",
            title="Başkasına ait kimlik veya kimlik bilgilerinin kullanılması",
            content="Madde 268-",
        ),
        _item(
            n=5,
            chunk_id="law:5237:article:209:v1",
            article_no="209",
            title="Açığa imzanın kötüye kullanılması",
            content="Madde 209-",
        ),
    ]
    answer = _build_extractive_answer("nitelikli dolandırıcılık", evidence)
    assert "TCK m.158" in answer
    assert "m.157" in answer
    assert "m.245" not in answer
    assert "m.268" not in answer
    assert "m.209" not in answer
    assert "birlikte değerlendirilir" not in answer


def test_cmk_query_does_not_accept_tck_standin() -> None:
    from retrieval.research import _query_supported

    assert (
        _query_supported(
            "CMK madde 158 ihbar ve şikayet nasıl yapılır?",
            [_item()],
        )
        is False
    )


def test_how_query_writes_plain_procedure_sentences() -> None:
    evidence = [
        _item(
            chunk_id="law:5271:article:158:v1",
            document_id="law:5271",
            law_no="5271",
            article_no="158",
            title="İhbar ve şikayet",
            content=(
                "Madde 158- (1) Suçlara ilişkin ihbar veya şikayet, Cumhuriyet "
                "Başsavcılığına veya kolluk makamlarına yapılabilir."
            ),
        )
    ]
    answer = _build_extractive_answer(
        "CMK madde 158 ihbar ve şikayet nasıl yapılır?",
        evidence,
    )
    assert "CMK m.158" in answer
    assert "TCK" not in answer
    sonuc = answer.split("\n\n")[1]
    assert "Evet:" not in sonuc
    assert "temel şekli" not in answer.lower()
    assert "kapsamında" not in sonuc.lower()
    assert "ihbar" in answer.lower()
    assert "[1]" in answer


def test_extractive_does_not_call_unrelated_articles_base_offence() -> None:
    evidence = [
        _item(n=1),
        _item(
            n=2,
            chunk_id="law:5237:article:73:v1",
            article_no="73",
            title="Soruşturulması ve kovuşturması şikayete bağlı suçlar",
            content="Madde 73- (1) Soruşturulması ve kovuşturulması şikayete bağlı suçlar",
        ),
        _item(
            n=4,
            chunk_id="law:5237:article:139:v1",
            article_no="139",
            title="Şikayet",
            content="Madde 139-",
        ),
    ]
    answer = _build_extractive_answer("CMK madde 158 ihbar ve şikayet nasıl yapılır?", evidence)
    assert "m.73" not in answer
    assert "m.139" not in answer
    assert "temel şekli" not in answer.lower()


def test_answer_items_keeps_close_articles_only() -> None:
    from retrieval.research import _answer_items

    items = _answer_items(
        "nitelikli dolandırıcılıkta banka hesabının kullanılması",
        [
            _item(n=1),
            _item(
                n=2,
                chunk_id="law:5237:article:245:v1",
                article_no="245",
                title="Banka veya kredi kartlarının kötüye kullanılması",
                content="Madde 245- (1) Başkasına ait bir banka veya kredi kartını,",
            ),
            _item(
                n=3,
                chunk_id="law:5237:article:157:v1",
                article_no="157",
                title="Dolandırıcılık",
                content="Madde 157- (1) Hileli davranışlarla bir kimseyi aldatıp,",
            ),
        ],
    )
    assert [item.article_no for item in items] == ["158", "157"]


def test_how_an_offence_is_regulated_is_not_procedure() -> None:
    from retrieval.research import _is_procedure_query

    assert _is_procedure_query("Trafik güvenliğini tehlikeye sokma TCK m.179’de nasıl düzenlenir?") is False
    assert _is_procedure_query("Bu maddenin birinci ve ikinci fıkraları nasıl ayrılır?") is False
    assert _is_procedure_query("Taksirle işlenmesi TCK m.180’de mi, yoksa 179 kapsamında mı kalır?") is False
    assert _is_procedure_query("CMK madde 158 ihbar ve şikayet nasıl yapılır?") is True


def test_extractive_179_is_not_a_procedure_rule() -> None:
    evidence = [
        _item(
            n=1,
            chunk_id="law:5237:article:179:v1",
            article_no="179",
            title="Trafik güvenliğini tehlikeye sokma",
            content=(
                "Madde 179- (1) Kara, deniz, hava veya demiryolu ulaşımının güven içinde "
                "akışını sağlamak için konulmuş her türlü işareti değiştirerek, kullanılamaz "
                "hale getirerek, konuldukları yerden kaldırarak, yanlış işaretler vererek, "
                "geçiş, varış, kalkış veya inişleri tehlikeye sokan kişi, bir yıldan altı yıla "
                "kadar hapis cezası ile cezalandırılır. "
                "(2) Kara, deniz, hava veya demiryolu ulaşım araçlarını kişilerin hayat, sağlık "
                "veya malvarlığı açısından tehlikeli olabilecek şekilde sevk ve idare eden kişi, "
                "üç aydan iki yıla kadar hapis cezası ile cezalandırılır."
            ),
        )
    ]
    answer = _build_extractive_answer(
        "Trafik güvenliğini tehlikeye sokma TCK m.179’de nasıl düzenlenir?",
        evidence,
    )
    assert "usul kuralı" not in answer.lower()
    assert "TCK m.179" in answer
    assert "başvurunun şeklini" not in answer.lower()


def test_extractive_splits_fikralar_when_asked() -> None:
    evidence = [
        _item(
            n=1,
            chunk_id="law:5237:article:179:v1",
            article_no="179",
            title="Trafik güvenliğini tehlikeye sokma",
            content=(
                "Madde 179- (1) Kara, deniz, hava veya demiryolu ulaşımının güven içinde "
                "akışını sağlamak için konulmuş her türlü işareti değiştirerek. "
                "(2) Kara, deniz, hava veya demiryolu ulaşım araçlarını tehlikeli olabilecek "
                "şekilde sevk ve idare eden kişi cezalandırılır."
            ),
        )
    ]
    answer = _build_extractive_answer(
        "Bu maddenin birinci ve ikinci fıkraları nasıl ayrılır?\nKonu: TCK m.179",
        evidence,
    )
    assert "usul kuralı" not in answer.lower()
    assert "(1)" in answer or "birinci fıkra" in answer.lower()
    assert "(2)" in answer or "ikinci fıkra" in answer.lower()


def test_taksir_question_prefers_180_over_unrelated_60() -> None:
    from retrieval.research import _answer_items

    items = [
        _item(
            n=1,
            chunk_id="law:5237:article:60:v1",
            article_no="60",
            title="Tüzel kişiler hakkında güvenlik tedbirleri",
            content="Madde 60- (1) Bir kamu kurumunun verdiği izne dayalı olarak",
        ),
        _item(
            n=2,
            chunk_id="law:5237:article:179:v1",
            article_no="179",
            title="Trafik güvenliğini tehlikeye sokma",
            content="Madde 179- (1) Kara, deniz, hava veya demiryolu",
        ),
        _item(
            n=3,
            chunk_id="law:5237:article:180:v1",
            article_no="180",
            title="Trafik güvenliğini taksirle tehlikeye sokma",
            content="Madde 180- (1) Taksirle, Trafik güvenliğini tehlikeye sokma",
        ),
    ]
    picked = _answer_items(
        "Taksirle işlenmesi TCK m.180’de mi, yoksa 179 kapsamında mı kalır?",
        items,
    )
    assert picked[0].article_no == "180"
    answer = _build_extractive_answer(
        "Taksirle işlenmesi TCK m.180’de mi, yoksa 179 kapsamında mı kalır?",
        items,
    )
    assert "TCK m.180" in answer
    assert "usul kuralı" not in answer.lower()
    assert "tüzel" not in answer.lower()


def test_mentions_foreign_article() -> None:
    from retrieval.research import _mentions_foreign_article

    assert _mentions_foreign_article("TCK m.158 kapsamında [1].", {"158", "157"}) is False
    assert _mentions_foreign_article("Banka hesabı TCK m.245’tedir [2].", {"158", "157"}) is True


def test_extractive_answer_labels_court_decision() -> None:
    from retrieval.research import EvidenceItem

    evidence = [
        EvidenceItem(
            n=1,
            chunk_id="decision:yargitay:2023:2023/1:2023/2:v1",
            document_id="decision:yargitay:2023:2023/1:2023/2",
            law_no=None,
            article_no="2023/2",
            title="7. Ceza Dairesi — dolandırıcılık",
            content="Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verilmiştir.",
            authority="official",
            bm25_rank=2,
            semantic_rank=1,
            rrf_rank=1,
            rrf_score=0.02,
            retrievers=["bm25", "semantic"],
            used_in_answer=True,
        )
    ]
    answer = _build_extractive_answer("nitelikli dolandırıcılık", evidence)
    assert "7. Ceza Dairesi" in answer
    assert "[1]" in answer
    assert "TCK Madde 2023/2" not in answer


def test_research_reasoning_has_hops() -> None:
    from retrieval.research import build_research_reasoning

    hops = build_research_reasoning(
        "nitelikli dolandırıcılık",
        [
            _item(n=1, bm25_rank=1, semantic_rank=1, used_in_answer=True),
        ],
        route="hybrid",
        answer="Nitelikli dolandırıcılık TCK m.158’de düzenlenir [1].",
    )
    assert hops["status"] == "solid"
    assert [row["id"] for row in hops["hops"]] == ["sorgu", "bm25", "vektor", "rrf", "cevap"]
    assert "TCK m.158" in hops["hops"][3]["answer"]
    assert hops["hops"][4]["answer"].startswith("Gerekçe aşağıda")
    assert hops["conclusion"] is None


def test_off_topic_query_is_not_supported() -> None:
    from retrieval.research import _query_supported

    noise = _item(
        n=1,
        article_no="129",
        title="Haksız fiil nedeniyle veya karşılıklı hakaret",
        content="Madde 129- (1) Haksız bir fiile tepki olarak,",
        bm25_rank=None,
        semantic_rank=1,
        retrievers=["semantic"],
    )
    assert _query_supported("fenerbahçe maçı ne olur", [noise]) is False
    assert _query_supported("hava durumu nasıl", [noise]) is False
    assert _query_supported("nitelikli dolandırıcılıkta banka hesabı", [_item()]) is True
    assert _query_supported("hakaret suçu", [noise]) is True


def test_refuse_answer_does_not_cite_law() -> None:
    from retrieval.research import _refuse_answer

    text = _refuse_answer()
    assert "TCK" not in text
    assert "m.129" not in text
    assert "hukuk" in text.lower()
    assert "Fenerbahçe" not in text


def test_off_topic_reasoning_does_not_pick_article() -> None:
    from retrieval.research import build_research_reasoning

    hops = build_research_reasoning(
        "fenerbahçe maçı ne olur",
        [
            _item(
                n=1,
                article_no="129",
                title="Haksız fiil nedeniyle veya karşılıklı hakaret",
                bm25_rank=None,
                semantic_rank=1,
                used_in_answer=False,
            )
        ],
        route="hybrid",
        answer="Bu sorgu hukuk araştırmasına uygun değil.",
        refused=True,
    )
    assert hops["status"] == "fragile"
    assert "m.129" not in hops["hops"][3]["answer"]
    assert "hukuk" in hops["hops"][4]["answer"].lower()
    assert hops["hops"][4]["state"] == "warn"


def test_garbage_placeholder_is_not_usable() -> None:
    from retrieval.research import _usable_draft

    blob = (
        "Evet: Fenerbahçe maçı [yaygın ad] takımına karşı [yaygın ad] skorla galip gelir [1]. "
        * 12
    )
    assert len(blob) >= 420
    assert _usable_draft(blob, {"evidence": [{"article_no": "129"}]}) is False


def _long_draft(article: str = "158") -> str:
    return (
        "Sonuç\n\n"
        f"Evet: sorulan olgu TCK m.{article} kapsamında nitelikli dolandırıcılık olarak değerlendirilir [1]. "
        "Madde, banka veya kredi kurumunun araç olarak kullanıldığı hâlleri temel şekilden ayırır [1]. "
        "Uygulama, bu seçeneğin somut olayda gerçekleşmesine bağlıdır [1].\n\n"
        "Hukuki dayanak\n\n"
        "1. TCK m.158, dolandırıcılığın bilişim sistemleri ile banka veya kredi kurumları kullanılarak işlenmesini nitelikli hâl sayar [1]. Lafız, bu seçeneği ağırlaştırıcı bir yol olarak kurar [1].\n"
        "2. Bu seçimlik hareket gerçekleştiğinde fiil, temel dolandırıcılıktan ayrı bir ağırlaştırılmış hâlde kalır [1]. Kanun koyucu bu yolu nitelikli şekil saymıştır [1].\n"
        "3. Temel şekil TCK m.157’de düzenlenir; nitelikli seçenekler 158’de toplanır [3]. 157 hile ve zarar unsurlarını, 158 ise belirli araçları ekler [3].\n"
        "4. Hesabın araç olarak kullanılması, hileli temin veya zararın gerçekleşmesinde vasıta işlevi görmeyi gerektirir [1]. Salt hesap sahibi olmak bu seçeneği doldurmaz [1].\n"
        "5. Nitelikli hâlin yanında temel suçun diğer unsurları da dosyadan aranır [1]. Arşiv maddesi ispatı varsaymaz [1].\n\n"
        "Değerlendirme\n\n"
        "Somut olay unsurlarının dosyadan ayrıca incelenmesi gerekir [1]. Bu metin çerçeve verir; hüküm kurmaz [1]."
    )


def test_draft_research_uses_api_when_it_writes(monkeypatch) -> None:
    from retrieval.research import _draft_research_answer

    def fake_write(module_id, engine, *, chat_fn=None, allow_ollama=True):
        assert chat_fn is None
        return _long_draft()

    monkeypatch.setattr("llm.api_client.api_configured", lambda: True)
    monkeypatch.setattr("llm.client.ping", lambda timeout=0.8: True)
    monkeypatch.setattr("llm.writer.write_module", fake_write)
    monkeypatch.setattr("llm.writer.writer_name", lambda allow_ollama=True: "api")

    text, writer, err = _draft_research_answer({"query": "banka", "evidence": [{"n": 1, "article_no": "158"}, {"n": 3, "article_no": "157"}]})
    assert writer == "api"
    assert "TCK m.158" in text
    assert err is None


def test_draft_research_falls_back_to_ollama(monkeypatch) -> None:
    from retrieval.research import _draft_research_answer

    calls: list[bool] = []

    def fake_write(module_id, engine, *, chat_fn=None, allow_ollama=True):
        calls.append(chat_fn is not None)
        if chat_fn is None:
            raise RuntimeError("LLM API 404: model decommissioned")
        return _long_draft()

    class _Cfg:
        research_allow_ollama = True

    monkeypatch.setattr("hakim_config.get_models", lambda: _Cfg())
    monkeypatch.setattr("llm.api_client.api_configured", lambda: True)
    monkeypatch.setattr("llm.client.ping", lambda timeout=0.8: True)
    monkeypatch.setattr("llm.writer.write_module", fake_write)
    monkeypatch.setattr("llm.writer.writer_name", lambda allow_ollama=True: "api")

    text, writer, err = _draft_research_answer({"query": "banka"})
    assert writer == "ollama"
    assert "TCK m.158" in text
    assert err is None
    assert calls == [False, True]


def test_draft_research_stays_extractive_when_both_fail(monkeypatch) -> None:
    from retrieval.research import _draft_research_answer

    def fake_write(module_id, engine, *, chat_fn=None, allow_ollama=True):
        raise RuntimeError("no llm")

    monkeypatch.setattr("llm.api_client.api_configured", lambda: True)
    monkeypatch.setattr("llm.client.ping", lambda timeout=0.8: True)
    monkeypatch.setattr("llm.writer.write_module", fake_write)

    text, writer, err = _draft_research_answer({"query": "banka"})
    assert text is None
    assert writer == "extractive"
    assert err and "no llm" in err


def test_draft_research_rejects_wrong_article(monkeypatch) -> None:
    from retrieval.research import _draft_research_answer

    def fake_write(module_id, engine, *, chat_fn=None, allow_ollama=True):
        return "Banka hesabının kullanılması TCK m.245’te düzenlenmiştir [2]."

    monkeypatch.setattr("llm.api_client.api_configured", lambda: True)
    monkeypatch.setattr("llm.client.ping", lambda timeout=0.8: False)
    monkeypatch.setattr("llm.writer.write_module", fake_write)
    monkeypatch.setattr("llm.writer.writer_name", lambda allow_ollama=True: "api")

    text, writer, err = _draft_research_answer(
        {
            "query": "banka",
            "evidence": [{"n": 1, "article_no": "158"}, {"n": 3, "article_no": "157"}],
        }
    )
    assert text is None
    assert writer == "extractive"
    assert err


def test_draft_research_rejects_short_answer(monkeypatch) -> None:
    from retrieval.research import _draft_research_answer

    def fake_write(module_id, engine, *, chat_fn=None, allow_ollama=True):
        return "Evet, TCK m.158 kapsamındadır [1]."

    monkeypatch.setattr("llm.api_client.api_configured", lambda: True)
    monkeypatch.setattr("llm.client.ping", lambda timeout=0.8: False)
    monkeypatch.setattr("llm.writer.write_module", fake_write)
    monkeypatch.setattr("llm.writer.writer_name", lambda allow_ollama=True: "api")

    text, writer, err = _draft_research_answer(
        {"query": "banka", "evidence": [{"n": 1, "article_no": "158"}]}
    )
    assert text is None
    assert writer == "extractive"
    assert err
