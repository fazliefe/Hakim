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


def test_extractive_answer_uses_distinct_citation_numbers() -> None:
    evidence = [
        _item(
            n=1,
            content=(
                "Madde 158- (1) Dolandırıcılık suçunun; f) Bilişim sistemlerinin, "
                "banka veya kredi kurumlarının araç olarak kullanılması suretiyle,"
            ),
        ),
        _item(
            n=2,
            chunk_id="law:5237:article:157:v1",
            article_no="157",
            title="Dolandırıcılık",
            content="Madde 157- (1) Hileli davranışlarla bir kimseyi aldatıp,",
        ),
    ]
    answer = _build_extractive_answer("nitelikli dolandırıcılıkta banka hesabı", evidence)
    assert "[1]" in answer
    assert "[2]" in answer
    assert "TCK m.157" in answer
    assert "[1] TCK m.158" in answer
    assert "[2] TCK m.157" in answer


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
    assert _query_supported("yaprak sarma", [noise]) is False
    assert _query_supported("nitelikli dolandırıcılıkta banka hesabı", [_item()]) is True
    assert _query_supported("hakaret suçu", [noise]) is True


def test_refuse_answer_does_not_cite_law() -> None:
    from retrieval.research import _refuse_answer

    text = _refuse_answer()
    assert "TCK" not in text
    assert "m.129" not in text
    assert "hukuk" in text.lower()
    assert "Fenerbahçe" not in text
    assert "spor" not in text.lower()
    assert "yaprak" not in text.lower()


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


def _aym_basvuru_item(**kwargs) -> EvidenceItem:
    return _item(
        n=kwargs.get("n", 1),
        chunk_id="decision:aym:2025:2023/73303:2023/73303:v1",
        document_id="decision:aym:2025:2023/73303:2023/73303",
        law_no=None,
        article_no="2023/73303",
        title="MURAT YILMAZ",
        content=(
            "Başvuru Numarası : 2023/73303\nKarar Tarihi : 10/12/2025\n"
            "TÜRKİYE CUMHURİYETİ\nANAYASA MAHKEMESİ\nİKİNCİ BÖLÜM\nKARAR\n"
            "MURAT YILMAZ BAŞVURUSU\nBaşvurucu : Murat YILMAZ\n"
        ),
        **{k: v for k, v in kwargs.items() if k != "n"},
    )


def test_petition_like_aym_basvuru_is_not_a_research_source() -> None:
    from retrieval.research import _is_petition_like

    assert _is_petition_like(_aym_basvuru_item()) is True
    assert _is_petition_like(_item()) is False
    yargitay = _item(
        n=2,
        chunk_id="decision:yargitay:2023:2023/1:2023/2:v1",
        document_id="decision:yargitay:2023:2023/1:2023/2",
        law_no=None,
        article_no="2023/2",
        title="7. Ceza Dairesi — 2023/1 E. — 2023/2 K.",
        content="Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verilmiştir.",
    )
    assert _is_petition_like(yargitay) is False


def test_answer_items_skips_dilekce_like_aym_and_uses_law() -> None:
    from retrieval.research import _answer_items

    picked = _answer_items(
        "nitelikli dolandırıcılıkta banka hesabı",
        [_aym_basvuru_item(n=1, used_in_answer=True), _item(n=2, used_in_answer=True)],
    )
    assert picked
    assert picked[0].article_no == "158"
    assert all(item.title != "MURAT YILMAZ" for item in picked)


def test_extractive_answer_does_not_quote_aym_basvuru_name() -> None:
    answer = _build_extractive_answer(
        "nitelikli dolandırıcılıkta banka hesabı",
        [_aym_basvuru_item(n=1, used_in_answer=True), _item(n=2, used_in_answer=True)],
    )
    assert "Murat" not in answer
    assert "YILMAZ" not in answer
    assert "Başvuru Numarası" not in answer
    assert "TCK m.158" in answer


