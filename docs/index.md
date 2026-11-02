# IntelliDoc

IntelliDoc takes a document (a photo, a scan, a PDF or a text file), works out what kind of
document it is, pulls out the fields that matter, **validates** them, and files the result in a
database. Anything it cannot read or cannot validate is retried with a different strategy and, if
that fails too, sent to a human review queue instead of being silently saved.

```
Upload -> Ingestion -> Classification -> Extraction -> Validation -> Integration
```

## What it handles

| Document | Fields extracted | Checks |
|---|---|---|
| PAN card | PAN number, name, father's name, date of birth | PAN format, holder-type letter, date parses |
| Aadhaar card | number, name, DOB / year of birth, gender | 12 digits, first digit 2-9, Verhoeff checksum |
| Research paper | title, abstract present, figure captions, KPI sentences | title present, figure count |
| Anything else | word count, text preview | at least some text |

Sample files in `samples/` are **synthetic**. They are not real cards.

## How the four pieces of feedback are covered

| Feedback | Where |
|---|---|
| Validate with Pydantic | [Validation](validation.md): every document type has a Pydantic model; the pipeline only integrates data that passes |
| Use Jev instead of an LLM | [Classification](classification.md): Jev classifies the document type; a keyword classifier is the offline fallback |
| Expand multimodality | Images, scanned PDFs, text PDFs and plain text are all accepted; each PDF page uses native text when it exists and OCR when it does not |
| Image preprocessing | [Preprocessing](preprocessing.md): grayscale, upscale, deskew, denoise, threshold; measured effect shown in the result |

## Next

- [Getting started](getting-started.md)
- [Architecture](architecture.md)
- [CLI reference](cli.md)
- [HTTP API](api.md)
- [Limitations](limitations.md)
