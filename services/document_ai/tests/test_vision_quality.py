from __future__ import annotations

import io

from PIL import Image


def _png(width: int, height: int, color: tuple[int, int, int] = (180, 180, 180)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_tiny_image_is_unusable() -> None:
    from document_ai.vision.quality import assess_image
    from hakim_legal_schema.document import QualityStatus

    report = assess_image(_png(1, 1), page=1)
    assert report.status == QualityStatus.UNUSABLE
    types = {item.type for item in report.issues}
    assert "low_resolution" in types


def test_glare_warns_with_region() -> None:
    from document_ai.vision.quality import assess_image, user_facing_quality_lines
    from hakim_legal_schema.document import QualityStatus

    image = Image.new("RGB", (900, 1200), (40, 40, 40))
    pixels = image.load()
    assert pixels is not None
    for x in range(450, 900):
        for y in range(600, 1200):
            pixels[x, y] = (255, 255, 255)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    report = assess_image(buf.getvalue(), page=1)
    assert report.status in {QualityStatus.WARNING, QualityStatus.UNUSABLE}
    glare = [item for item in report.issues if item.type == "glare"]
    assert glare
    lines = user_facing_quality_lines(report)
    assert any("parlama" in line.lower() for line in lines)
    assert any("sağ alt" in line for line in lines)


def test_sharp_document_sized_scan_is_not_unusable() -> None:
    from document_ai.vision.quality import assess_image
    from hakim_legal_schema.document import QualityStatus

    image = Image.new("RGB", (1000, 1400), (240, 240, 240))
    pixels = image.load()
    assert pixels is not None
    for y in range(40, 1360, 3):
        for x in range(40, 960):
            pixels[x, y] = (20, 20, 20)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    report = assess_image(buf.getvalue())
    assert report.status != QualityStatus.UNUSABLE


def test_jpeg_preview_is_base64_jpeg() -> None:
    from document_ai.vision.quality import jpeg_preview

    image = Image.new("RGB", (800, 1000), (240, 240, 240))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    width, height, encoded = jpeg_preview(buf.getvalue())
    assert width == 800
    assert height == 1000
    assert encoded
    raw = __import__("base64").b64decode(encoded)
    assert raw[:2] == b"\xff\xd8"
