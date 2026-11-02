# Getting started

## 1. Install

You need Python 3.10+ and the **Tesseract** OCR program.

```bash
# macOS
brew install tesseract
# Ubuntu / Debian
sudo apt install tesseract-ocr

python -m pip install -r requirements.txt
```

Check Tesseract is found: `tesseract --version`.

## 2. Make the sample files

```bash
python make_samples.py
```

This writes synthetic documents to `samples/`: a PAN card, an Aadhaar card, a research paper, a
scanned PDF, a deliberately tilted and noisy PAN photo, a PAN with an invalid number, a text note
and a blank image.

## 3. Run it

```bash
python -m intellidoc process samples/ --no-jev
python -m intellidoc stats
python -m intellidoc serve          # then open http://127.0.0.1:8000
```

`--no-jev` uses the keyword classifier, so nothing needs an account or an internet connection.

## 4. Turn on Jev (optional)

Jev is a hosted classifier from TypeSafe AI and needs an API key with credits on the account.

```bash
cp .env.example .env     # then edit .env and paste your key
python -m intellidoc process samples/sample_pan.png
```

The `.env` file is listed in `.gitignore`. Never commit it and never paste a key into a chat or a
ticket. If Jev is unreachable for any reason, IntelliDoc falls back to the keyword classifier and
records a warning in the result.

## 5. Run the tests

```bash
python -m pytest -q
```

## Where results go

Everything lives in the folder given by `--data-dir` (default `data/`):

| File | Contents |
|---|---|
| `intellidoc.db` | SQLite database with the integrated documents |
| `review_queue.jsonl` | documents a person needs to look at, with the reasons |
| `events.jsonl` | one line per run: file, status and the step-by-step event log |
| `uploads/` | files uploaded through the dashboard |
