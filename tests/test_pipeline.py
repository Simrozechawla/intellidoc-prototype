"""End-to-end runs on the synthetic samples (these call real Tesseract)."""

import pytest

from intellidoc.pipeline import run_document
from tests.conftest import needs_tesseract

pytestmark = needs_tesseract


def run(path, tmp_path, **kw):
    return run_document(str(path), data_dir=str(tmp_path), use_jev=False, **kw)


def nodes(result):
    return [e["node"] for e in result["events"]]


def test_pan_image_is_integrated(samples, tmp_path):
    r = run(samples / "sample_pan.png", tmp_path)
    assert r["status"] == "integrated" and r["doc_type"] == "pan_card"
    assert r["extracted_data"]["pan_number"] == "ABCPV1234K"
    assert r["extracted_data"]["name"] == "ASHA VERMA"
    assert nodes(r) == ["ingest", "classify", "process", "integrate"]


def test_scanned_pdf_uses_ocr_and_text_pdf_does_not(samples, tmp_path):
    scanned = run(samples / "sample_scan.pdf", tmp_path)
    assert scanned["metadata"]["extraction_method"] == "ocr"
    assert scanned["status"] == "integrated"
    paper = run(samples / "sample_paper.pdf", tmp_path)
    assert paper["metadata"]["extraction_method"] == "native"
    assert paper["metadata"]["ocr_confidence"] is None
    assert paper["doc_type"] == "research_paper"
    assert paper["extracted_data"]["n_figures"] == 2
    assert any("12%" in k for k in paper["extracted_data"]["kpis"])


def test_aadhaar_checksum_pipeline(samples, tmp_path):
    r = run(samples / "sample_aadhaar.png", tmp_path)
    assert r["status"] == "integrated"
    assert r["extracted_data"]["masked_number"] == "XXXX XXXX 0124"


def test_invalid_document_retries_then_goes_to_review(samples, tmp_path):
    r = run(samples / "sample_pan_invalid.png", tmp_path, max_retries=2)
    assert r["status"] == "review" and r["retries"] == 2
    assert nodes(r).count("ingest") == 3
    assert nodes(r)[-2:] == ["handle_error", "human_review"]
    assert [a["psm"] for a in r["metadata"]["attempt_log"]] == [6, 4, 11]
    assert (tmp_path / "review_queue.jsonl").exists()


def test_preprocessing_rescues_a_degraded_photo(samples, tmp_path):
    """Preprocessing must lift OCR from unreadable to readable on a tilted, noisy photo.

    We do not require status == "integrated": a single misread digit (for example a date's
    1 read as 4) depends on the Tesseract version and rightly sends the document to review.
    """
    off = run(samples / "sample_pan_noisy.png", tmp_path, preprocess="off", max_retries=0)
    auto = run(samples / "sample_pan_noisy.png", tmp_path, preprocess="auto")
    assert auto["metadata"]["ocr_confidence"] > off["metadata"]["ocr_confidence"] + 20
    assert auto["extracted_data"]["pan_number"] == "ABCPV1234K"
    assert auto["status"] in ("integrated", "review")     # never saved with unvalidated data
    if auto["status"] == "review":
        assert auto["errors"]


@pytest.mark.parametrize("name,message", [
    ("sample_blank.png", "no text"),
    ("does_not_exist.png", "not found"),
])
def test_unreadable_input_fails_cleanly(samples, tmp_path, name, message):
    r = run(samples / name, tmp_path)
    assert r["status"] == "failed" and message in r["errors"][0]
    assert nodes(r) == ["ingest"]


def test_unsupported_extension(tmp_path):
    f = tmp_path / "data.xyz"
    f.write_text("hello")
    r = run(f, tmp_path / "out")
    assert r["status"] == "failed" and "unsupported" in r["errors"][0]