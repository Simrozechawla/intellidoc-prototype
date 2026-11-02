"""Graph assembly and the runner that streams progress events.

    START -> ingest -> classify -> process -> integrate -> END
               |           |          |
               |           |          +-- error --> handle_error --+-- retry --> ingest
               |           |                                       +-- escalate -> human_review -> END
               |           +-- low confidence --> human_review
               +-- unreadable file --> END
"""

import json
import time
import uuid
from pathlib import Path
from typing import Iterator

from langgraph.graph import END, START, StateGraph

from .classify import classify_node
from .ingest import ingest_node
from .nodes import handle_error_node, human_review_node, integrate_node, process_node
from .routing import route_after_classify, route_after_error, route_after_ingest, route_after_process
from .state import IntelliDocState, new_state

NODE_ORDER = ["ingest", "classify", "process", "handle_error", "human_review", "integrate"]


def build_graph():
    g = StateGraph(IntelliDocState)
    g.add_node("ingest", ingest_node)
    g.add_node("classify", classify_node)
    g.add_node("process", process_node)
    g.add_node("handle_error", handle_error_node)
    g.add_node("human_review", human_review_node)
    g.add_node("integrate", integrate_node)

    g.add_edge(START, "ingest")
    g.add_conditional_edges("ingest", route_after_ingest, {"ok": "classify", "fail": END})
    g.add_conditional_edges("classify", route_after_classify, {"ok": "process", "review": "human_review"})
    g.add_conditional_edges("process", route_after_process, {"ok": "integrate", "error": "handle_error"})
    g.add_conditional_edges("handle_error", route_after_error, {"retry": "ingest", "escalate": "human_review"})
    g.add_edge("integrate", END)
    g.add_edge("human_review", END)
    return g.compile()


GRAPH = build_graph()


def _summary(node: str, update: dict, state: dict) -> str:
    md = update.get("metadata") or state.get("metadata", {})
    if node == "ingest":
        if update.get("status") == "failed":
            return "; ".join(update.get("errors", []))
        conf = md.get("ocr_confidence")
        extra = f", OCR confidence {conf}" if conf is not None else ""
        pre = ", preprocessing applied" if md.get("preprocessing_used") else ""
        return f"{md.get('extraction_method')} extraction{extra}{pre}"
    if node == "classify":
        return f"{update['doc_type']} ({update['doc_type_confidence']}, via {md.get('classifier')})"
    if node == "process":
        v = update["validation"]
        return "validation passed" if v["passed"] else f"{len(v['issues'])} validation issue(s)"
    if node == "handle_error":
        return md.get("retry_strategy") or "escalating to review"
    if node == "human_review":
        return "queued for review"
    if node == "integrate":
        return f"saved to {md.get('integrated_into')}"
    return ""


def run_stream(path: str, **options) -> Iterator[dict]:
    """Run one document, yielding an event after every node, then a final result."""
    state = new_state(path, **options)
    data_dir = Path(state["settings"]["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    doc_id = str(uuid.uuid4())
    events: list[dict] = []
    last = time.perf_counter()

    for chunk in GRAPH.stream(state, stream_mode="updates"):
        for node, update in chunk.items():
            update = update or {}
            now = time.perf_counter()
            state.update(update)
            event = {
                "event": "node",
                "node": node,
                "ms": round((now - last) * 1000),
                "summary": _summary(node, update, state),
                "status": state["status"],
            }
            last = now
            events.append(event)
            yield event

    md = {k: v for k, v in state["metadata"].items() if k != "classifier_probabilities"}
    result = {
        "id": doc_id,
        "file": state["metadata"].get("filename", Path(path).name),
        "status": state["status"],
        "doc_type": state["doc_type"],
        "doc_type_confidence": state["doc_type_confidence"],
        "extracted_data": state["extracted_data"],
        "validation": state["validation"],
        "errors": state["errors"],
        "warnings": state["warnings"],
        "retries": state["retries"],
        "metadata": md,
        "text_preview": state["doc"].get("text", "")[:400],
        "events": events,
    }
    with (data_dir / "events.jsonl").open("a") as f:
        f.write(json.dumps({"id": doc_id, "file": result["file"], "status": result["status"],
                            "events": events}) + "\n")
    yield {"event": "final", "result": result}


def run_document(path: str, **options) -> dict:
    """Run one document and return the final result."""
    result = None
    for ev in run_stream(path, **options):
        if ev["event"] == "final":
            result = ev["result"]
    return result
