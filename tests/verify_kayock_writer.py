#!/usr/bin/env python3
"""Kayock Writer self-verification (fast, offline, no model needed).

Inspired by FOXAI's core/VERIFY_KAYOCK_WRITER_V2.py: instead of hashing
protected FOXAI sections, this verifies the extracted standalone app:
source compiles, all voice profiles and prompt builders are intact with no
bundled copyrighted poems, the UI ships the three forges in a navigation
tree, config defaults are safe, and storage guards reject traversal.

Run:  python tests/verify_kayock_writer.py [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import py_compile
import sys
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))

from app import __version__  # noqa: E402
from app import ui, voices  # noqa: E402
from app.config import load_config  # noqa: E402
from app.novelforge import NovelForge  # noqa: E402
from app.storage import Store  # noqa: E402

SCHEMA = "kayock.writer.standalone.v1.verification"

EXPECTED_PROFILES = {
    'eric_poet_narrator': 'Eric — Poet/Narrator',
    'eric_short_fiction': 'Eric — Short Fiction',
    'edgar_allan_poe_gothic_lyric': 'Edgar Allan Poe — Gothic Lyric',
    'beneath_the_beats_west_coast_voice': 'Beneath the Beats — West Coast Voice',
    'dust_and_duty_last_gunslinger': 'Dust and Duty — Last Gunslinger Voice',
    'the_forsaken_flame_exiles_voice': 'The Forsaken Flame — Exile’s Voice',
    'robin_hood_merry_outlaw': 'Robin Hood — The Merry Outlaw',
    'zorro_masked_fox': 'Zorro — The Masked Fox',
    'dracula_ancient_count': 'Dracula — The Ancient Count',
    'sherlock_holmes_consulting_mind': 'Sherlock Holmes — The Consulting Mind',
}

# Copyrighted poem lines that must NOT be bundled in the default package.
# Fingerprints identify accidentally bundled private source-poem lines
# without publishing the lines themselves.
PROTECTED_LINE_SHA256 = {
    '8d3d4841edbcb75ae06e7bdae932990a87e8dca0be03ac779101ebcdbc33e1c5',
    '50d22f413a58cc043af87781234ace54a421b2666bb140199158eea3e55054a2',
    '81ab8c428615ca335f5c26ed00f0eb52c70d0c42434e4b68535df4ee99aea90d',
    '33901bf8152fabff74f9b823e26df02bfb6bf36ca55451fb2a5a489a3fcf7f1b',
}


REQUIRED_UI_MARKERS = [
    'Poetry Forge', 'Short Story Forge', 'Novel Forge', 'Story Forge',
    'The Weaver', 'Create a Poem', 'Polish a Poem', 'Start a Story',
    'Browse My Writing', 'Opening a room never changes your saved work.',
    'Selected Lines &amp; Stanza Workshop', 'name="viewport"',
]


def verify() -> dict:
    checks = []

    def check(cid, ok, message=''):
        checks.append({'id': cid, 'ok': bool(ok), 'message': message})
        return ok

    # 1. everything compiles
    sources = sorted(APP_ROOT.glob('*.py')) + sorted((APP_ROOT / 'app').glob('*.py')) \
        + sorted((APP_ROOT / 'tests').glob('*.py'))
    compiled = True
    for path in sources:
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as exc:
            compiled = False
            check(f'compile:{path.name}', False, str(exc))
    check('source_compiles', compiled, f'{len(sources)} files')

    # 2. voice profiles intact
    for profile_id, name in EXPECTED_PROFILES.items():
        profile = voices.POETRY_VOICE_PROFILES.get(profile_id)
        check(f'voice:{profile_id}',
              bool(profile) and profile.get('name') == name,
              name)

    # 3. no copyrighted poem texts bundled
    voices_mod = (APP_ROOT / 'app' / 'voices.py').read_text(encoding='utf-8')
    clean = not any(hashlib.sha256(line.strip().encode('utf-8')).hexdigest() in PROTECTED_LINE_SHA256 for line in voices_mod.splitlines())
    check('no_bundled_source_poems', clean,
          'default package carries derived style settings only')
    check('eric_profile_sources_empty', not voices.ERIC_POET_NARRATOR_PROFILE['sources'],
          'private pack not loaded by default')

    # 4. prompt builders produce the profiles' prompts
    p1 = voices.build_writer_voice_prompt('eric_poet_narrator', 'Recognizably Eric', 'poem')
    p2 = voices.build_writer_voice_prompt('eric_short_fiction', 'Full Eric story voice', 'short_story')
    p3 = voices.poetry_compact_voice_prompt('eric_poet_narrator', 'Strong Eric voice')
    check('prompt_builders', all([p1, p2, p3])
          and 'ERIC — POET/NARRATOR VOICE PROFILE' in p1
          and 'ERIC — SHORT FICTION VOICE PROFILE' in p2
          and 'COMPACT VOICE GUIDE' in p3)

    # 5. UI ships the navigation tree with all forges
    html = ui.render_page()
    missing = [m for m in REQUIRED_UI_MARKERS if m not in html]
    check('ui_navigation_tree', not missing,
          'missing: ' + ', '.join(missing) if missing else 'all markers present')

    # 6. safe default config
    cfg = load_config(None)
    check('default_host_lan', cfg.host == '0.0.0.0', cfg.host)
    check('model_endpoint_configurable',
          cfg.get('model.base_url') and cfg.get('model.chat_path') == '/v1/chat/completions')

    # 7. storage traversal guard
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp))
        forge = NovelForge(store)
        p = forge.novel_path('../../etc/passwd')
        inside = p is None or str(p).startswith(str(store.folder('novel_forge')))
        check('novel_path_traversal_guard', inside)

    failed = [c for c in checks if not c['ok']]
    return {
        'ok': not failed,
        'schema': SCHEMA,
        'app_version': __version__,
        'checks_total': len(checks),
        'checks_failed': len(failed),
        'checks': checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status = 'OK' if result['ok'] else 'FAILED'
        print(f"Kayock Writer verification: {status} "
              f"({result['checks_total'] - result['checks_failed']}"
              f"/{result['checks_total']} checks passed)")
        for c in result['checks']:
            if not c['ok']:
                print(f"  FAIL {c['id']}: {c['message']}")
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
