"""Optional UI JavaScript syntax smoke test for GitHub Actions.

Node is used only by CI, not by the Kayock Writer runtime.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.ui import _JS


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("Node.js unavailable: optional UI syntax check skipped.")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "kayock_ui.js"
        script.write_text(_JS, encoding="utf-8")
        result = subprocess.run([node, "--check", str(script)],
                                text=True, capture_output=True)
        if result.returncode:
            print(result.stderr)
            return result.returncode
    print("Kayock Writer UI JavaScript parses successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
