from __future__ import annotations

from hakim_evolver.score import score_draft


def test_score_accepts_clean_temyiz() -> None:
    text = (
        "Yargıtay ilgili ceza dairesine. Temyiz süresi CMK m.291 uyarınca iki haftadır. "
        "Kararın bozulması talep olunur."
    )
    report = score_draft(text, belge_id="temyiz", emsal=[])
    assert report["ok"] is True
    assert "gene_no_bu_yonde" in report["genes_held"]
    assert report["prompt_edit"] == "human_approval_required"


def test_score_flags_bu_yonde_lie() -> None:
    text = (
        "Benzer uyuşmazlıkta 1. Ceza Dairesi — 2022/13957 E. — 2024/2429 K. "
        "bu yönde değerlendirme yapmıştır; dilekçe sahibi aynı emsale dayanır."
    )
    report = score_draft(text, belge_id="temyiz", emsal=[])
    assert report["ok"] is False
    assert "lie_bu_yonde" in report["signals"]
    assert "invented_kunye" in report["signals"]


def test_score_keeps_listed_kunye() -> None:
    text = "Dayanılan emsal: Yargıtay 11. Ceza Dairesi, 2018/334 esas, 2018/891 karar ilam"
    report = score_draft(
        text,
        belge_id="temyiz",
        emsal=[{"atif": "Yargıtay 11. Ceza Dairesi, 2018/334 esas, 2018/891 karar ilam", "esas_no": "2018/334", "karar_no": "2018/891"}],
    )
    assert "invented_kunye" not in report["signals"]


def test_score_flags_iyuk_on_temyiz() -> None:
    report = score_draft("Başvuru İYUK m.7 hükümlerine tabidir.", belge_id="temyiz")
    assert "iyuk_on_ceza_yol" in report["signals"]
