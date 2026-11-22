"""Prepare disposable, author-owned cover art for CI-only browser publishing.

Reuses the tiny JPEG fixture already tested in test_cover_unicode_pdf.py.
Never downloads fonts, ships licensed font files or reads user data.
"""
from __future__ import annotations

import base64
from pathlib import Path

from test_cover_unicode_pdf import JPEG_B64

root = Path("test-results/ci-private")
root.mkdir(parents=True, exist_ok=True)
cover = root / "synthetic-cover.jpg"
cover.write_bytes(base64.b64decode(JPEG_B64, validate=True))
print("CI synthetic cover ready:", cover)
