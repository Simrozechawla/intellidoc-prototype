"""Command-line interface.

    python -m intellidoc process FILE... [options]
    python -m intellidoc stats [--data-dir DIR]
    python -m intellidoc serve [--host H] [--port P]

The parser is built by build_parser() so the documentation generator can read
every argument, type and default straight from the code.
"""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .ingest import SUPPORTED_EXTS
from .state import DEFAULT_SETTINGS

EXIT_OK, EXIT_NEEDS_ATTENTION = 0, 1


def _add_data_dir(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--data-dir", default=DEFAULT_SETTINGS["data_dir"], metavar="DIR",
        help="folder for the database, review queue and event log",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intellidoc",
        description="Extract, validate and file structured data from documents.",
    )
    parser.add_argument("--version", action="version", version=f"intellidoc {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser(
        "process", help="run documents through the pipeline",
        description="Run one or more files (or folders of files) through ingest, "
                    "classify, process and integrate.",
    )
    p.add_argument("paths", nargs="+", metavar="PATH",
                   help="file or folder to process; supported: " + ", ".join(sorted(SUPPORTED_EXTS)))
    p.add_argument("--output", choices=["text", "json"], default="text",
                   help="'text' for a readable summary, 'json' for one JSON object per document")
    p.add_argument("--preprocess", choices=["auto", "on", "off"], default="auto",
                   help="image clean-up before OCR; 'auto' tries both and keeps the better read")
    p.add_argument("--psm", type=int, default=6, metavar="N",
                   help="Tesseract page-segmentation mode for the first attempt (6 = one block of text)")
    p.add_argument("--min-confidence", type=float, default=DEFAULT_SETTINGS["min_confidence"], metavar="F",
                   help="classifier confidence (0-1) below which a document goes to human review")
    p.add_argument("--max-retries", type=int, default=DEFAULT_SETTINGS["max_retries"], metavar="N",
                   help="how many times a failed OCR document is re-read with a different strategy")
    p.add_argument("--no-jev", action="store_true",
                   help="do not call Jev even if TYPESAFE_API_KEY is set; use the keyword classifier")
    _add_data_dir(p)

    p = sub.add_parser(
        "stats", help="show counts of processed, reviewed and failed documents",
        description="Print totals and the most recent runs from the event log in --data-dir.",
    )
    _add_data_dir(p)

    p = sub.add_parser(
        "serve", help="start the web dashboard and API",
        description="Start the dashboard at http://HOST:PORT/ and the JSON/NDJSON API under /api.",
    )
    p.add_argument("--host", default="127.0.0.1", help="address to listen on")
    p.add_argument("--port", type=int, default=8000, help="port to listen on")
    p.add_argument("--samples-dir", default="samples", metavar="DIR",
                   help="folder of sample files offered in the dashboard")
    _add_data_dir(p)
    return parser


def _expand(paths: list[str]) -> list[str]:
    files = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files += [str(f) for f in sorted(p.iterdir()) if f.suffix.lower() in SUPPORTED_EXTS]
        else:
            files.append(raw)
    return files


def _print_text(r: dict) -> None:
    md = r["metadata"]
    conf = r["doc_type_confidence"]
    print(f"\n{r['file']}")
    print(f"  status      {r['status']}" + (f"  (after {r['retries']} retries)" if r["retries"] else ""))
    if r["doc_type"]:
        print(f"  type        {r['doc_type']}  (confidence {conf}, via {md.get('classifier')})")
    method = md.get("extraction_method")
    if method:
        extra = f", OCR confidence {md['ocr_confidence']}" if md.get("ocr_confidence") is not None else ""
        print(f"  extraction  {method}{extra}")
    for key, value in (r["extracted_data"] or {}).items():
        shown = json.dumps(value) if isinstance(value, (list, dict)) else value
        print(f"  {key:<11} {shown}")
    for e in r["errors"]:
        print(f"  ERROR       {e}")
    for w in r["warnings"]:
        print(f"  warning     {w}")


def cmd_process(args) -> int:
    from .pipeline import run_document

    files = _expand(args.paths)
    if not files:
        print("no supported files found", file=sys.stderr)
        return EXIT_NEEDS_ATTENTION
    attention = 0
    for path in files:
        result = run_document(
            path,
            preprocess=args.preprocess, psm=args.psm,
            min_confidence=args.min_confidence, max_retries=args.max_retries,
            use_jev=not args.no_jev, data_dir=args.data_dir,
        )
        if args.output == "json":
            print(json.dumps(result))
        else:
            _print_text(result)
        attention += result["status"] != "integrated"
    return EXIT_NEEDS_ATTENTION if attention else EXIT_OK


def cmd_stats(args) -> int:
    from .stats import collect_stats

    s = collect_stats(args.data_dir)
    print(f"total {s['total']} | integrated {s['integrated']} | review {s['review']} | failed {s['failed']}")
    for run in s["recent"]:
        print(f"  {run['status']:<10} {run['file']}")
    return EXIT_OK


def cmd_serve(args) -> int:
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(args.data_dir, args.samples_dir), host=args.host, port=args.port)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return {"process": cmd_process, "stats": cmd_stats, "serve": cmd_serve}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
