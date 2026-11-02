import pytest
from pydantic import ValidationError

from intellidoc.schemas import (
    AadhaarCard, PanCard, ResearchPaper, verhoeff_check_digit, verhoeff_valid,
)


def test_verhoeff_known_example():
    assert verhoeff_check_digit("236") == 3
    assert verhoeff_valid("2363")
    assert not verhoeff_valid("2364")


def test_pan_valid():
    pan = PanCard(pan_number="abcpv1234k", name="asha  verma", dob="14/03/1995")
    assert pan.pan_number == "ABCPV1234K"
    assert pan.name == "ASHA VERMA"
    assert pan.holder_type == "Individual"
    assert str(pan.dob) == "1995-03-14"


@pytest.mark.parametrize("bad", ["ABCPV1234", "ABCPV12345", "ABCXV1234K", "1BCPV1234K", ""])
def test_pan_rejects_bad_numbers(bad):
    with pytest.raises(ValidationError):
        PanCard(pan_number=bad, name="ASHA VERMA")


def test_pan_rejects_future_dob_and_odd_name():
    with pytest.raises(ValidationError):
        PanCard(pan_number="ABCPV1234K", name="ASHA VERMA", dob="01/01/2999")
    with pytest.raises(ValidationError):
        PanCard(pan_number="ABCPV1234K", name="AS#A V3RMA")


def _aadhaar(prefix="23456789012"):
    return prefix + str(verhoeff_check_digit(prefix))


def test_aadhaar_valid_and_masked():
    a = AadhaarCard(aadhaar_number=_aadhaar(), name="asha verma", dob="14/03/1995", gender="female")
    assert a.name == "Asha Verma"
    assert a.gender == "FEMALE"
    assert a.masked_number.endswith(a.aadhaar_number[-4:])
    assert a.masked_number.startswith("XXXX XXXX")


def test_aadhaar_checksum_catches_a_misread_digit():
    good = _aadhaar()
    bad = good[:-1] + str((int(good[-1]) + 1) % 10)
    with pytest.raises(ValidationError, match="checksum"):
        AadhaarCard(aadhaar_number=bad, name="Asha Verma", dob="14/03/1995")


def test_aadhaar_rules():
    with pytest.raises(ValidationError):
        AadhaarCard(aadhaar_number="0" + _aadhaar()[1:], name="Asha Verma", dob="14/03/1995")
    with pytest.raises(ValidationError, match="birth"):
        AadhaarCard(aadhaar_number=_aadhaar(), name="Asha Verma")
    ok = AadhaarCard(aadhaar_number=_aadhaar(), name="Asha Verma", year_of_birth="1995")
    assert ok.year_of_birth == 1995


def test_research_paper_counts_figures():
    paper = ResearchPaper(title="A Reasonable Title", has_abstract=True,
                          figure_captions=["Figure 1: a", "Figure 2: b"])
    assert paper.n_figures == 2
    with pytest.raises(ValidationError):
        ResearchPaper(title="Hi", has_abstract=False)


def test_misread_date_error_suggests_a_fix_but_does_not_change_data():
    with pytest.raises(ValidationError) as exc:
        PanCard.model_validate({"pan_number": "ABCPV1234K", "name": "ASHA VERMA", "dob": "44/03/1995"})
    message = str(exc.value)
    assert "did you mean 14/03/1995" in message          # a hint for the reviewer
    assert "dob" in message                              # the document is still rejected
