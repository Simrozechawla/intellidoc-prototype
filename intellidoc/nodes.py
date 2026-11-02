"""process, handle_error, human_review and integrate nodes.

Every node is a plain function: state in, partial state update out.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .extract import EXTRACTORS
from .schemas import SCHEMAS
from .state import IntelliDocState

RETRY_PSMS = [4, 11, 12]   # a different page-layout strategy for each retry
LOW_OCR_CONFIDENCE = 60.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _data_dir(state: IntelliDocState) -> Path:
    d = Path(state["settings"]["data_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- process -------------------------------------------------------------------

def process_node(state: IntelliDocState) -> dict:
    """Extract fields with rules, then validate them with Pydantic."""
    doc_type = state["doc_type"] or "other"
    text = state["doc"]["text"]
    raw = EXTRACTORS[doc_type](text)
    md = dict(state["metadata"])
    warnings = list(state["warnings"])

    attempt = {"attempt": state["retries"] + 1, "ocr_confidence": md.get("ocr_confidence"),
               "psm": state["doc"].get("psm"), "preprocessing": md.get("preprocessing_used")}
    try:
        model = SCHEMAS[doc_type].model_validate(raw)
    except ValidationError as exc:
        issues = [
            {
                "field": ".".join(str(p) for p in e["loc"]) or "document",
                "message": "not found in the document" if e.get("input") is None else e["msg"].removeprefix("Value error, "),
            }
            for e in exc.errors()
        ]
        attempt.update(passed=False, issues=[f"{i['field']}: {i['message']}" for i in issues])
        md["attempt_log"] = md.get("attempt_log", []) + [attempt]
        return {
            "extracted_data": raw,
            "validation": {"passed": False, "issues": issues},
            "errors": [f"{i['field']}: {i['message']}" for i in issues],
            "metadata": md,
        }

    attempt.update(passed=True, issues=[])
    md["attempt_log"] = md.get("attempt_log", []) + [attempt]
    conf = md.get("ocr_confidence")
    if conf is not None and conf < LOW_OCR_CONFIDENCE:
        warnings.append(f"OCR confidence is low ({conf}); fields passed validation but check them")
    return {
        "extracted_data": model.model_dump(mode="json"),
        "validation": {"passed": True, "issues": []},
        "errors": [],
        "warnings": warnings,
        "metadata": md,
    }


# --- handle_error --------------------------------------------------------------

def handle_error_node(state: IntelliDocState) -> dict:
    """Decide between retry and escalate, and change the approach when retrying.

    Repeating the exact same OCR would fail the exact same way, so a retry
    re-ingests with preprocessing forced on and a different layout mode.
    Documents read from a native text layer cannot improve by re-reading, so
    those escalate straight away.
    """
    md = dict(state["metadata"])
    can_improve = md.get("extraction_method") in ("ocr", "mixed")
    retries = state["retries"]
    max_retries = state["settings"]["max_retries"]

    if can_improve and retries < max_retries:
        doc = dict(state["doc"])
        doc["preprocess"] = "on"
        doc["psm"] = RETRY_PSMS[min(retries, len(RETRY_PSMS) - 1)]
        md["error_decision"] = "retry"
        md["retry_strategy"] = f"preprocessing on, layout mode psm {doc['psm']}"
        return {"retries": retries + 1, "doc": doc, "metadata": md}

    md["error_decision"] = "escalate"
    return {"metadata": md}


# --- human_review --------------------------------------------------------------

def human_review_node(state: IntelliDocState) -> dict:
    """Queue a document a person should look at."""
    reasons = list(state["errors"])
    conf = state["doc_type_confidence"]
    if not reasons and conf is not None and conf < state["settings"]["min_confidence"]:
        reasons = [f"low classification confidence ({conf})"]

    entry = {
        "id": str(uuid.uuid4()),
        "queued_at": _now(),
        "file": state["metadata"].get("filename"),
        "doc_type": state["doc_type"],
        "doc_type_confidence": conf,
        "reasons": reasons,
        "extracted_data": state["extracted_data"],
    }
    queue = _data_dir(state) / "review_queue.jsonl"
    with queue.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    md = {**state["metadata"], "review_id": entry["id"]}
    return {"status": "review", "errors": reasons, "metadata": md}


# --- integrate -----------------------------------------------------------------

def _mask(number: str) -> str:
    return "X" * (len(number) - 4) + number[-4:] if number and len(number) > 4 else number


def _adapter_identity(data: dict, doc_type: str) -> tuple[str, dict]:
    number = data.get("pan_number") or data.get("aadhaar_number")
    return "identity_documents", {
        "doc_type": doc_type,
        "number_masked": _mask(number),
        "name": data.get("name"),
        "dob": data.get("dob"),
    }


def _adapter_paper(data: dict, doc_type: str) -> tuple[str, dict]:
    return "papers", {
        "title": data["title"],
        "n_figures": data["n_figures"],
        "n_kpis": len(data["kpis"]),
        "kpis_json": json.dumps(data["kpis"]),
    }


def _adapter_generic(data: dict, doc_type: str) -> tuple[str, dict]:
    return "other_documents", {"word_count": data["word_count"], "preview": data["preview"]}


# Dispatch table: one adapter per document type. Adding a destination for a new
# document type means adding one function and one entry here.
ADAPTERS = {
    "pan_card": _adapter_identity,
    "aadhaar_card": _adapter_identity,
    "research_paper": _adapter_paper,
    "other": _adapter_generic,
}

_TABLES = {
    "identity_documents": "doc_type TEXT, number_masked TEXT, name TEXT, dob TEXT",
    "papers": "title TEXT, n_figures INTEGER, n_kpis INTEGER, kpis_json TEXT",
    "other_documents": "word_count INTEGER, preview TEXT",
}


def db_path(data_dir: str) -> Path:
    p = Path(data_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p / "intellidoc.db"


def integrate_node(state: IntelliDocState) -> dict:
    """Write validated data to the enterprise store (SQLite stands in for it)."""
    doc_type = state["doc_type"] or "other"
    table, row = ADAPTERS[doc_type](state["extracted_data"], doc_type)
    record_id = str(uuid.uuid4())

    with sqlite3.connect(db_path(state["settings"]["data_dir"])) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, filename TEXT, "
            "doc_type TEXT, confidence REAL, table_name TEXT, created_at TEXT)"
        )
        for name, cols in _TABLES.items():
            conn.execute(f"CREATE TABLE IF NOT EXISTS {name} (doc_id TEXT, {cols})")
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?)",
            (record_id, state["metadata"].get("filename"), doc_type,
             state["doc_type_confidence"], table, _now()),
        )
        keys = ", ".join(["doc_id", *row])
        marks = ", ".join("?" * (len(row) + 1))
        conn.execute(f"INSERT INTO {table} ({keys}) VALUES ({marks})", (record_id, *row.values()))

    md = {**state["metadata"], "record_id": record_id, "integrated_into": table}
    return {"status": "integrated", "metadata": md}
