from __future__ import annotations

from retrieval.mapping import detect_mulga_warning


def test_detect_mulga_warning_partial_fikra() -> None:
    content = (
        "Madde 141- (1) Zilyedinin rızası olmadan başkasına ait taşınır bir "
        "malı alan kimseye bir yıldan üç yıla kadar hapis cezası verilir.\n"
        "(2) (Mülga: 2/7/2012-6352/105 md.)\n"
        "Nitelikli hırsızlık"
    )
    warning = detect_mulga_warning(content)
    assert warning is not None
    assert "kısmı mülga" in warning
    assert "Mülga: 2/7/2012-6352/105 md." in warning


def test_detect_mulga_warning_handles_no_space_before_colon() -> None:
    content = "Madde 291- (1) Temyiz istemi...\n(2) (Mülga:2/3/2024-7499/19 md.)"
    warning = detect_mulga_warning(content)
    assert warning is not None
    assert "Mülga:2/3/2024-7499/19 md." in warning


def test_detect_mulga_warning_whole_article() -> None:
    content = "Madde 55- (Mülga: 2/7/2012-6352/105 md.)"
    warning = detect_mulga_warning(content)
    assert warning is not None
    assert "tamamen mülga" in warning


def test_detect_mulga_warning_none_when_clean() -> None:
    content = "Madde 141- (1) Zilyedinin rızası olmadan başkasına ait taşınır bir malı alan kimseye ceza verilir."
    assert detect_mulga_warning(content) is None


def test_detect_mulga_warning_empty_content() -> None:
    assert detect_mulga_warning("") is None
    assert detect_mulga_warning(None) is None  # type: ignore[arg-type]


def test_detect_mulga_warning_decision_wording_differs_from_article() -> None:
    """Regresyon: canlı doğrulandı — arşivdeki 1.240 karar (çoğu eski
    Yargıtay kararı, 765 sayılı mülga TCK'ya atıf yapan) bu taramayı
    tetikliyordu, ama "Bu madde... mülga" ifadesi bir KARARIN kendisi için
    yanıltıcıydı — karar mülga olmaz, kararın andığı bir hüküm mülga olmuş
    olabilir."""
    content = (
        "12. Hukuk Dairesi 1997/7423 E., 1997/8321 K.\n"
        "2004 S. İCRA VE İFLAS KANUNU (MÜLGA) [ Madde 19 ]"
    )
    article_warning = detect_mulga_warning(content, is_decision=False)
    decision_warning = detect_mulga_warning(content, is_decision=True)
    assert article_warning is not None and "Bu maddenin" in article_warning
    assert decision_warning is not None
    assert "Bu kararda atıfta bulunulan" in decision_warning
    assert "Bu maddenin" not in decision_warning


def test_detect_mulga_warning_decision_whole_article_wording() -> None:
    content = "(Mülga: 2/7/2012-6352/105 md.)"
    warning = detect_mulga_warning(content, is_decision=True)
    assert warning is not None
    assert "Bu kararda atıfta bulunulan hükümler" in warning
    assert "Bu madde" not in warning
