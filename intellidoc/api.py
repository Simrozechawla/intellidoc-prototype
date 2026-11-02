"""FastAPI app: a streaming upload endpoint plus the dashboard page."""

import json
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from . import __version__
from .ingest import SUPPORTED_EXTS
from .pipeline import run_stream
from .stats import collect_stats

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
WEB_DIR = Path(__file__).parent / "web"


def create_app(data_dir: str = "data", samples_dir: str = "samples") -> FastAPI:
    app = FastAPI(title="IntelliDoc API", version=__version__)
    data = Path(data_dir)
    samples = Path(samples_dir)

    def ndjson(path: Path, preprocess: str):
        """One JSON event per line, flushed as each pipeline node finishes."""
        def gen():
            try:
                for event in run_stream(str(path), preprocess=preprocess, data_dir=str(data)):
                    yield json.dumps(event) + "\n"
            except Exception as exc:  # surface unexpected failures to the page
                yield json.dumps({"event": "error", "message": f"{type(exc).__name__}: {exc}"}) + "\n"
        return StreamingResponse(gen(), media_type="application/x-ndjson")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/stats")
    def stats():
        return collect_stats(str(data))

    @app.get("/api/samples")
    def list_samples():
        if not samples.is_dir():
            return []
        return sorted(f.name for f in samples.iterdir() if f.suffix.lower() in SUPPORTED_EXTS)

    @app.post("/api/process")
    async def process(file: UploadFile = File(...), preprocess: Literal["auto", "on", "off"] = "auto"):
        name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "upload").name)
        if Path(name).suffix.lower() not in SUPPORTED_EXTS:
            raise HTTPException(400, f"unsupported file type; use one of {sorted(SUPPORTED_EXTS)}")
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "file is larger than 25 MB")
        uploads = data / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        dest = uploads / f"{uuid.uuid4().hex[:8]}_{name}"
        dest.write_bytes(content)
        return ndjson(dest, preprocess)

    @app.post("/api/process-sample")
    def process_sample(name: str, preprocess: Literal["auto", "on", "off"] = "auto"):
        path = samples / Path(name).name          # no directory traversal
        if not path.is_file():
            raise HTTPException(404, "no such sample")
        return ndjson(path, preprocess)

    return app
