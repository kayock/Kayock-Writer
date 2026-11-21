#!/usr/bin/env bash
# Kayock Writer: optional, unprivileged installation of source files.
# No service creation, model changes, firewall changes, sudo, or autostart.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SRC="$(dirname "$SCRIPT_DIR")"
DST="${KAYOCK_WRITER_INSTALL_DIR:-$HOME/Applications/KayockWriter}"
PYTHON="${PYTHON:-python3}"
"$PYTHON" - "$SRC" "$DST" <<'PYCODE'
import os, pathlib, shutil, sys
src=pathlib.Path(sys.argv[1]).resolve()
dst=pathlib.Path(sys.argv[2]).expanduser().resolve()
if src == dst:
    print('Already at installation directory; nothing to copy.')
    raise SystemExit(0)
if dst == src or src in dst.parents:
    raise SystemExit('Refusing to install inside the source directory.')
if dst in src.parents:
    raise SystemExit('Refusing to install over a parent of the source directory.')
if dst.exists() and dst.is_symlink():
    raise SystemExit('Refusing to overwrite symlink destination.')
dst.mkdir(parents=True, exist_ok=True)
for relative in ('kayock_writer.py','README.md','LICENSE_NOTES.md','config.example.json'):
    shutil.copy2(src/relative, dst/relative)
for directory in ('app','docs','deploy','tests'):
    (dst/directory).mkdir(parents=True,exist_ok=True)
    for f in (src/directory).rglob('*'):
        if f.is_symlink() or not f.is_file() or '__pycache__' in f.parts or f.suffix in {'.pyc','.pyo'}:
            continue
        target=dst/f.relative_to(src)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(f,target)
print('Installed source to:',dst)
print('Existing config.json, private addons, and writing data were preserved.')
print('No processes or services have been touched.')
print('Run: cd "'+str(dst)+'" && '+sys.executable+' kayock_writer.py --base-url YOUR_OPENAI_COMPATIBLE_URL')
PYCODE
