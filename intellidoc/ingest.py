"""ingest_node: turn any supported file into text plus metadata.

Decision logic:
  * .txt                  -> read directly
  * .pdf, per page        -> use the embedded text layer if there is one,
                             otherwise render the page and OCR it
  * images                -> OCR
OCR can run with or without preprocessing. In "auto" mode both run and the
result with the higher Tesseract confidence is kept.
"""

from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

from .preprocess import preprocess
from .state import IntelliDocState

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
SUPPORTED_EXTS = IMAGE_EXTS | {".pdf", ".txt"}
MIN_NATIVE_CHARS = 20   # fewer characters than this on a page means "no text layer"


def ocr(image: Image.Image, psm: int = 6) -> tuple[str, float]:
    """Run Tesseract once. Returns (text, mean word confidence 0-100)."""
    cfg = f"--psm {psm}"
    data = pytesseract.image_to_data(image, config=cfg, output_type=pytesseract.Output.DICT)
    confs = []
    for word, conf in zip(data["text"], data["conf"]):
        try:
            c = float(conf)
        except ValueError:
            continue
        if word.strip() and c >= 0:
            confs.append(c)
    text = pytesseract.image_to_string(image, config=cfg)
    return text, (sum(confs) / len(confs) if confs else 0.0)


def ocr_with_mode(image: Image.Image, mode: str, psm: int) -> tuple[str, float, dict]:
    """OCR an image honouring the preprocessing mode: off | on | auto."""
    if mode == "off":
        text, conf = ocr(image, psm)
        return text, conf, {"raw": conf, "preprocessed": None, "used": False}
    pre_text, pre_conf = ocr(preprocess(image), psm)
    if mode == "on":
        return pre_text, pre_conf, {"raw": None, "preprocessed": pre_conf, "used": True}
    raw_text, raw_conf = ocr(image, psm)
    if pre_conf > raw_conf:
        return pre_text, pre_conf, {"raw": raw_conf, "preprocessed": pre_conf, "used": True}
    return raw_text, raw_conf, {"raw": raw_conf, "preprocessed": pre_conf, "used": False}


def text_quality(text: str) -> float:
    """Rough 0-1 score: share of non-space characters that look like real text.

    A heuristic for spotting OCR garbage. It is not accuracy, and clean text
    can score low if it is mostly symbols.
    """
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    good = sum(c.isalnum() or c in ".,:;/-()'\"%&@" for c in chars)
    return good / len(chars)


def ingest_node(state: IntelliDocState) -> dict:
    doc = state["doc"]
    path = Path(doc["path"])
    mode = doc.get("preprocess", "auto")
    psm = int(doc.get("psm", 6))
    ext = path.suffix.lower()

    md = {
        "filename": path.name,
        "extension": ext,
        "preprocess_mode": mode,
        "psm": psm,
        "ocr_confidence": None,
        "ocr_raw_confidence": None,
        "ocr_preprocessed_confidence": None,
        "preprocessing_used": False,
        "embedded_images": 0,
        # carried across retries so the history of attempts survives re-ingestion
        "attempt_log": state["metadata"].get("attempt_log", []),
    }

    def fail(message: str) -> dict:
        return {"errors": [message], "status": "failed", "metadata": md}

    if not path.exists():
        return fail(f"file not found: {path}")
    if ext not in SUPPORTED_EXTS:
        return fail(f"unsupported file type: {ext or '(none)'}")

    confs: list[float] = []

    def note_ocr(conf: float, info: dict) -> None:
        confs.append(conf)
        md["ocr_raw_confidence"] = info["raw"]
        md["ocr_preprocessed_confidence"] = info["preprocessed"]
        md["preprocessing_used"] = md["preprocessing_used"] or info["used"]

    if ext == ".txt":
        text, method = path.read_text(errors="ignore"), "text"

    elif ext == ".pdf":
        pages_text, page_methods = [], []
        with pymupdf.open(path) as pdf:
            md["page_count"] = len(pdf)
            for page in pdf:
                md["embedded_images"] += len(page.get_images(full=True))
                native = page.get_text()
                if len(native.strip()) >= MIN_NATIVE_CHARS:
                    pages_text.append(native)
                    page_methods.append("native")
                else:
                    pix = page.get_pixmap(dpi=200)
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    t, c, info = ocr_with_mode(img, mode, psm)
                    note_ocr(c, info)
                    pages_text.append(t)
                    page_methods.append("ocr")
        text = "\n".join(pages_text)
        md["page_methods"] = page_methods
        kinds = set(page_methods)
        method = "native" if kinds == {"native"} else "ocr" if kinds == {"ocr"} else "mixed"

    else:  # image
        with Image.open(path) as img:
            t, c, info = ocr_with_mode(img.convert("RGB"), mode, psm)
        note_ocr(c, info)
        text, method = t, "ocr"

    md["extraction_method"] = method
    if confs:
        md["ocr_confidence"] = round(sum(confs) / len(confs), 1)
    md["text_quality"] = round(text_quality(text), 2)

    if not text.strip():
        return fail("no text could be extracted from the document")

    return {
        "doc": {**doc, "text": text},
        "metadata": md,
        "status": "processing",
        "errors": [],
    }
