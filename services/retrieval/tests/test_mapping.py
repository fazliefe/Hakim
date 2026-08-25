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
