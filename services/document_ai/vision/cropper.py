from __future__ import annotations

import io

from PIL import Image


def crop_bbox(image_bytes: bytes, bbox: list[float], *, pad: float = 0.04) -> bytes:
    """Crop a normalized bbox from an image; used for second-pass llm-large."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = image.size
    x0, y0, x1, y1 = (float(v) for v in bbox)
    x0 = max(0.0, x0 - pad)
    y0 = max(0.0, y0 - pad)
    x1 = min(1.0, x1 + pad)
    y1 = min(1.0, y1 + pad)
    box = (
        int(x0 * width),
        int(y0 * height),
        max(int(x1 * width), int(x0 * width) + 1),
        max(int(y1 * height), int(y0 * height) + 1),
    )
    cropped = image.crop(box)
    out = io.BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()
