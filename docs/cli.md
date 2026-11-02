# CLI reference

_Generated from the code by `scripts/gen_cli_docs.py`. Do not edit by hand._

```
python -m intellidoc COMMAND [options]
```

Exit codes: `0` = every document was integrated, `1` = at least one was sent to review, failed, or nothing was found.

Global option: `--version` prints the version and exits.

## `process`

Run one or more files (or folders of files) through ingest, classify, process and integrate.

```
usage: intellidoc process [-h] [--output {text,json}]
                          [--preprocess {auto,on,off}] [--psm N]
                          [--min-confidence F] [--max-retries N] [--no-jev]
                          [--data-dir DIR]
                          PATH [PATH ...]
```

8 arguments:

| Argument | Type | Required | Default | What it does |
|---|---|---|---|---|
| `PATH` | text | yes |  | file or folder to process; supported: .bmp, .jpeg, .jpg, .pdf, .png, .tif, .tiff, .txt |
| `--output` | text \| json | no | `text` | 'text' for a readable summary, 'json' for one JSON object per document |
| `--preprocess` | auto \| on \| off | no | `auto` | image clean-up before OCR; 'auto' tries both and keeps the better read |
| `--psm` `N` | int | no | `6` | Tesseract page-segmentation mode for the first attempt (6 = one block of text) |
| `--min-confidence` `F` | float | no | `0.6` | classifier confidence (0-1) below which a document goes to human review |
| `--max-retries` `N` | int | no | `2` | how many times a failed OCR document is re-read with a different strategy |
| `--no-jev` | flag | no |  | do not call Jev even if TYPESAFE_API_KEY is set; use the keyword classifier |
| `--data-dir` `DIR` | text | no | `data` | folder for the database, review queue and event log |

## `stats`

Print totals and the most recent runs from the event log in --data-dir.

```
usage: intellidoc stats [-h] [--data-dir DIR]
```

1 argument:

| Argument | Type | Required | Default | What it does |
|---|---|---|---|---|
| `--data-dir` `DIR` | text | no | `data` | folder for the database, review queue and event log |

## `serve`

Start the dashboard at http://HOST:PORT/ and the JSON/NDJSON API under /api.

```
usage: intellidoc serve [-h] [--host HOST] [--port PORT] [--samples-dir DIR]
                        [--data-dir DIR]
```

4 arguments:

| Argument | Type | Required | Default | What it does |
|---|---|---|---|---|
| `--host` `HOST` | text | no | `127.0.0.1` | address to listen on |
| `--port` `PORT` | int | no | `8000` | port to listen on |
| `--samples-dir` `DIR` | text | no | `samples` | folder of sample files offered in the dashboard |
| `--data-dir` `DIR` | text | no | `data` | folder for the database, review queue and event log |
