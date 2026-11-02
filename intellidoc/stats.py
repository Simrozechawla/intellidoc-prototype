"""Read run history back from the event log."""

import json
from pathlib import Path


def collect_stats(data_dir: str, recent: int = 8) -> dict:
    """Counts by outcome plus the most recent runs, from data/events.jsonl."""
    log = Path(data_dir) / "events.jsonl"
    runs = []
    if log.exists():
        for line in log.read_text().splitlines():
            if line.strip():
                try:
                    runs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    counts = {"integrated": 0, "review": 0, "failed": 0}
    for run in runs:
        if run.get("status") in counts:
            counts[run["status"]] += 1
    return {
        "total": len(runs),
        **counts,
        "recent": [
            {"id": r["id"], "file": r["file"], "status": r["status"], "steps": len(r["events"])}
            for r in reversed(runs[-recent:])
        ],
    }
