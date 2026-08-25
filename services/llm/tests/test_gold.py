from __future__ import annotations

from collections import Counter

from llm.formats import validate_belge
from llm.gold import GOLD_PATH, accept_row, fewshot_for, load_gold
from llm.prompt import belge_messages


def test_gold_file_is_accepted_seed() -> None:
    assert GOLD_PATH.exists(), "data/gold/dilekce_ornekleri.jsonl yok"
    rows = load_gold()
    assert len(rows) >= 70
    actions = Counter(r["action"] for r in rows)
    sources = Counter((r.get("emsal") or {}).get("source") for r in rows)
    assert actions["bireysel_basvuru"] >= 20
    assert actions["idari_dava"] >= 25
    assert actions["temyiz"] >= 25
    assert "aym_bb" in sources and "danistay" in sources and "yargitay" in sources
    assert "aym_norm" not in sources
    for row in rows:
        court = str((row.get("emsal") or {}).get("court") or "").lower()
        assert "ticaret" not in court
        assert validate_belge(row["action"], row["dilekce"]) == []


def test_accept_row_drops_ticaret_and_aym_norm() -> None:
    base = load_gold()[0]
    bad_court = {
        **base,
        "emsal": {**(base.get("emsal") or {}), "court": "İstanbul 15. Asliye Ticaret Mahkemesi", "source": "emsal"},
    }
    bad_norm = {**base, "emsal": {**(base.get("emsal") or {}), "source": "aym_norm"}}
    assert accept_row(base) is True
    assert accept_row(bad_court) is False
    assert accept_row(bad_norm) is False


def test_fewshot_for_known_and_missing_actions() -> None:
    shot = fewshot_for("bireysel_basvuru")
    assert shot is not None
    assert "Emsal künye" in shot["user"]
    assert "makam" in shot["assistant"]
    temyiz = fewshot_for("temyiz")
    assert temyiz is not None
    assert "esas" in temyiz["user"].lower() or "Emsal künye" in temyiz["user"]
    assert fewshot_for("istinaf") is None


def test_belge_messages_inserts_gold_turn() -> None:
    aym = belge_messages("bireysel_basvuru", {"action": "bireysel_basvuru", "user_text": "başvuru"})
    assert len(aym) == 4
    assert aym[1]["role"] == "user"
    assert aym[2]["role"] == "assistant"
    assert "Emsal künye" in aym[1]["content"]

    temyiz = belge_messages("temyiz", {"action": "temyiz", "user_text": "temyiz"})
    assert len(temyiz) == 4
    assert "Emsal künye" in temyiz[1]["content"]

    istinaf = belge_messages("istinaf", {"action": "istinaf", "user_text": "istinaf"})
    assert len(istinaf) == 2
    assert istinaf[0]["role"] == "system"
    assert istinaf[1]["role"] == "user"
