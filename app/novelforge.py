"""Kayock Writer — Novel Forge (port of FOXAI novel universe functions).

Ported from core/foxai_web.py `novel_root` through `export_story_bible`
(lines ~14472–14663). Universe JSON files and the Markdown mirror keep the
original FOXAI NovelForge schema so existing universes can be dropped in.

Additive improvement: unknown keys already present in an existing universe
file (e.g. structured codex card details) survive a re-save; FOXAI's original
save rebuilt the file from only its known keys.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .storage import Store, atomic_write_text, contained, jread, jwrite, now, slug

KNOWN_UNIVERSE_KEYS = {
    'universe', 'file_name', 'premise', 'characters', 'locations', 'artifacts',
    'timeline', 'mysteries', 'scenes', 'notes', 'created', 'modified',
    'version', 'source',
}


def lines_to_list(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value or '').splitlines() if x.strip()]


class NovelForge:
    def __init__(self, store: Store):
        self.store = store

    # -- paths ---------------------------------------------------------------
    def novel_root(self) -> Path:
        return self.store.folder('novel_forge')

    def novel_path(self, name):
        base = self.novel_root()
        safe = slug(name or 'Untitled_Universe')
        if safe.lower().endswith('.json'):
            safe = safe[:-5]
        p = (base / (safe + '.json')).resolve()
        if not contained(p, base):
            return None
        return p

    def novel_md_path(self, name):
        base = self.novel_root() / 'Markdown'
        base.mkdir(parents=True, exist_ok=True)
        safe = slug(name or 'Untitled_Universe')
        return base / (safe + '.md')

    # -- CRUD ------------------------------------------------------------------
    def list_universes(self):
        base = self.novel_root()
        arr = []
        for p in sorted(base.glob('*.json'),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            d = jread(p, {})
            arr.append({
                'name': p.stem,
                'universe': d.get('universe') or d.get('name') or p.stem,
                'premise': (d.get('premise') or '')[:220],
                'characters': len(d.get('characters', [])) if isinstance(d.get('characters'), list) else 0,
                'locations': len(d.get('locations', [])) if isinstance(d.get('locations'), list) else 0,
                'artifacts': len(d.get('artifacts', [])) if isinstance(d.get('artifacts'), list) else 0,
                'timeline': len(d.get('timeline', [])) if isinstance(d.get('timeline'), list) else 0,
                'mysteries': len(d.get('mysteries', [])) if isinstance(d.get('mysteries'), list) else 0,
                'scenes': len(d.get('scenes', [])) if isinstance(d.get('scenes'), list) else 0,
                'modified': datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
            })
        return {'ok': True, 'universes': arr, 'folder': str(base)}

    def read_universe(self, name):
        p = self.novel_path(name)
        if not p or not p.exists():
            return {'ok': False, 'message': 'Universe not found.'}
        d = jread(p, {})
        d.update({'ok': True, 'file_name': p.stem, 'path': str(p)})
        return d

    def save_universe(self, d):
        name = (d.get('universe') or d.get('name') or 'Untitled Universe').strip()
        if not name:
            return {'ok': False, 'message': 'Universe name is required.'}
        p = self.novel_path(name)
        if not p:
            return {'ok': False, 'message': 'Invalid universe name.'}
        old = jread(p, {}) if p.exists() else {}
        data = {
            'universe': name,
            'file_name': p.stem,
            'premise': (d.get('premise') or '').strip(),
            'characters': lines_to_list(d.get('characters', '')),
            'locations': lines_to_list(d.get('locations', '')),
            'artifacts': lines_to_list(d.get('artifacts', '')),
            'timeline': lines_to_list(d.get('timeline', '')),
            'mysteries': lines_to_list(d.get('mysteries', '')),
            'scenes': lines_to_list(d.get('scenes', '')),
            'notes': (d.get('notes') or '').strip(),
            'created': old.get('created', now()) if old else now(),
            'modified': now(),
            'version': '0.1',
            'source': 'Novel Forge',
        }
        # Additive round-trip: preserve extra structured keys (codex cards etc.)
        # that older saves or external tools stored in this file.
        for key, value in (old or {}).items():
            if key not in KNOWN_UNIVERSE_KEYS and key not in data:
                data[key] = value
        if p.exists():
            self.store.backup_file(p, kind='universes')
        jwrite(p, data)
        md = self.novel_md_path(name)
        if md.exists():
            self.store.backup_file(md, kind='universe_markdown')
        atomic_write_text(md,
            f"# {name}\n\n"
            f"Modified: {data['modified']}\n\n"
            f"## Premise\n\n{data['premise']}\n\n"
            f"## Characters\n\n" + "\n".join(f"- {x}" for x in data['characters']) + "\n\n"
            f"## Locations\n\n" + "\n".join(f"- {x}" for x in data['locations']) + "\n\n"
            f"## Artifacts\n\n" + "\n".join(f"- {x}" for x in data['artifacts']) + "\n\n"
            f"## Timeline\n\n" + "\n".join(f"- {x}" for x in data['timeline']) + "\n\n"
            f"## Mysteries / Unresolved Threads\n\n" + "\n".join(f"- {x}" for x in data['mysteries']) + "\n\n"
            f"## Scenes\n\n" + "\n".join(f"- {x}" for x in data.get('scenes', [])) + "\n\n"
            f"## Notes\n\n{data['notes']}\n",
        )
        return {'ok': True, 'message': f'Saved universe: {name}', 'universe': data,
                'name': p.stem, 'path': str(p), 'markdown': str(md)}

    def duplicate_universe(self, d):
        name = d.get('name', '')
        new_title = (d.get('new_title') or '').strip()
        p = self.novel_path(name)
        if not p or not p.exists():
            return {'ok': False, 'message': 'Universe not found.'}
        old = jread(p, {})
        if not new_title:
            new_title = (old.get('universe') or p.stem) + ' Copy'
        target = self.novel_path(new_title)
        if target is None or target.exists():
            return {'ok': False, 'message': 'Duplicate target already exists or has an invalid name.'}
        old['universe'] = new_title
        old['source'] = 'Novel Forge Duplicate'
        return self.save_universe(old)

    def rename_universe(self, d):
        name = d.get('name', '')
        new_title = (d.get('new_title') or '').strip()
        if not new_title:
            return {'ok': False, 'message': 'New universe name is required.'}
        p = self.novel_path(name)
        if not p or not p.exists():
            return {'ok': False, 'message': 'Universe not found.'}
        old = jread(p, {})
        old_title = old.get('universe') or p.stem
        old['universe'] = new_title
        result = self.save_universe(old)
        if result.get('ok') and result.get('name') != p.stem:
            try:
                p.unlink()
                md = self.novel_md_path(name)
                if md.exists():
                    md.unlink()
            except Exception:
                pass
        return result

    def delete_universe(self, name):
        p = self.novel_path(name)
        if not p or not p.exists():
            return {'ok': False, 'message': 'Universe not found.'}
        title = jread(p, {}).get('universe') or p.stem
        try:
            p.unlink()
            md = self.novel_md_path(name)
            if md.exists():
                md.unlink()
        except Exception as e:
            return {'ok': False, 'message': f'Delete failed: {e}'}
        return {'ok': True, 'message': f'Deleted universe: {title}'}

    # -- story bible export -------------------------------------------------------
    def export_story_bible(self, d):
        base = self.store.folder('novel_exports')
        universe = (d.get('universe') or 'Untitled Universe').strip()
        safe = slug(universe)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix = f"{safe}_Story_Bible_{stamp}"
        json_path = base / (prefix + '.json')
        md_path = base / (prefix + '.md')
        txt_path = base / (prefix + '.txt')
        summary = d.get('summary') or {}
        bible = d.get('story_bible') or ''
        codex = d.get('codex') or {}
        export_data = {
            'universe': universe,
            'exported': now(),
            'summary': summary,
            'codex': codex,
            'story_bible': bible,
            'source': 'Novel Forge Story Bible Export',
            'version': '1.0',
        }
        jwrite(json_path, export_data)
        summary_md = "\n".join([
            f"- Characters: {summary.get('characters','')}",
            f"- Locations: {summary.get('locations','')}",
            f"- Artifacts: {summary.get('artifacts','')}",
            f"- Timeline Events: {summary.get('timeline','')}",
            f"- Mysteries: {summary.get('mysteries','')}",
            f"- Readiness: {summary.get('readiness','')}",
        ])
        md_text = (f"# {universe} — Story Bible\n\nExported: {export_data['exported']}\n\n"
                   f"## Dashboard Summary\n\n{summary_md}\n\n---\n\n{bible}\n")
        md_path.write_text(md_text, encoding='utf-8')
        txt_path.write_text(md_text.replace('# ', '').replace('## ', ''), encoding='utf-8')
        return {
            'ok': True,
            'message': f'Exported Story Bible for {universe}',
            'folder': str(base),
            'json': str(json_path),
            'markdown': str(md_path),
            'text': str(txt_path),
        }
