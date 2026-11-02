"""classify_node: decide what kind of document this is.

Two classifiers share one interface and return (label, confidence, probabilities):
  * Jev (TypeSafe AI), a "System One" model that answers a multiple-choice
    question with a probability per option. Used when TYPESAFE_API_KEY is set.
  * A keyword classifier, used as the fallback when there is no key, no
    credits, or the API call fails.
"""

import os
import re

import requests

from .state import IntelliDocState

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_TEXT_LIMIT = 6000   # characters sent to Jev; well inside its 32k-token state limit

LABELS = {
    "pan_card": "An Indian PAN (Permanent Account Number) card from the Income Tax Department",
    "aadhaar_card": "An Indian Aadhaar card issued by UIDAI, showing a 12-digit number",
    "research_paper": "An academic or scientific research paper with an abstract, sections and figures",
    "other": "Any other kind of document",
}

# (pattern, weight) per document type for the fallback classifier
_PAN_RE = r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"
_AADHAAR_RE = r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"
SIGNALS = {
    "pan_card": [
        (_PAN_RE, 5.0),
        (r"income\s*tax\s*department", 3.0),
        (r"permanent\s*account\s*number", 3.0),
        (r"\bpan\b", 1.0),
    ],
    "aadhaar_card": [
        (_AADHAAR_RE, 3.0),
        (r"aadhaar|aadhar", 3.0),
        (r"uidai|unique\s*identification", 3.0),
        (r"government\s*of\s*india", 1.0),
        (r"year\s*of\s*birth|\bdob\b", 1.0),
    ],
    "research_paper": [
        (r"\babstract\b", 1.5),
        (r"\bintroduction\b", 1.0),
        (r"\breferences\b", 1.0),
        (r"\bfig(?:ure|\.)\s*\d", 1.0),
        (r"\bet al\b", 1.0),
        (r"\bkeywords?\b", 1.0),
        (r"arxiv|\bdoi\b", 1.0),
    ],
}


def classify_keywords(text: str) -> tuple[str, float, dict]:
    """Fallback classifier: weighted keyword and pattern matches."""
    scores = {}
    for label, signals in SIGNALS.items():
        flags = 0 if label == "pan_card" else re.IGNORECASE
        scores[label] = sum(w for pat, w in signals if re.search(pat, text, flags))
    best_label = max(scores, key=scores.get)
    best = scores[best_label]
    if best == 0:
        return "other", 0.7, {"other": 0.7}
    confidence = round(best / (best + 1.0), 2)
    return best_label, confidence, {k: round(v / (v + 1.0), 2) for k, v in scores.items()}


def classify_jev(text: str, api_key: str, timeout: float = 20.0) -> tuple[str, float, dict]:
    """Ask Jev a single multiple-choice question about the document text."""
    body = {
        "model": JEV_MODEL,
        "state": text[:JEV_TEXT_LIMIT],
        "questions": {
            "doc_type": {
                "type": "choice",
                "instructions": "What kind of document is this?",
                "criteria": LABELS,
            }
        },
    }
    resp = requests.post(
        JEV_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    # The docs show answers under "answers"; accept a bare mapping too.
    answer = data.get("answers", data)["doc_type"]
    label = answer["choice"]
    if label not in LABELS:
        raise ValueError(f"Jev returned an unknown label: {label!r}")
    return label, float(answer["confidence"]), answer.get("probabilities", {})


def classify_node(state: IntelliDocState) -> dict:
    text = state["doc"].get("text", "")
    settings = state["settings"]
    warnings = list(state["warnings"])
    md = dict(state["metadata"])

    api_key = os.environ.get("TYPESAFE_API_KEY")
    result, source = None, "keywords"

    if settings.get("use_jev", True) and api_key:
        try:
            result, source = classify_jev(text, api_key), "jev"
        except Exception as exc:  # network, billing, bad response: all fall back
            warnings.append(f"Jev unavailable, used keyword classifier ({type(exc).__name__})")
    if result is None:
        result = classify_keywords(text)

    label, confidence, probabilities = result
    md["classifier"] = source
    md["classifier_probabilities"] = probabilities
    return {
        "doc_type": label,
        "doc_type_confidence": round(float(confidence), 3),
        "metadata": md,
        "warnings": warnings,
    }