def test_usable_draft_rejects_dilekce_dump() -> None:
    from retrieval.research import _usable_draft

    dump = (
        "Nitelikli dolandırıcılık TCK m.158 kapsamındadır [1]. "
        "Anayasa Mahkemesi'nin 2023/73303 sayılı Murat Yılmaz kararı dayanak alınır [2]. "
        "Başvuru Numarası : 2023/73303 Karar Tarihi : 10/12/2025 "
        "MURAT YILMAZ BAŞVURUSU. " * 8
    )
    engine = {
        "query": "nitelikli dolandırıcılık banka hesabı",
        "evidence": [{"n": 1, "article_no": "158"}],
    }
    assert _usable_draft(dump, engine) is False


def test_assemble_research_drops_aym_basvuru_from_evidence(monkeypatch) -> None:
    from retrieval.bm25 import SearchHit
    from retrieval.research import ResearchEngine, assemble_research_result
    from retrieval.rrf import FusedHit

    monkeypatch.setattr(
        "retrieval.research._draft_research_answer",
        lambda payload: (None, "extractive", None),
    )

    aym = SearchHit(
        chunk_id="decision:aym:2025:2023/73303:2023/73303:v1",
        score=12.0,
        law_no=None,
        article_no="2023/73303",
        title="MURAT YILMAZ",
        content=(
            "Başvuru Numarası : 2023/73303\nANAYASA MAHKEMESİ\n"
            "MURAT YILMAZ BAŞVURUSU\nBaşvurucu : Murat YILMAZ"
        ),
        document_id="decision:aym:2025:2023/73303:2023/73303",
        article_id=None,
        authority="official",
        rank=1,
    )
    law = SearchHit(
        chunk_id="law:5237:article:158:v1",
        score=9.0,
        law_no="5237",
        article_no="158",
        title="Nitelikli dolandırıcılık",
        content="Madde 158- (1) Dolandırıcılık suçunun; f) banka veya kredi kurumlarının araç olarak kullanılması suretiyle,",
        document_id="law:5237",
        article_id="law:5237:article:158",
        authority="official",
        rank=2,
    )
    fused = [
        FusedHit("decision:aym:2025:2023/73303:2023/73303:v1", 0.04, 1, ("bm25",), aym, 1, 2),
        FusedHit("law:5237:article:158:v1", 0.03, 2, ("bm25", "semantic"), law, 2, 1),
    ]
    engine = ResearchEngine.__new__(ResearchEngine)
    engine.evidence_limit = 8
    result = assemble_research_result(engine, "nitelikli dolandırıcılıkta banka hesabı", fused, "hybrid")
    assert all("aym" not in (item.document_id or "") for item in result.evidence)
    assert all(item.title != "MURAT YILMAZ" for item in result.evidence)
    assert "Murat" not in result.answer
    assert "TCK m.158" in result.answer


def _ticaret_bam_item(**kwargs) -> EvidenceItem:
    return _item(
        n=kwargs.get("n", 1),
        chunk_id="decision:istinafhukuk:2026:2026/1544:2026/1561:v1",
        document_id="decision:istinafhukuk:2026:2026/1544:2026/1561",
        law_no=None,
        article_no="2026/1561",
        title="Kayseri Bölge Adliye Mahkemesi 6. Hukuk Dairesi — 2026/1544 E. — 2026/1561 K.",
        content=(
            "T.C. KAYSERİ BÖLGE ADLİYE MAHKEMESİ 6. HUKUK DAİRESİ "
            "MAHKEMESİ: KAYSERİ 1. ASLİYE TİCARET MAHKEMESİ "
            "TALEBİN KONUSU: İhtiyati Tedbir vekili dilekçesiyle"
        ),
        **{k: v for k, v in kwargs.items() if k != "n"},
    )


