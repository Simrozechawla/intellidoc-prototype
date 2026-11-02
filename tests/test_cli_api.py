"""CLI and web API (real Tesseract, synthetic samples)."""

import json

import pytest
from fastapi.testclient import TestClient

from intellidoc.api import create_app
from intellidoc.cli import build_parser, main
from intellidoc.stats import collect_stats
from tests.conftest import needs_tesseract


def test_parser_has_the_documented_commands():
    parser = build_parser()
    assert parser.parse_args(["process", "a.png"]).preprocess == "auto"
    assert parser.parse_args(["serve", "--port", "9000"]).port == 9000
    with pytest.raises(SystemExit):
        parser.parse_args([])                        # a command is required
    with pytest.raises(SystemExit):
        parser.parse_args(["process", "a.png", "--preprocess", "maybe"])


def test_stats_on_an_empty_folder(tmp_path):
    assert collect_stats(str(tmp_path))["total"] == 0


@needs_tesseract
def test_cli_json_output_and_exit_codes(samples, tmp_path, capsys):
    ok = main(["process", str(samples / "sample_pan.png"), "--no-jev",
               "--output", "json", "--data-dir", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert ok == 0 and out["extracted_data"]["pan_number"] == "ABCPV1234K"

    bad = main(["process", str(samples / "sample_blank.png"), "--no-jev", "--data-dir", str(tmp_path)])
    assert bad == 1                                  # needs attention -> non-zero exit
    assert collect_stats(str(tmp_path))["total"] == 2


@needs_tesseract
def test_api_streams_events_and_rejects_bad_input(samples, tmp_path):
    client = TestClient(create_app(str(tmp_path), str(samples)))
    assert client.get("/api/health").json()["status"] == "ok"
    assert "sample_pan.png" in client.get("/api/samples").json()

    r = client.post("/api/process-sample", params={"name": "sample_pan.png"})
    events = [json.loads(line) for line in r.text.splitlines()]
    assert [e.get("node") for e in events[:-1]] == ["ingest", "classify", "process", "integrate"]
    assert events[-1]["result"]["status"] == "integrated"

    assert client.post("/api/process-sample", params={"name": "../secret"}).status_code == 404
    assert client.post("/api/process", files={"file": ("x.exe", b"abc")}).status_code == 400
    assert client.get("/").status_code == 200


@needs_tesseract
def test_api_upload(samples, tmp_path):
    client = TestClient(create_app(str(tmp_path), str(samples)))
    data = (samples / "sample_aadhaar.png").read_bytes()
    r = client.post("/api/process", files={"file": ("my card!.png", data)})
    final = [json.loads(line) for line in r.text.splitlines()][-1]["result"]
    assert final["extracted_data"]["masked_number"] == "XXXX XXXX 0124"
