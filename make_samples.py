"""Generate synthetic test documents into samples/.

Everything here is made up: names, numbers and text. The ID samples are plain
text on a white background, not copies of any real card layout.
Run:  python make_samples.py
"""

from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

from intellidoc.schemas import verhoeff_check_digit

OUT = Path("samples")
OUT.mkdir(exist_ok=True)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def text_image(lines: list[str], path: Path, size: int = 34, width: int = 1100) -> Image.Image:
    f = font(size)
    height = 60 + len(lines) * (size + 22)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = 30
    for line in lines:
        draw.text((50, y), line, fill="black", font=f)
        y += size + 22
    img.save(path)
    return img


FOOTER = "SYNTHETIC TEST SAMPLE - NOT A REAL DOCUMENT"

# --- ID-style samples -----------------------------------------------------------
pan_lines = [
    "INCOME TAX DEPARTMENT", "GOVT. OF INDIA", "Permanent Account Number Card",
    "ABCPV1234K", "Name", "ASHA VERMA", "Father's Name", "RAJESH VERMA",
    "Date of Birth", "14/03/1995", "Signature", FOOTER,
]
pan = text_image(pan_lines, OUT / "sample_pan.png")

prefix = "23456789012"
aadhaar_no = prefix + str(verhoeff_check_digit(prefix))
aadhaar_no = f"{aadhaar_no[:4]} {aadhaar_no[4:8]} {aadhaar_no[8:]}"
text_image(
    ["Government of India", "Asha Verma", "DOB: 14/03/1995", "FEMALE", aadhaar_no, FOOTER],
    OUT / "sample_aadhaar.png",
)

# invalid on purpose: 4th PAN character 'X' is not a holder type, so validation fails
text_image(
    ["INCOME TAX DEPARTMENT", "Permanent Account Number Card", "ABCXV1234K",
     "Name", "ASHA VERMA", "Date of Birth", "14/03/1995", FOOTER],
    OUT / "sample_pan_invalid.png",
)

# --- degraded photo of the PAN sample: tilt, uneven light, blur, noise ------------
arr = np.array(pan)
h, w = arr.shape[:2]
m = cv2.getRotationMatrix2D((w / 2, h / 2), 3.0, 1.0)
arr = cv2.warpAffine(arr, m, (w, h), borderValue=(235, 235, 235))
gradient = np.tile(np.linspace(0.55, 1.0, w), (h, 1))[..., None]
arr = (arr * gradient).astype(np.uint8)
arr = cv2.GaussianBlur(arr, (5, 5), 1.2)
rng = np.random.default_rng(7)
arr = np.clip(arr + rng.normal(0, 14, arr.shape), 0, 255).astype(np.uint8)
Image.fromarray(arr).save(OUT / "sample_pan_noisy.png")

# --- research paper (text PDF) ---------------------------------------------------
paper = [
    "Efficient Multimodal Retrieval for Scientific Documents",
    "A. Researcher and B. Researcher, University of Somewhere",
    "",
    "Abstract",
    "We present a pipeline for extracting structured knowledge from scientific",
    "papers that contain both text and embedded figures. Our method combines",
    "OCR-based text extraction with vision-language captioning.",
    "",
    "1. Introduction",
    "Scientific papers often present key results as figures rather than prose.",
    "",
    "2. Results",
    "Our method improves retrieval accuracy by 12% over text-only baselines.",
    "Average latency dropped from 480 ms to 210 ms after caching.",
    "",
    "Figure 1: Accuracy improves by 12% when captioning is combined with",
    "OCR-based extraction on three benchmark datasets.",
    "",
    "Figure 2: Latency per page with and without the caching layer.",
    "",
    "References",
    "[1] Researcher et al. A made-up reference, 2025.",
]
pdf = pymupdf.open()
page = pdf.new_page()
y = 72
for line in paper:
    page.insert_text((72, y), line, fontsize=11)
    y += 16
pdf.save(OUT / "sample_paper.pdf")

# --- scanned PDF: the PAN sample as an image-only page (forces OCR on a PDF) --------
scan = pymupdf.open()
p = scan.new_page(width=600, height=int(600 * pan.height / pan.width))
p.insert_image(p.rect, filename=str(OUT / "sample_pan.png"))
scan.save(OUT / "sample_scan.pdf")

# --- other ---------------------------------------------------------------------------
(OUT / "sample_note.txt").write_text(
    "Team sync notes. We agreed to move the demo to Wednesday and review the "
    "pipeline diagram together. Action items: update the schema, rerun tests.\n"
)
Image.new("RGB", (800, 400), "white").save(OUT / "sample_blank.png")

print("wrote:", ", ".join(sorted(p.name for p in OUT.iterdir())))
print("Aadhaar sample number:", aadhaar_no)
