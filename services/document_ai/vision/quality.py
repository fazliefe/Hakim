from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image, ImageOps

from hakim_legal_schema.document import QualityIssue, QualityReport, QualityStatus


def assess_image(data: bytes, *, page: int = 1) -> QualityReport:
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image)
        rgb = image.convert("RGB")
    except Exception:
        return QualityReport(
            quality_score=0.0,
            status=QualityStatus.UNUSABLE,
            issues=[
                QualityIssue(
                    type="unreadable",
                    severity="high",
                    page=page,
                    message="Görüntü açılamadı. Dosya bozuk olabilir.",
                )
            ],
        )

    width, height = rgb.size
    gray = np.asarray(rgb.convert("L"), dtype=np.float32)
    issues: list[QualityIssue] = []
    score = 1.0

    if min(width, height) < 700:
        issues.append(
            QualityIssue(
                type="low_resolution",
                severity="high" if min(width, height) < 400 else "medium",
                page=page,
                message=f"Çözünürlük düşük ({width}×{height}). Belgeyi daha yakından çekin.",
            )
        )
        score -= 0.25

    gx = np.diff(gray, axis=1) if width >= 2 else np.array([], dtype=np.float32)
    gy = np.diff(gray, axis=0) if height >= 2 else np.array([], dtype=np.float32)
    if gx.size == 0 or gy.size == 0:
        sharpness = 0.0
    else:
        sharpness = float(np.var(gx) + np.var(gy))
        if not np.isfinite(sharpness):
            sharpness = 0.0
    if sharpness < 18:
        issues.append(
            QualityIssue(
                type="blur",
                severity="high",
                page=page,
                message="Görüntü bulanık. Sabit tutup yeniden çekin.",
            )
        )
        score -= 0.45
    elif sharpness < 70:
        issues.append(
            QualityIssue(
                type="blur",
                severity="medium",
                page=page,
                message="Hafif bulanıklık var; tarih ve sayı alanları zayıf okunabilir.",
            )
        )
        score -= 0.2

    mean = float(np.mean(gray))
    if mean < 42:
        issues.append(
            QualityIssue(
                type="too_dark",
                severity="medium",
                page=page,
                message="Görüntü aşırı karanlık.",
            )
        )
        score -= 0.2
    elif mean > 225:
        issues.append(
            QualityIssue(
                type="overexposed",
                severity="medium",
                page=page,
                message="Görüntü aşırı pozlanmış; parlama olabilir.",
            )
        )
        score -= 0.2

    bright_ratio = float(np.mean(gray > 248))
    if bright_ratio > 0.12:
        region = _brightest_region(gray)
        issues.append(
            QualityIssue(
                type="glare",
                severity="medium",
                page=page,
                message=f"{region} bölgede parlama var. Tarih ve sayı alanlarının okunabilirliği düşük olabilir.",
            )
        )
        score -= 0.15

    score = max(0.0, min(1.0, score))
    highs = [item for item in issues if item.severity == "high"]
    if min(width, height) < 400 or score < 0.35 or (highs and sharpness < 18):
        status = QualityStatus.UNUSABLE
    elif issues:
        status = QualityStatus.WARNING
    else:
        status = QualityStatus.GOOD
    return QualityReport(quality_score=round(score, 3), status=status, issues=issues)


def _brightest_region(gray: np.ndarray) -> str:
    height, width = gray.shape
    mid_y, mid_x = height // 2, width // 2
    blocks = {
        "sol üst": gray[:mid_y, :mid_x],
        "sağ üst": gray[:mid_y, mid_x:],
        "sol alt": gray[mid_y:, :mid_x],
        "sağ alt": gray[mid_y:, mid_x:],
    }
    name, _ = max(
        ((label, float(np.mean(block > 248))) for label, block in blocks.items() if block.size),
        key=lambda item: item[1],
        default=("belge", 0.0),
    )
    return name


def user_facing_quality_lines(report: QualityReport) -> list[str]:
    lines: list[str] = []
    for item in report.issues:
        mark = "⚠" if item.severity != "high" else "✖"
        lines.append(f"{mark} {item.message}")
    return lines


def jpeg_preview(data: bytes, *, max_side: int = 1400) -> tuple[int | None, int | None, str | None]:
    """EXIF-corrected JPEG for bbox overlay. Same pixels the VLM saw, smaller payload."""
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception:
        return None, None, None
    width, height = image.size
    longest = max(width, height)
    if longest > max_side:
        scale = max_side / float(longest)
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
        width, height = image.size
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=72, optimize=True)
    return width, height, base64.b64encode(out.getvalue()).decode("ascii")