def test_ticaret_istinaf_is_not_a_research_source() -> None:
    from retrieval.research import _exclude_from_research, _is_petition_like

    bam = _ticaret_bam_item()
    assert _exclude_from_research(bam) is True
    yargitay = _item(
        n=2,
        chunk_id="decision:yargitay:2023:2023/1:2023/2:v1",
        document_id="decision:yargitay:2023:2023/1:2023/2",
        law_no=None,
        article_no="2023/2",
        title="7. Ceza Dairesi — 2023/1 E. — 2023/2 K.",
        content="Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verilmiştir.",
    )
    assert _exclude_from_research(yargitay) is False
    assert _is_petition_like(_item()) is False


def test_civil_yargitay_chamber_is_not_a_research_source_regression() -> None:
    """Canlı doğrulanan regresyon: `_exclude_from_research` eskiden
    `llm.emsal.court_ok()` kullanıyordu — o fonksiyon YALNIZCA İşlem'in
    ceza-odaklı dilekçe emsal künyesi içindir ve "hukuk" geçip "ceza"
    geçmeyen HER kararı reddeder. Araştırma'da kullanılınca TÜM Yargıtay
    Hukuk Daireleri (medeni hukuk: tazminat, boşanma, miras, kira, iş
    hukuku...) sessizce kayboluyordu. Bu test civil (Hukuk Dairesi) bir
    Yargıtay kararının dışlanmadığını doğrular — eski kodda FAIL ederdi."""
    from retrieval.research import _exclude_from_research

    civil = _item(
        n=1,
        chunk_id="decision:yargitay:2005:2005/71:2005/102:v1",
        document_id="decision:yargitay:2005:2005/71:2005/102",
        law_no=None,
        article_no="2005/102",
        title="Hukuk Genel Kurulu — 2005/71 E. — 2005/102 K.",
        content=(
            "4. Hukuk Dairesi trafik kazası sonucu oluşan maddi ve manevi "
            "tazminat isteminin koşullarını değerlendirmiştir."
        ),
    )
    assert _exclude_from_research(civil) is False


def test_answer_items_skips_ticaret_bam_and_uses_law() -> None:
    from retrieval.research import _answer_items

    picked = _answer_items(
        "nitelikli dolandırıcılıkta banka hesabı",
        [_ticaret_bam_item(n=1, used_in_answer=True), _item(n=2, used_in_answer=True)],
    )
    assert picked[0].article_no == "158"
    assert all("istinafhukuk" not in (item.document_id or "") for item in picked)


def test_assemble_research_drops_ticaret_bam_from_evidence(monkeypatch) -> None:
    from retrieval.bm25 import SearchHit
    from retrieval.research import ResearchEngine, assemble_research_result
    from retrieval.rrf import FusedHit

    monkeypatch.setattr(
        "retrieval.research._draft_research_answer",
        lambda payload: (None, "extractive", None),
    )
    bam = SearchHit(
        chunk_id="decision:istinafhukuk:2026:2026/1544:2026/1561:v1",
        score=12.0,
        law_no=None,
        article_no="2026/1561",
        title="Kayseri Bölge Adliye Mahkemesi 6. Hukuk Dairesi — 2026/1544 E. — 2026/1561 K.",
        content="ASLİYE TİCARET MAHKEMESİ TALEBİN KONUSU: İhtiyati Tedbir vekili dilekçesiyle",
        document_id="decision:istinafhukuk:2026:2026/1544:2026/1561",
        article_id=None,
        authority="official",
        rank=1,
    )
    law = SearchHit(
        chunk_id="law:5237:article:158:v1",
        score=9.0,
        law_no="5237",
        article_no="158",
        title="Nitelikli dolandırıcılık",
        content="Madde 158- (1) Dolandırıcılık suçunun; f) banka veya kredi kurumlarının araç olarak kullanılması suretiyle,",
        document_id="law:5237",
        article_id="law:5237:article:158",
        authority="official",
        rank=2,
    )
    fused = [
        FusedHit(bam.chunk_id, 0.04, 1, ("bm25",), bam, 1, 2),
        FusedHit(law.chunk_id, 0.03, 2, ("bm25", "semantic"), law, 2, 1),
    ]
    engine = ResearchEngine.__new__(ResearchEngine)
    engine.evidence_limit = 8
    result = assemble_research_result(engine, "nitelikli dolandırıcılıkta banka hesabı", fused, "hybrid")
    assert all("istinafhukuk" not in (item.document_id or "") for item in result.evidence)
    assert "Kayseri" not in result.answer
    assert "TCK m.158" in result.answer


