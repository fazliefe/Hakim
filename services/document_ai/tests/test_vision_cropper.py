from __future__ import annotations

import io

from PIL import Image


def test_crop_bbox_returns_smaller_png() -> None:
    from document_ai.vision.cropper import crop_bbox

    image = Image.new("RGB", (100, 100), (10, 20, 30))
    pixels = image.load()
    assert pixels is not None
    for x in range(60, 80):
        for y in range(40, 50):
            pixels[x, y] = (255, 0, 0)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    cropped = crop_bbox(buf.getvalue(), [0.6, 0.4, 0.8, 0.5], pad=0.0)
    out = Image.open(io.BytesIO(cropped))
    assert out.size == (20, 10)
