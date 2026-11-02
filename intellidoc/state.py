"""Shared state passed between every node in the graph."""

from typing import Literal, Optional, TypedDict

Status = Literal["pending", "processing", "integrated", "review", "failed"]

DEFAULT_SETTINGS = {
    "min_confidence": 0.6,   # classifier confidence below this goes to human review
    "max_retries": 2,        # how many times a failed OCR document may be re-ingested
    "data_dir": "data",      # where the database, review queue and event log live
    "use_jev": True,         # try Jev for classification when TYPESAFE_API_KEY is set
}


class IntelliDocState(TypedDict):
    doc: dict                          # path, extraction options, and the extracted text
    doc_type: Optional[str]            # set by classify
    doc_type_confidence: Optional[float]
    metadata: dict                     # filename, extraction method, OCR confidence, ...
    extracted_data: Optional[dict]     # validated fields (or partial fields on failure)
    validation: Optional[dict]         # {"passed": bool, "issues": [...]}
    status: Status
    errors: list[str]
    warnings: list[str]
    retries: int
    settings: dict


def new_state(
    path: str,
    *,
    preprocess: str = "auto",
    psm: int = 6,
    **settings,
) -> IntelliDocState:
    """Build the initial state for one document."""
    return {
        "doc": {"path": str(path), "preprocess": preprocess, "psm": psm},
        "doc_type": None,
        "doc_type_confidence": None,
        "metadata": {},
        "extracted_data": None,
        "validation": None,
        "status": "pending",
        "errors": [],
        "warnings": [],
        "retries": 0,
        "settings": {**DEFAULT_SETTINGS, **settings},
    }
