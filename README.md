# IntelliDoc

Upload a document (photo, scan, PDF or text). IntelliDoc classifies it, extracts the key fields,
validates them with Pydantic, and saves the result. Anything it cannot read or validate is retried
with a different strategy and then sent to a review queue.

```
Upload -> Ingestion -> Classification -> Extraction -> Validation -> Integration
```

Built with LangGraph, Tesseract, PyMuPDF, OpenCV, Pydantic, Jev (classification) and FastAPI.

## Quick start

```bash
brew install tesseract              # macOS; on Ubuntu: sudo apt install tesseract-ocr
python -m pip install -r requirements.txt
python make_samples.py              # synthetic sample documents
python -m intellidoc process samples/ --no-jev
python -m intellidoc serve          # dashboard at http://127.0.0.1:8000
```

## Commands

| Command | What it does |
|---|---|
| `python -m intellidoc process PATH...` | run files or folders through the pipeline |
| `python -m intellidoc stats` | counts of integrated / review / failed |
| `python -m intellidoc serve` | dashboard and HTTP API |

Every argument, type and default is in the [CLI reference](docs/cli.md), which is generated from the
code (`python scripts/gen_cli_docs.py`).

## Documentation

Read the docs in `docs/`, or build the site:

```bash
python -m pip install -r requirements-dev.txt
mkdocs serve
```

## Tests

```bash
python -m pytest -q
```

## Privacy

The samples are synthetic. Real ID documents are personal data: only process what you are allowed
to, keep `data/` and `.env` out of Git (both are in `.gitignore`).