def test_is_count_query_detects_tck_tmk_comparison() -> None:
    from retrieval.research import _is_count_query, _laws_in_query

    assert _is_count_query("tckda mı daha fazla madde var tmkda mı daha fazla kanun var sayısal olarak ver")
    assert _is_count_query("TCK ve TMK madde sayısı")
    assert not _is_count_query("nitelikli dolandırıcılıkta banka hesabı")
    assert _laws_in_query("tckda mı tmkda mı") == ["5237", "4721"]


def test_count_answer_is_numeric_not_emsal() -> None:
    from retrieval.research import _build_count_answer

    answer = _build_count_answer(
        "tckda mı daha fazla madde var tmkda mı sayısal olarak ver",
        {"5237": 340, "4721": 1012},
    )
    assert "1012" in answer
    assert "340" in answer
    assert "TMK" in answer
    assert "TCK" in answer
    assert "emsal karardır" not in answer
    assert "[1]" in answer
    assert "[2]" in answer


def test_answer_items_keeps_distinct_laws() -> None:
    from retrieval.research import _answer_items

    picked = _answer_items(
        "tck tmk madde",
        [
            _item(n=1, used_in_answer=True),
            _item(
                n=2,
                chunk_id="law:4721:article:555:v1",
                document_id="law:4721",
                law_no="4721",
                article_no="555",
                title="Havale",
                content="Madde 555- Havale, havale edenin...",
                used_in_answer=True,
            ),
        ],
    )
    assert {item.law_no for item in picked} == {"5237", "4721"}


def test_spread_cites_uses_second_source_in_body() -> None:
    from retrieval.research import _spread_cites

    text = (
        "Sonuç\n\nA cümle [1]. B cümle [1]. C cümle [1].\n\n"
        "Hukuki dayanak\n\n1. Dayanak [1].\n2. Dayanak [1].\n\n"
        "Kaynak\n[1] TCK m.158\n[2] TMK m.555"
    )
    out = _spread_cites(text, [_item(n=1), _item(n=2, article_no="555", law_no="4721", chunk_id="law:4721:article:555:v1", document_id="law:4721")])
    body, kaynak = out.split("\n\nKaynak\n", 1)
    assert "[2]" in body
    assert "[1] TCK m.158" in kaynak
    assert "[2] TMK m.555" in kaynak


def test_align_citation_numbers_is_dense_and_puts_picked_first() -> None:
    from retrieval.research import _align_citation_numbers

    tbk = _item(
        n=1,
        chunk_id="law:6098:article:555:v1",
        document_id="law:6098",
        law_no="6098",
        article_no="555",
        title="Havale",
        content="Madde 555- Havale, havale edenin...",
    )
    tck = _item(
        n=3,
        chunk_id="law:5237:article:245:v1",
        article_no="245",
        title="Banka veya kredi kartlarının kötüye kullanılması",
        content="Madde 245- (1) Başkasına ait bir banka veya kredi kartını,",
    )
    ay = _item(
        n=6,
        chunk_id="law:2709:article:14:v1",
        document_id="law:2709",
        law_no="2709",
        article_no="14",
        title="Temel hak ve hürriyetlerin kötüye kullanılamaması",
        content="Madde 14- (1) Anayasada yer alan hak ve hürriyetlerden hiçbiri,",
    )
    aligned = _align_citation_numbers([tbk, tck, ay], [tck, tbk])
    assert [item.n for item in aligned] == [1, 2, 3]
    assert [item.article_no for item in aligned] == ["245", "555", "14"]
    assert aligned[0].used_in_answer is True
    assert aligned[1].used_in_answer is True
    assert aligned[2].used_in_answer is False


