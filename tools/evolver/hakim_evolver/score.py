"""Taslak kalite sinyali. prompt.py / writer.py yerini almaz; künye uydurmaz."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIE_RE = re.compile(r"bu yönde değerlendirme|aynı emsale dayanır", re.I)
ESAS_RE = re.compile(r"\d{4}/\d+")
IYUK_RE = re.compile(r"\bİYUK\b|\bIYUK\b", re.I)
CMK_RE = re.compile(r"\bCMK\b")
TICARET_RE = re.compile(r"ticaret mahkemesi|rekabet kurumu", re.I)
CEZA_YOL = {"temyiz", "istinaf", "itiraz", "adli_kontrol_itiraz"}
IDARI = {"idari_dava"}

GEP_DIR = Path(__file__).resolve().parents[1] / "gep"


def _allowed_esas(emsal: list[dict[str, Any]] | None) -> set[str]:
    tokens: set[str] = set()
    for item in emsal or []:
        blob = " ".join(str(item.get(key) or "") for key in ("esas_no", "karar_no", "atif"))
        tokens.update(ESAS_RE.findall(blob))
    return tokens


def score_draft(
    text: str,
    *,
    belge_id: str = "",
    parsed: dict[str, Any] | None = None,
    emsal: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    blob = str(text or "")
    kind = (belge_id or str((parsed or {}).get("id") or "")).strip().lower()
    signals: list[str] = []
    suggestions: list[str] = []
    held: list[str] = []

    if LIE_RE.search(blob):
        signals.append("lie_bu_yonde")
        suggestions.append(
            "«bu yönde değerlendirme» yasak. prompt.py USER_EMSAL_RULE duruyor; "
            "prompt değişikliği insan onayı ister."
        )
    else:
        held.append("gene_no_bu_yonde")

    allowed = _allowed_esas(emsal)
    found = set(ESAS_RE.findall(blob))
    invented = sorted(found - allowed)
    if invented:
        signals.append("invented_kunye")
        suggestions.append(
            f"Listede olmayan künye: {', '.join(invented)}. emsal_atif boş kalmalı veya canlı hit."
        )
    else:
        held.append("gene_no_invented_kunye")

    if kind in CEZA_YOL and IYUK_RE.search(blob):
        signals.append("iyuk_on_ceza_yol")
        suggestions.append("Temyiz/istinaf/itirazda İYUK kullanma; CMK usulü.")
    elif kind in CEZA_YOL:
        held.append("gene_cmk_not_iyuk")

    if kind in IDARI and CMK_RE.search(blob):
        signals.append("cmk_on_idari")
        suggestions.append("İdari davada CMK değil İYUK.")
    elif kind in IDARI:
        held.append("gene_iyuk_not_cmk")

    if kind in CEZA_YOL | IDARI | {"sikayet", "bireysel_basvuru"} and TICARET_RE.search(blob):
        signals.append("ticaret_emsal")
        suggestions.append("Ticaret/Rekabet ilamı ceza dilekçesine emsal değil.")
    else:
        held.append("gene_no_ticaret_emsal")

    fails = len(signals)
    score = max(0.0, round(1.0 - 0.25 * fails, 2))
    return {
        "ok": fails == 0,
        "score": score,
        "belge_id": kind,
        "signals": signals,
        "genes_held": held,
        "suggestions": suggestions,
        "source": "hakim_evolver",
        "prompt_edit": "human_approval_required",
    }


def record_event(report: dict[str, Any]) -> Path:
    GEP_DIR.mkdir(parents=True, exist_ok=True)
    path = GEP_DIR / "events.jsonl"
    event = {
        "type": "EvolutionEvent",
        "id": f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "repair" if not report.get("ok") else "optimize",
        "signals": report.get("signals") or [],
        "genes": report.get("genes_held") or [],
        "outcome": {
            "status": "success" if report.get("ok") else "failed",
            "score": report.get("score"),
        },
        "belge_id": report.get("belge_id"),
        "suggestions": report.get("suggestions") or [],
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path


def score_and_record(
    text: str,
    *,
    belge_id: str = "",
    parsed: dict[str, Any] | None = None,
    emsal: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report = score_draft(text, belge_id=belge_id, parsed=parsed, emsal=emsal)
    try:
        record_event(report)
    except OSError:
        pass
    return report
