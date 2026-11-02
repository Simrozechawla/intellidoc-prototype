"""Image clean-up applied before OCR."""

import cv2
import numpy as np
from PIL import Image

MIN_SIDE = 2000   # upscale small photos so characters have enough pixels
MAX_SIDE = 3200   # cap huge scans so denoising stays fast


def _estimate_skew(gray: np.ndarray, limit: float = 10.0) -> float:
    """Return the rotation (degrees) that makes text rows most horizontal.

    Uses a projection-profile search: when text lines are horizontal, the row
    sums of dark pixels vary the most. The same rotation call is used for the
    search and the correction, so the sign is consistent by construction.
    """
    small = gray
    longest = max(gray.shape)
    if longest > 1000:
        scale = 1000 / longest
        small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    _, bw = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    h, w = bw.shape
    centre = (w / 2, h / 2)

    def score(angle: float) -> float:
        m = cv2.getRotationMatrix2D(centre, angle, 1.0)
        rotated = cv2.warpAffine(bw, m, (w, h), flags=cv2.INTER_NEAREST)
        return float(np.var(rotated.sum(axis=1)))

    coarse = max(np.arange(-limit, limit + 0.1, 1.0), key=score)
    fine = max(np.arange(coarse - 1.0, coarse + 1.01, 0.25), key=score)
    return float(fine)


def _rotate(gray: np.ndarray, angle: float) -> np.ndarray:
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def preprocess(img: Image.Image) -> Image.Image:
    """grayscale -> resize -> deskew -> denoise -> adaptive threshold."""
    gray = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2GRAY)

    longest = max(gray.shape)
    if longest < MIN_SIDE:
        scale = MIN_SIDE / longest
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    elif longest > MAX_SIDE:
        scale = MAX_SIDE / longest
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    angle = _estimate_skew(gray)
    if 0.4 <= abs(angle) <= 10:
        gray = _rotate(gray, angle)

    gray = cv2.fastNlMeansDenoising(gray, None, h=10)

    # adaptive threshold copes with uneven lighting in phone photos
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    return Image.fromarray(binary)
