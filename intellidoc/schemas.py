"""Pydantic models: the contract for what "valid extracted data" means.

Adding a document type means adding one model here, one extractor in
extract.py, and one entry in each registry (SCHEMAS, EXTRACTORS, ADAPTERS).
"""

import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

# --- helpers -------------------------------------------------------------------

PAN_HOLDER_TYPES = {
    "P": "Individual", "C": "Company", "H": "Hindu Undivided Family", "F": "Firm",
    "A": "Association of Persons", "T": "Trust", "B": "Body of Individuals",
    "L": "Local Authority", "J": "Artificial Juridical Person", "G": "Government",
}

_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_valid(number: str) -> bool:
    """Check the Verhoeff checksum, which Aadhaar numbers carry as their last digit."""
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(prefix: str) -> int:
    """Compute the check digit to append to a numeric prefix."""
    c = 0
    for i, ch in enumerate(reversed(prefix)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return _INV[c]


def parse_date(value) -> Optional[date]:
    """Accept date objects or dd/mm/yyyy and dd-mm-yyyy strings."""
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date format: {value!r}{_misread_hint(str(value))}")


# Digits OCR commonly mixes up. Used only to SUGGEST a reading to a reviewer, never to change data.
_LOOKALIKE_DIGITS = {"0": "86", "1": "47", "3": "85", "4": "19", "5": "63", "6": "058", "7": "1", "8": "036", "9": "4"}


def _misread_hint(value: str) -> str:
    """If one misread digit would make a dd/mm/yyyy date valid, say so in the error."""
    text = value.strip()
    if not re.fullmatch(r"\d{2}[/-]\d{2}[/-]\d{4}", text):
        return ""
    found = []
    for i, ch in enumerate(text):
        for repl in _LOOKALIKE_DIGITS.get(ch, ""):
            candidate = text[:i] + repl + text[i + 1:]
            try:
                d = datetime.strptime(candidate, "%d/%m/%Y" if "/" in candidate else "%d-%m-%Y").date()
            except ValueError:
                continue
            if 1900 <= d.year and d <= date.today() and candidate not in found:
                found.append(candidate)
    return f" (possible OCR misread; did you mean {' or '.join(found[:3])}?)" if found else ""


def _check_birth_date(d: Optional[date]) -> Optional[date]:
    if d is None:
        return d
    if d > date.today():
        raise ValueError("date of birth is in the future")
    if d.year < 1900:
        raise ValueError("date of birth is before 1900")
    return d


def _clean_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    name = re.sub(r"\s+", " ", value).strip(" .,-").upper()
    if not re.fullmatch(r"[A-Z][A-Z .'-]{1,59}", name):
        raise ValueError(f"name contains unexpected characters: {value!r}")
    return name


# --- models --------------------------------------------------------------------

class PanCard(BaseModel):
    pan_number: str
    name: str
    father_name: Optional[str] = None
    dob: Optional[date] = None

    @field_validator("pan_number")
    @classmethod
    def _pan(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", v):
            raise ValueError("must be 5 letters, 4 digits, 1 letter (e.g. ABCPD1234E)")
        if v[3] not in PAN_HOLDER_TYPES:
            raise ValueError(f"4th character {v[3]!r} is not a valid holder type")
        return v

    @field_validator("name", "father_name", mode="before")
    @classmethod
    def _names(cls, v):
        return _clean_name(v)

    @field_validator("dob", mode="before")
    @classmethod
    def _dob(cls, v):
        return _check_birth_date(parse_date(v))

    @computed_field
    @property
    def holder_type(self) -> str:
        return PAN_HOLDER_TYPES[self.pan_number[3]]


class AadhaarCard(BaseModel):
    aadhaar_number: str
    name: str
    dob: Optional[date] = None
    year_of_birth: Optional[int] = None
    gender: Optional[str] = None

    @field_validator("aadhaar_number", mode="before")
    @classmethod
    def _number(cls, v):
        digits = re.sub(r"\s+", "", str(v))
        if not re.fullmatch(r"[2-9][0-9]{11}", digits):
            raise ValueError("must be 12 digits and must not start with 0 or 1")
        if not verhoeff_valid(digits):
            raise ValueError("checksum (Verhoeff) does not match; a digit was probably misread")
        return digits

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v):
        name = re.sub(r"\s+", " ", str(v)).strip(" .,-")
        if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,59}", name):
            raise ValueError(f"name contains unexpected characters: {v!r}")
        return name.title()

    @field_validator("dob", mode="before")
    @classmethod
    def _dob(cls, v):
        return _check_birth_date(parse_date(v))

    @field_validator("year_of_birth", mode="before")
    @classmethod
    def _yob(cls, v):
        if v in (None, ""):
            return None
        year = int(v)
        if not 1900 <= year <= date.today().year:
            raise ValueError("year of birth is out of range")
        return year

    @field_validator("gender", mode="before")
    @classmethod
    def _gender(cls, v):
        if v in (None, ""):
            return None
        g = str(v).strip().upper()
        if g not in {"MALE", "FEMALE", "TRANSGENDER"}:
            raise ValueError(f"unexpected gender value: {v!r}")
        return g

    @model_validator(mode="after")
    def _needs_birth_info(self):
        if self.dob is None and self.year_of_birth is None:
            raise ValueError("neither date of birth nor year of birth was found")
        return self

    @computed_field
    @property
    def masked_number(self) -> str:
        return f"XXXX XXXX {self.aadhaar_number[-4:]}"


class ResearchPaper(BaseModel):
    title: str = Field(min_length=5)
    has_abstract: bool
    figure_captions: list[str] = []
    kpis: list[str] = []

    @computed_field
    @property
    def n_figures(self) -> int:
        return len(self.figure_captions)


class GenericDocument(BaseModel):
    word_count: int = Field(gt=0)
    preview: str


SCHEMAS = {
    "pan_card": PanCard,
    "aadhaar_card": AadhaarCard,
    "research_paper": ResearchPaper,
    "other": GenericDocument,
}
