from intellidoc.extract import extract_aadhaar, extract_pan, extract_research_paper, fix_pan_candidate, find_pan
from intellidoc.schemas import AadhaarCard, PanCard, verhoeff_check_digit


def test_fix_pan_candidate_repairs_look_alike_characters():
    assert fix_pan_candidate("ABCPV1234K") == "ABCPV1234K"
    assert fix_pan_candidate("0BCPV1234K") == "OBCPV1234K"      # zero where a letter belongs
    assert fix_pan_candidate("ABCPVI234K") == "ABCPV1234K"      # letter I where a digit belongs
    assert fix_pan_candidate("ABCPV1Z34K") == "ABCPV1234K"      # Z where a digit belongs
    assert fix_pan_candidate("ABCXV1234K") is None              # 4th char cannot be a holder type
    assert fix_pan_candidate("DEPARTMENT") is None              # an ordinary word is not a PAN


def test_find_pan_ignores_header_words():
    assert find_pan("INCOME TAX DEPARTMENT\nPermanent Account Number\nABCPV1234K") == "ABCPV1234K"


def test_pan_with_labels_on_separate_lines():
    text = "INCOME TAX DEPARTMENT\nGOVT. OF INDIA\nABCPV1234K\nName\nASHA VERMA\nFather's Name\nRAJESH VERMA\nDate of Birth\n14/03/1995\n"
    pan = PanCard.model_validate(extract_pan(text))
    assert (pan.name, pan.father_name, str(pan.dob)) == ("ASHA VERMA", "RAJESH VERMA", "1995-03-14")


def test_pan_with_bilingual_labels():
    text = "आयकर विभाग\nINCOME TAX DEPARTMENT\nABCPV1234K\nनाम / Name\nASHA VERMA\nपिता का नाम / Father's Name\nRAJESH VERMA\nजन्म तिथि / Date of Birth\n14/03/1995\n"
    raw = extract_pan(text)
    assert raw["name"] == "ASHA VERMA"
    assert raw["father_name"] == "RAJESH VERMA"


def test_pan_name_fallback_without_labels():
    raw = extract_pan("INCOME TAX DEPARTMENT\nABCPV1234K\nASHA VERMA\n14/03/1995\n")
    assert raw["name"] == "ASHA VERMA"


def test_aadhaar_extraction():
    prefix = "23456789012"
    number = prefix + str(verhoeff_check_digit(prefix))
    spaced = f"{number[:4]} {number[4:8]} {number[8:]}"
    text = f"Government of India\nAsha Verma\nDOB: 14/03/1995\nFEMALE\n{spaced}\n"
    card = AadhaarCard.model_validate(extract_aadhaar(text))
    assert card.aadhaar_number == number
    assert card.name == "Asha Verma"
    assert card.gender == "FEMALE"          # not "MALE" from inside the word FEMALE


def test_research_paper_extraction():
    text = (
        "Efficient Multimodal Retrieval for Scientific Documents\nAuthors\nAbstract\nWe study things.\n"
        "Our method improves accuracy by 12% over baselines.\n"
        "Figure 1: Accuracy improves by 12% when\ncaptioning is combined with OCR.\n"
        "Figure 2: Latency per page.\n"
    )
    raw = extract_research_paper(text)
    assert raw["title"].startswith("Efficient Multimodal")
    assert raw["has_abstract"] is True
    assert len(raw["figure_captions"]) == 2
    assert "captioning is combined with OCR" in raw["figure_captions"][0]
    assert any("12%" in k for k in raw["kpis"])