def test_keep_cited_evidence_drops_uncited_ranks() -> None:
    from retrieval.research import _keep_cited_evidence

    kept = _keep_cited_evidence(
        [
            _item(n=1),
            _item(
                n=2,
                chunk_id="law:2709:article:14:v1",
                document_id="law:2709",
                law_no="2709",
                article_no="14",
                title="AY",
            ),
            _item(
                n=6,
                chunk_id="law:6098:article:40:v1",
                document_id="law:6098",
                law_no="6098",
                article_no="40",
                title="Sorumluluk",
                used_in_answer=False,
            ),
        ],
        "Sonuç\n\nA [1]. B [2].\n\nKaynak\n[1] TCK m.245\n[2] AY m.14\n[6] TBK m.40",
    )
    assert [item.n for item in kept] == [1, 2]
    assert all(item.used_in_answer for item in kept)


def test_reserve_decisions_survives_evidence_limit_truncation() -> None:
    """Canlı doğrulanan regresyon: `HybridSearcher.fuse()` kendi (daha
    geniş) havuzunda kararlara yer ayırsa da, kararlar düşük ham RRF
    skoru yüzünden havuzun sonuna düşüyor — DAHA DAR `evidence_limit`
    kesmesi (fuse()'un limit'inden küçük) onları yeniden dışarı
    atıyordu. Bu test, 10 kanun maddesi + 3 karardan oluşan 13'lük bir
    havuzun evidence_limit=8'e kesilirken en az 3 kararı koruduğunu
    doğrular — eski kodda (salt `hits[:limit]`) FAIL ederdi."""
    from retrieval.bm25 import SearchHit
    from retrieval.research import _reserve_decisions
    from retrieval.rrf import FusedHit

    laws = [
        FusedHit(
            f"law-{i}",
            1.0 - i * 0.01,
            i,
            ("bm25", "semantic"),
            SearchHit(f"law-{i}", 1.0, "6098", str(i), None, "madde", "law:6098", None, "official", i),
            i,
            i,
        )
        for i in range(1, 11)
    ]
    decisions = [
        FusedHit(
            f"dec-{i}",
            0.3 - i * 0.01,
            10 + i,
            ("bm25_decisions",),
            SearchHit(f"dec-{i}", 1.0, None, None, f"Karar {i}", "karar", f"decision:yargitay:{i}", None, "decision", i),
            None,
            None,
        )
        for i in range(1, 4)
    ]
    result = _reserve_decisions(laws + decisions, limit=8)
    assert len(result) == 8
    kept_decisions = [h for h in result if h.hit.document_id.startswith("decision:")]
    assert len(kept_decisions) == 3


def test_reserve_decisions_no_op_when_pool_fits() -> None:
    from retrieval.bm25 import SearchHit
    from retrieval.research import _reserve_decisions
    from retrieval.rrf import FusedHit

    laws = [
        FusedHit(
            f"law-{i}",
            1.0,
            i,
            ("bm25",),
            SearchHit(f"law-{i}", 1.0, "6098", str(i), None, "madde", "law:6098", None, "official", i),
            i,
            None,
        )
        for i in range(1, 4)
    ]
    result = _reserve_decisions(laws, limit=8)
    assert result == laws


def test_keep_cited_evidence_keeps_uncited_decisions() -> None:
    from retrieval.research import _keep_cited_evidence

    karar = _item(
        n=5,
        chunk_id="decision:yargitay:2023:2023/1:2023/2:v1",
        document_id="decision:yargitay:2023:2023/1:2023/2",
        law_no=None,
        article_no="2023/2",
        title="7. Ceza Dairesi — 2023/1 E. — 2023/2 K.",
        content="Sanığın mahkûmiyetine karar verilmiştir.",
        used_in_answer=False,
    )
    kept = _keep_cited_evidence(
        [_item(n=1), karar],
        "Sonuç\n\nA [1].\n\nKaynak\n[1] TCK m.158",
    )
    assert [item.n for item in kept] == [1, 2]
    assert kept[0].used_in_answer is True
    assert kept[1].used_in_answer is False
    assert (kept[1].document_id or "").startswith("decision:")


