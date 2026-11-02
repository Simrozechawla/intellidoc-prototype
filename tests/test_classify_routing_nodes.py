import json
import sqlite3

import pytest
import requests

from intellidoc import classify
from intellidoc.classify import classify_keywords, classify_node
from intellidoc.nodes import handle_error_node, human_review_node, integrate_node
from intellidoc.routing import (
    route_after_classify, route_after_error, route_after_ingest, route_after_process,
)
from intellidoc.state import new_state


# --- keyword classifier ---------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("INCOME TAX DEPARTMENT\nPermanent Account Number Card\nABCPV1234K", "pan_card"),
    ("Government of India\nAsha Verma\nDOB: 14/03/1995\nFEMALE\n2345 6789 0124", "aadhaar_card"),
    ("Abstract\nWe study X.\n1. Introduction\nFigure 1: a plot\nReferences\nSmith et al.", "research_paper"),
    ("Lunch is at noon on Tuesday.", "other"),
])
def test_keyword_classifier(text, expected):
    label, confidence, _ = classify_keywords(text)
    assert label == expected
    assert confidence >= 0.6


def test_weak_evidence_gives_low_confidence():
    label, confidence, _ = classify_keywords("see the figure 3 below")
    assert confidence < 0.6


# --- Jev classifier (network is stubbed) ---------------------------------------

class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status} error")

    def json(self):
        return self.payload


def _state(text):
    s = new_state("x.txt")
    s["doc"]["text"] = text
    return s


def test_jev_response_is_used(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    payload = {"answers": {"doc_type": {"type": "choice", "choice": "pan_card", "confidence": 0.97,
                                         "probabilities": {"pan_card": 0.97, "other": 0.03}}}}
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return FakeResponse(payload)

    monkeypatch.setattr(classify.requests, "post", fake_post)
    out = classify_node(_state("some text"))
    assert out["doc_type"] == "pan_card" and out["doc_type_confidence"] == 0.97
    assert out["metadata"]["classifier"] == "jev"
    assert sent["headers"]["Authorization"] == "Bearer test-key"
    assert sent["body"]["questions"]["doc_type"]["type"] == "choice"


@pytest.mark.parametrize("failure", [
    lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("offline")),
    lambda *a, **k: FakeResponse({}, status=402),
    lambda *a, **k: FakeResponse({"answers": {"doc_type": {"choice": "banana", "confidence": 0.9}}}),
])
def test_jev_failure_falls_back_to_keywords(monkeypatch, failure):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(classify.requests, "post", failure)
    out = classify_node(_state("INCOME TAX DEPARTMENT ABCPV1234K Permanent Account Number"))
    assert out["metadata"]["classifier"] == "keywords"
    assert out["doc_type"] == "pan_card"
    assert any("Jev unavailable" in w for w in out["warnings"])


def test_no_key_means_no_network_call(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(classify.requests, "post", lambda *a, **k: pytest.fail("network used"))
    assert classify_node(_state("Abstract\nIntroduction\nReferences"))["metadata"]["classifier"] == "keywords"


# --- routing ----------------------------------------------------------------------

def test_routes():
    s = new_state("x")
    assert route_after_ingest({**s, "status": "failed"}) == "fail"
    assert route_after_ingest({**s, "status": "processing"}) == "ok"
    assert route_after_classify({**s, "doc_type_confidence": 0.9}) == "ok"
    assert route_after_classify({**s, "doc_type_confidence": 0.3}) == "review"
    assert route_after_classify({**s, "doc_type_confidence": None}) == "review"
    assert route_after_process({**s, "validation": {"passed": True}}) == "ok"
    assert route_after_process({**s, "validation": {"passed": False}}) == "error"
    assert route_after_error({**s, "metadata": {"error_decision": "retry"}}) == "retry"
    assert route_after_error({**s, "metadata": {"error_decision": "escalate"}}) == "escalate"


# --- handle_error / review / integrate ---------------------------------------------

def test_handle_error_changes_strategy_and_stops_at_the_limit():
    s = new_state("x.png", max_retries=2)
    s["metadata"] = {"extraction_method": "ocr"}
    first = handle_error_node(s)
    assert first["retries"] == 1 and first["doc"]["preprocess"] == "on" and first["doc"]["psm"] == 4
    s.update(first)
    second = handle_error_node(s)
    assert second["retries"] == 2 and second["doc"]["psm"] == 11
    s.update(second)
    third = handle_error_node(s)
    assert third["metadata"]["error_decision"] == "escalate"


def test_native_text_is_never_retried():
    s = new_state("x.pdf")
    s["metadata"] = {"extraction_method": "native"}
    assert handle_error_node(s)["metadata"]["error_decision"] == "escalate"


def test_human_review_writes_queue(tmp_path):
    s = new_state("x.png", data_dir=str(tmp_path))
    s.update(errors=["pan_number: not found in the document"], doc_type="pan_card",
             doc_type_confidence=0.8, metadata={"filename": "x.png"})
    out = human_review_node(s)
    assert out["status"] == "review"
    entry = json.loads((tmp_path / "review_queue.jsonl").read_text().splitlines()[0])
    assert entry["file"] == "x.png" and entry["reasons"] == ["pan_number: not found in the document"]


def test_integrate_masks_identity_numbers(tmp_path):
    s = new_state("x.png", data_dir=str(tmp_path))
    s.update(doc_type="pan_card", doc_type_confidence=0.9, metadata={"filename": "x.png"},
             extracted_data={"pan_number": "ABCPV1234K", "name": "ASHA VERMA", "dob": "1995-03-14"})
    out = integrate_node(s)
    assert out["status"] == "integrated"
    with sqlite3.connect(tmp_path / "intellidoc.db") as conn:
        (masked,) = conn.execute("SELECT number_masked FROM identity_documents").fetchone()
    assert masked == "XXXXXX234K" and "ABCPV" not in masked
