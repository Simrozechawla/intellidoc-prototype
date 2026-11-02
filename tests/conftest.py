import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="Tesseract is not installed"
)


@pytest.fixture(scope="session")
def samples() -> Path:
    folder = ROOT / "samples"
    if not (folder / "sample_pan.png").exists():
        subprocess.run([sys.executable, "make_samples.py"], cwd=ROOT, check=True)
    return folder