def test_extractive_answer_uses_dense_cites_when_ranks_are_sparse() -> None:
    evidence = [
        _item(
            n=1,
            chunk_id="law:6098:article:555:v1",
            document_id="law:6098",
            law_no="6098",
            article_no="555",
            title="Havale",
            content="Madde 555- Havale, havale edenin...",
        ),
        _item(
            n=3,
            chunk_id="law:5237:article:245:v1",
            article_no="245",
            title="Banka veya kredi kartlarının kötüye kullanılması",
            content="Madde 245- (1) Başkasına ait bir banka veya kredi kartını izinsiz kullanarak,",
        ),
        _item(
            n=6,
            chunk_id="law:2709:article:14:v1",
            document_id="law:2709",
            law_no="2709",
            article_no="14",
            title="Temel hak ve hürriyetlerin kötüye kullanılamaması",
            content="Madde 14- (1) Anayasada yer alan hak ve hürriyetlerden hiçbiri,",
        ),
    ]
    answer = _build_extractive_answer("banka hesabından izinsiz para çekme", evidence)
    body, kaynak = answer.split("\n\nKaynak\n", 1)
    cites = [int(n) for n in re.findall(r"\[(\d+)\]", body)]
    assert cites
    assert 6 not in cites
    assert max(cites) <= 3
    assert "[6]" not in kaynak
    assert "[1]" in body
    assert "[3]" in body


def test_assemble_research_renumbers_sparse_ranks(monkeypatch) -> None:
    from retrieval.bm25 import SearchHit
    from retrieval.research import ResearchEngine, assemble_research_result
    from retrieval.rrf import FusedHit

    monkeypatch.setattr(
        "retrieval.research._draft_research_answer",
        lambda payload: (None, "extractive", None),
    )

    tbk = SearchHit(
        chunk_id="law:6098:article:555:v1",
        score=12.0,
        law_no="6098",
        article_no="555",
        title="Havale",
        content="Madde 555- Havale, havale edenin bir bedeli...",
        document_id="law:6098",
        article_id="law:6098:article:555",
        authority="official",
        rank=1,
    )
    tck = SearchHit(
        chunk_id="law:5237:article:245:v1",
        score=11.0,
        law_no="5237",
        article_no="245",
        title="Banka veya kredi kartlarının kötüye kullanılması",
        content="Madde 245- (1) Başkasına ait bir banka veya kredi kartını izinsiz kullanarak,",
        document_id="law:5237",
        article_id="law:5237:article:245",
        authority="official",
        rank=3,
    )
    ay = SearchHit(
        chunk_id="law:2709:article:14:v1",
        score=8.0,
        law_no="2709",
        article_no="14",
        title="Temel hak ve hürriyetlerin kötüye kullanılamaması",
        content="Madde 14- (1) Anayasada yer alan hak ve hürriyetlerden hiçbiri,",
        document_id="law:2709",
        article_id="law:2709:article:14",
        authority="official",
        rank=6,
    )
    fused = [
        FusedHit("law:6098:article:555:v1", 0.05, 1, ("bm25",), tbk, 1, 2),
        FusedHit("law:5237:article:245:v1", 0.04, 3, ("bm25", "semantic"), tck, 3, 1),
        FusedHit("law:2709:article:14:v1", 0.02, 6, ("bm25",), ay, 6, 5),
    ]
    engine = ResearchEngine.__new__(ResearchEngine)
    engine.evidence_limit = 8
    result = assemble_research_result(
        engine,
        "TCK m.245 banka kartı kötüye kullanma",
        fused,
        "hybrid",
    )
    assert [item.article_no for item in result.evidence] == ["245"]
    assert [item.n for item in result.evidence] == [1]
    assert all(item.used_in_answer for item in result.evidence)
    body = result.answer.split("\n\nKaynak\n")[0]
    cites = [int(n) for n in re.findall(r"\[(\d+)\]", body)]
    assert 6 not in cites
    assert max(cites) <= 1
    payload_ns = []

    def capture(payload):
        payload_ns.extend(item["n"] for item in payload.get("evidence") or [])
        return None, "extractive", None

    monkeypatch.setattr("retrieval.research._draft_research_answer", capture)
    assemble_research_result(engine, "TCK m.245 banka kartı kötüye kullanma", fused, "hybrid")
    assert payload_ns == list(range(1, len(payload_ns) + 1))
    assert 6 not in payload_ns


