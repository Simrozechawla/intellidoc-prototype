"""Conditional-edge functions. They only read state and return a label; they
never change it. All control flow of the graph lives here and in graph.py."""

from .state import IntelliDocState


def route_after_ingest(state: IntelliDocState) -> str:
    return "fail" if state["status"] == "failed" else "ok"


def route_after_classify(state: IntelliDocState) -> str:
    confidence = state["doc_type_confidence"]
    if confidence is None or confidence < state["settings"]["min_confidence"]:
        return "review"
    return "ok"


def route_after_process(state: IntelliDocState) -> str:
    validation = state["validation"] or {}
    return "ok" if validation.get("passed") else "error"


def route_after_error(state: IntelliDocState) -> str:
    return "retry" if state["metadata"].get("error_decision") == "retry" else "escalate"
