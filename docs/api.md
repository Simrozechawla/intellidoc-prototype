# HTTP API

Start the server with `python -m intellidoc serve`. Interactive docs are at `/docs`.

| Method and path | Purpose |
|---|---|
| `GET /` | the dashboard |
| `GET /api/health` | `{"status": "ok", "version": "..."}` |
| `GET /api/stats` | totals and the most recent runs |
| `GET /api/samples` | sample file names available to the dashboard |
| `POST /api/process` | upload a file (multipart field `file`, query `preprocess=auto\|on\|off`) |
| `POST /api/process-sample?name=...` | run a sample file |

Uploads: PNG, JPG, TIFF, BMP, PDF or TXT, up to 25 MB. File names are sanitised and stored under
`<data-dir>/uploads/` with a random prefix. Wrong type returns 400, too large 413.

## Streaming response

`/api/process` and `/api/process-sample` return **NDJSON**: one JSON object per line, sent as each
pipeline node finishes.

```json
{"event": "node", "node": "ingest", "ms": 2577, "summary": "ocr extraction, OCR confidence 94.7", "status": "processing"}
{"event": "node", "node": "classify", "ms": 1, "summary": "pan_card (0.83, via keywords)", "status": "processing"}
{"event": "final", "result": {"status": "integrated", "doc_type": "pan_card", "extracted_data": {"...": "..."}}}
```

Example:

```bash
curl -N -F "file=@samples/sample_pan.png" "http://127.0.0.1:8000/api/process?preprocess=auto"
```

If something unexpected goes wrong the stream ends with `{"event": "error", "message": "..."}`.
