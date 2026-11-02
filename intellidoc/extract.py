"""Rule-based extractors. Each takes the document text and returns raw field
values (strings or None). The Pydantic models in schemas.py then decide whether
those values are valid, so an extractor never has to be "right", only
"a best attempt" that validation can check."""

import re
from typing import Callable, Optional

from .schemas import PAN_HOLDER_TYPES

# --- shared helpers ------------------------------------------------------------

_DATE_CORE = r"(\d{2}[/-]\d{2}[/-]\d{4})"
_DATE_RE = r"\b" + _DATE_CORE + r"\b"
_LABEL_WORDS = ("name", "father", "date of birth", "dob", "signature", "year of birth")


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _is_label(line: str) -> bool:
    low = line.lower()
    return any(w in low for w in _LABEL_WORDS)


def _looks_like_name(line: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z .'-]{2,59}", line.strip()))


def _value_after(lines: list[str], idx: int, upper_only: bool = False) -> Optional[str]:
    """First plausible name-like line after position idx, skipping labels."""
    for ln in lines[idx + 1: idx + 5]:
        if _is_label(ln):
            continue
        if _looks_like_name(ln) and (not upper_only or ln.upper() == ln):
            return ln
    return None


# --- PAN -----------------------------------------------------------------------

# OCR confuses look-alike characters. PAN has a fixed shape (LLLLL DDDD L), so
# each position can be corrected towards the class it must belong to.
_TO_LETTER = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}
_TO_DIGIT = {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"}


def fix_pan_candidate(token: str, strict: bool = True) -> Optional[str]:
    """Return a PAN-shaped version of a 10-char token, or None if impossible.

    strict=False also accepts an unknown 4th character, so the validator can say
    exactly what is wrong instead of reporting the number as missing.
    """
    if len(token) != 10:
        return None
    out = []
    for i, ch in enumerate(token):
        want_letter = i < 5 or i == 9
        if want_letter:
            ch = ch if ch.isalpha() else _TO_LETTER.get(ch, "")
        else:
            ch = ch if ch.isdigit() else _TO_DIGIT.get(ch, "")
        if not ch:
            return None
        out.append(ch)
    fixed = "".join(out)
    return fixed if (not strict or fixed[3] in PAN_HOLDER_TYPES) else None


def find_pan(text: str) -> Optional[str]:
    tokens = re.findall(r"(?<![A-Z0-9])[A-Z0-9]{10}(?![A-Z0-9])", text.upper())
    for strict in (True, False):          # a fully valid PAN wins; a near-miss is still reported
        for token in tokens:
            fixed = fix_pan_candidate(token, strict=strict)
            if fixed:
                return fixed
    return None


_PAN_HEADER = ("income tax", "govt", "government", "permanent account", "department", "card")


def extract_pan(text: str) -> dict:
    lines = _lines(text)
    pan = find_pan(text)

    father = name = None
    for i, ln in enumerate(lines):
        low = ln.lower()
        if "father" in low and father is None:
            father = _value_after(lines, i, upper_only=True)
        elif re.search(r"\bname\b", low) and name is None:
            name = _value_after(lines, i, upper_only=True)

    if name is None:  # fall back to the first uppercase non-header line after the PAN
        start = next((i for i, ln in enumerate(lines) if pan and pan in ln.upper().replace(" ", "")), -1)
        for ln in lines[start + 1:]:
            if _is_label(ln) or any(h in ln.lower() for h in _PAN_HEADER):
                continue
            if _looks_like_name(ln) and ln.upper() == ln:
                name = ln
                break

    dob_match = re.search(_DATE_RE, text)
    return {
        "pan_number": pan,
        "name": name,
        "father_name": father,
        "dob": dob_match.group(1) if dob_match else None,
    }


# --- Aadhaar -------------------------------------------------------------------

def extract_aadhaar(text: str) -> dict:
    lines = _lines(text)
    number = None
    for m in re.finditer(r"(?<!\d)(\d{4})\s?(\d{4})\s?(\d{4})(?!\d)", text):
        number = "".join(m.groups())
        break

    dob = re.search(r"(?:DOB|Date of Birth)\s*[:\-]?\s*" + _DATE_CORE, text, re.I)
    if dob is None:
        dob = re.search(_DATE_RE, text)
    yob = re.search(r"Year of Birth\s*[:\-]?\s*(\d{4})", text, re.I)
    gender = re.search(r"\b(FEMALE|MALE|TRANSGENDER)\b", text, re.I)

    # name: nearest name-like line above the birth-date line
    name = None
    anchor = next(
        (i for i, ln in enumerate(lines) if re.search(r"dob|date of birth|year of birth", ln, re.I)),
        None,
    )
    if anchor is not None:
        for ln in reversed(lines[:anchor]):
            low = ln.lower()
            if _looks_like_name(ln) and not any(w in low for w in ("government", "india", "unique", "authority", "aadhaar")):
                name = ln
                break

    return {
        "aadhaar_number": number,
        "name": name,
        "dob": dob.group(1) if dob else None,
        "year_of_birth": yob.group(1) if yob else None,
        "gender": gender.group(1) if gender else None,
    }


# --- research paper ------------------------------------------------------------

_KPI_WORDS = re.compile(
    r"accuracy|precision|recall|f1|bleu|rouge|latency|speed-?up|error|improv|reduc|increase|outperform",
    re.I,
)


def extract_research_paper(text: str) -> dict:
    lines = _lines(text)
    title = next((ln for ln in lines if len(ln.split()) >= 3 and not re.match(r"(?i)^(arxiv|abstract|figure|fig\.)", ln)), None)

    captions = []
    for i, ln in enumerate(lines):
        if re.match(r"(?i)^(figure|fig\.)\s*\d+\s*[:.\-]", ln):
            caption = ln
            for nxt in lines[i + 1: i + 3]:
                if re.match(r"(?i)^(figure|fig\.|references\b|\d+\.?\s+[A-Z])", nxt):
                    break
                caption += " " + nxt
            captions.append(caption)

    flat = re.sub(r"\s+", " ", text)
    sentences = re.split(r"(?<=[.!?])\s+", flat)
    kpis = [s.strip() for s in sentences if re.search(r"\d", s) and _KPI_WORDS.search(s) and len(s) < 300]

    return {
        "title": title,
        "has_abstract": bool(re.search(r"\babstract\b", text, re.I)),
        "figure_captions": captions,
        "kpis": kpis[:10],
    }


def extract_generic(text: str) -> dict:
    flat = re.sub(r"\s+", " ", text).strip()
    return {"word_count": len(flat.split()), "preview": flat[:200]}


EXTRACTORS: dict[str, Callable[[str], dict]] = {
    "pan_card": extract_pan,
    "aadhaar_card": extract_aadhaar,
    "research_paper": extract_research_paper,
    "other": extract_generic,
}