def test_assemble_rewrites_sparse_llm_cites(monkeypatch) -> None:
    from retrieval.bm25 import SearchHit
    from retrieval.research import ResearchEngine, assemble_research_result
    from retrieval.rrf import FusedHit

    draft = (
        "Sonuç\n\n"
        "Kartın rızasız kullanılması TCK m.245 kapsamındadır [3]. "
        "Hesaptan para çekme aynı maddenin unsurlarını doldurur [3]. "
        "Yarar sağlama unsuru da aranır [3].\n\n"
        "Hukuki dayanak\n\n"
        "1. Kartın kötüye kullanılması [3].\n"
        "2. Rıza dışı zilyetlik [3].\n"
        "3. Yarar sağlama [3].\n\n"
        "Kaynak\n"
        "[1] TBK m.555\n[3] TCK m.245\n[6] AY m.14"
    )

    def fake_draft(payload):
        assert [item["n"] for item in payload["evidence"]] == [1, 2, 3]
        return draft, "api", None

    monkeypatch.setattr("retrieval.research._draft_research_answer", fake_draft)

    def law(law_no, article, title, content, rank):
        return SearchHit(
            chunk_id=f"law:{law_no}:article:{article}:v1",
            score=12.0 - rank,
            law_no=law_no,
            article_no=str(article),
            title=title,
            content=content,
            document_id=f"law:{law_no}",
            article_id=f"law:{law_no}:article:{article}",
            authority="official",
            rank=rank,
        )

    tbk = law("6098", "555", "Havale", "Madde 555- Havale, havale edenin bir bedeli...", 1)
    tck = law(
        "5237",
        "245",
        "Banka veya kredi kartlarının kötüye kullanılması",
        "Madde 245- (1) Başkasına ait bir banka veya kredi kartını izinsiz kullanarak,",
        3,
    )
    ay = law(
        "2709",
        "14",
        "Temel hak ve hürriyetlerin kötüye kullanılamaması",
        "Madde 14- (1) Anayasada yer alan hak ve hürriyetlerden hiçbiri,",
        6,
    )
    fused = [
        FusedHit(tbk.chunk_id, 0.05, 1, ("bm25",), tbk, 1, 2),
        FusedHit(tck.chunk_id, 0.04, 3, ("bm25", "semantic"), tck, 3, 1),
        FusedHit(ay.chunk_id, 0.02, 6, ("bm25",), ay, 6, 5),
    ]
    engine = ResearchEngine.__new__(ResearchEngine)
    engine.evidence_limit = 8
    result = assemble_research_result(
        engine,
        "banka hesabından izinsiz para çekme",
        fused,
        "hybrid",
    )
    body, kaynak = result.answer.split("\n\nKaynak\n", 1)
    cites = [int(n) for n in re.findall(r"\[(\d+)\]", body)]
    assert cites == [1, 2, 3, 1, 2, 3]
    assert "[6]" not in result.answer
    assert "[1]" in kaynak
    assert "[2]" in kaynak
    assert "[3]" in kaynak
    assert result.evidence[0].n == 1
    assert all(item.used_in_answer for item in result.evidence)
    assert all(item.n <= 3 for item in result.evidence)
    assert {item.article_no for item in result.evidence} <= {"555", "245", "14"}
