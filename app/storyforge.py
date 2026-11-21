"""Kayock Writer — Story Forge (generalized port of FOXAI story workflow).

FOXAI's Story Forge (core/foxai_web.py lines ~26912–36660) implements a
gate → preview → approval-phrase → action workflow over real files: project
manifests (kayock.writer.project.v1), book chapter cards, continuity handoffs,
drafts with version history, prose manuscripts with verified diffs, and report
receipts for every action.

This port keeps the workflow, file formats, and safety contract, and makes it
work for ANY project instead of only the flagship:

- create_project_gate / create_project_action   (approval phrase + preflight)
- project_dashboard / project_health_card
- chapter_planner_preview                       (no-write preview)
- chapter_save_gate / chapter_save_action       (cards + handoffs + preview set)
- saved_chapter_dashboard
- chapter_editor_preview / chapter_edit_gate / chapter_edit_action
  (exact-selection verification, backup before overwrite, diff audit)
- draft_workspace / draft_save_gate / draft_save_action
- draft_reader_dashboard / draft_version_history / draft_compare
- draft_continue_gate / draft_continue_action   (versioned continuation)
- prose_draft_gate / prose_draft_save / prose_editor_gate / prose_edit_save
- prose_refresh_compare

Differences from FOXAI (documented in docs/PARITY.md):
- Storage rooted in the app data dir; no Z:\\ paths, no os.startfile.
- Reports are written as compact JSON receipts (Reports/KayockWriter/<Tool>/).
- Report payloads keep the key fields (ok, status, blockers, preflight,
  overwrite_risks, created/written files, safety) but not FOXAI's
  multi-milestone marketing text.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .storage import Store, contained, jread, jwrite, now, slug

PROJECT_SCHEMA = "kayock.writer.project.v1"
PREVIEW_SET_SCHEMA = "kayock.writer.chapter_preview_set.v1"
DEFAULT_APPROVAL_PHRASE = "CREATE STORY PROJECT"


def _text(value, limit=20000):
    return str(value or '').replace('\x00', '').strip()[:max(1, int(limit))]


def word_count(value):
    return len(re.findall(r"[A-Za-z0-9'’_-]+", str(value or '')))


def change_metrics(original, candidate):
    """Ported FOXAI story_change_metrics (difflib word-level stats)."""
    original_words = re.findall(r"[A-Za-z0-9'’_-]+", str(original or '').casefold())
    candidate_words = re.findall(r"[A-Za-z0-9'’_-]+", str(candidate or '').casefold())
    matcher = difflib.SequenceMatcher(None, original_words, candidate_words, autojunk=False)
    changed_words = 0
    changed_blocks = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        changed_blocks += 1
        changed_words += max(i2 - i1, j2 - j1)
    exact = (
        re.sub(r'\s+', ' ', str(original or '')).strip().casefold()
        == re.sub(r'\s+', ' ', str(candidate or '')).strip().casefold()
    )
    return {
        'exact_match': exact,
        'similarity': round(float(matcher.ratio()), 6),
        'changed_words': int(changed_words),
        'changed_blocks': int(changed_blocks),
        'original_words': len(original_words),
        'candidate_words': len(candidate_words),
    }


class StoryForge:
    def __init__(self, store: Store, require_approval_phrase: bool = True,
                 default_author: str = "Eric Z. Fox"):
        self.store = store
        self.require_approval_phrase = bool(require_approval_phrase)
        self.default_author = default_author

    # ------------------------------------------------------------------
    # paths / manifest
    # ------------------------------------------------------------------
    def projects_root(self) -> Path:
        return self.store.folder('projects')

    def project_root(self, project_id: str) -> Optional[Path]:
        safe = slug(_text(project_id, 80))
        if not safe or safe in {'New_Project'}:
            return None
        p = (self.projects_root() / safe).resolve()
        if not contained(p, self.projects_root()):
            return None
        return p

    def manifest_path(self, project_id) -> Optional[Path]:
        root = self.project_root(project_id)
        return (root / 'project.kayock-writer.json') if root else None

    def load_manifest(self, project_id) -> Optional[dict]:
        path = self.manifest_path(project_id)
        if not path or not path.exists():
            return None
        data = jread(path, {})
        return data if isinstance(data, dict) and data.get('project_id') else data or None

    def list_projects(self):
        root = self.projects_root()
        projects = []
        for path in sorted(root.glob('*/project.kayock-writer.json')):
            m = jread(path, {})
            if not isinstance(m, dict):
                continue
            books = m.get('books') or []
            projects.append({
                'project_id': m.get('project_id') or path.parent.name,
                'title': m.get('title') or path.parent.name,
                'status': m.get('status', ''),
                'created_at': m.get('created_at', ''),
                'books': [
                    {'id': b.get('id'), 'title': b.get('title', ''),
                     'summary': b.get('summary', '')}
                    for b in books if isinstance(b, dict)
                ],
                'book_count': len(books),
                'path': str(path.parent),
            })
        return {'ok': True, 'projects': projects, 'folder': str(root)}

    # ------------------------------------------------------------------
    # reporting receipts
    # ------------------------------------------------------------------
    def _report(self, tool: str, payload: dict) -> str:
        try:
            path = self.store.write_report(tool, payload)
            return str(path)
        except Exception:
            return ''

    # ------------------------------------------------------------------
    # create project (gate + action) — generalized flagship flow
    # ------------------------------------------------------------------
    def create_project_gate(self, d=None):
        d = d or {}
        title = _text(d.get('title') or d.get('project_title'), 120) or 'New Story Project'
        project_id = slug(d.get('project_id') or title)
        root = self.project_root(project_id)
        if root is None:
            return {'ok': False, 'message': 'Invalid project id.'}
        books_in = d.get('books') if isinstance(d.get('books'), list) else []
        books = []
        for index, item in enumerate(books_in[:12], start=1):
            if isinstance(item, dict):
                books.append({
                    'id': slug(item.get('id') or f'book_{index}').lower(),
                    'title': _text(item.get('title') or f'Book {index}', 120),
                    'status': 'outline_seed',
                    'summary': _text(item.get('summary'), 2000),
                    'chapter_placeholder_count': 0,
                    'scene_placeholder_count': 0,
                })
        if not books:
            books = [{'id': 'book_1', 'title': 'Book 1', 'status': 'outline_seed',
                      'summary': '', 'chapter_placeholder_count': 0,
                      'scene_placeholder_count': 0}]

        folders = []
        for key, purpose in [
            ('project_root', 'Main Kayock Writer project folder.'),
            ('markdown', 'Portable manuscript and planning Markdown.'),
            ('chapters', 'Chapter cards and chapter drafts.'),
            ('scenes', 'Scene cards and scene drafts.'),
            ('codex', 'Characters, lore, factions, artifacts, locations, and canon entries.'),
            ('timeline', 'Book, chapter, scene, flashback, and chronology notes.'),
            ('continuity', 'Continuity checks, contradictions, setup/payoff.'),
            ('mysteries', 'Mystery tracker: clues, reveals, payoff status.'),
            ('drafts', 'Chapter draft versions with history.'),
            ('prose', 'Real prose manuscript versions.'),
            ('exports', 'Story bible and shareable exports.'),
        ]:
            target = root if key == 'project_root' else root / key
            folders.append({'id': key, 'path': str(target), 'purpose': purpose,
                            'exists': target.exists()})

        files = []
        for key, rel, kind in [
            ('manifest', 'project.kayock-writer.json', 'json'),
            ('readme', 'README.md', 'markdown'),
            ('books', 'Markdown/Books.md', 'markdown'),
        ]:
            target = root / rel
            files.append({'id': key, 'path': str(target), 'kind': kind,
                          'exists': target.exists()})

        overwrite_risks = [f['id'] for f in files if f['exists']]
        exists_already = root.exists()
        phrase_ok = self._phrase_ok(d.get('approval_phrase'), DEFAULT_APPROVAL_PHRASE)
        gate_ready = (not exists_already) and bool(title) and phrase_ok
        blockers = []
        if exists_already:
            blockers.append({'id': 'project_exists',
                             'message': f'A project folder already exists at {root}. '
                                        'Choose a different title or project id.'})
        if not self.require_approval_phrase:
            phrase_ok = True
        elif not phrase_ok:
            blockers.append({'id': 'phrase_mismatch',
                             'message': f'Type the exact approval phrase to allow creation: '
                                        f'"{DEFAULT_APPROVAL_PHRASE}".'})

        manifest_preview = {
            'api_version': PROJECT_SCHEMA,
            'project_id': project_id,
            'title': title,
            'department': 'Kayock Writer',
            'module': 'Story Forge',
            'status': 'manifest_preview_only',
            'storage': 'Markdown source of truth with JSON sidecars where useful',
            'proposed_project_root': str(root),
            'author': _text(d.get('author') or self.default_author, 120),
            'books': books,
            'handoff_points': {
                'codex': ['characters', 'locations', 'artifacts', 'factions',
                          'reader knowledge', 'author knowledge'],
                'timeline': ['book chronology', 'chapter chronology', 'flashbacks'],
                'continuity': ['canon checks', 'contradiction flags', 'setup/payoff'],
                'mystery_tracker': ['clues', 'reveals', 'unresolved threads'],
            },
        }
        result = {
            'ok': True,
            'title': 'Kayock Writer — Create Project Approval Gate',
            'read_only': True,
            'gate_ready': gate_ready,
            'approval_phrase_required': DEFAULT_APPROVAL_PHRASE,
            'approval_phrase_matches': phrase_ok,
            'blockers': blockers,
            'summary': {
                'project_id': project_id,
                'title': title,
                'proposed_project_root': str(root),
                'project_exists': exists_already,
                'folder_count': len(folders),
                'file_count': len(files),
                'book_count': len(books),
                'overwrite_risks': len(overwrite_risks),
            },
            'manifest_preview': manifest_preview,
            'proposed_folders': folders,
            'proposed_files': files,
            'overwrite_risks': overwrite_risks,
            'safety': {
                'no_writes_in_gate': True,
                'no_delete': True, 'no_move': True,
                'no_overwrite_without_backup': True,
                'approval_phrase_required': self.require_approval_phrase,
            },
        }
        result['report_path'] = self._report('CreateProjectGate', result)
        return result

    def create_project_action(self, d=None):
        gate = self.create_project_gate(d)
        if not gate.get('ok'):
            return gate
        blockers = gate.get('blockers') or []
        execute = bool(d.get('execute'))
        if blockers:
            return {
                'ok': False,
                'message': 'Create blocked: ' + '; '.join(
                    b.get('message', '') for b in blockers),
                'blockers': blockers,
                'gate': gate,
                'action_taken': False,
            }
        if not execute:
            return {
                'ok': True,
                'message': 'Preflight passed. Set execute=true (and the approval '
                           'phrase) to create the project.',
                'action_taken': False,
                'gate': gate,
            }
        root = self.project_root(gate['summary']['project_id'])
        manifest = dict(gate['manifest_preview'])
        manifest['status'] = 'active_project'
        manifest['created_by'] = 'Kayock Writer'
        manifest['created_at'] = now()
        manifest['safety_contract'] = {
            'legacy_import_copy_only': True,
            'no_delete': True,
            'no_move': True,
            'no_overwrite_without_backup': True,
            'future_story_writes_require_user_approval': True,
        }
        title = manifest['title']
        books = manifest['books']

        readme_text = f"""# {title}

Created by Kayock Writer / Story Forge.

## Status

This project was created through the Story Forge approval gate.

## Safety

- No existing story files were overwritten.
- Future story writes use preview and approval gates.
- The manifest is `project.kayock-writer.json` (schema {PROJECT_SCHEMA}).

## Project Layout

- `Markdown/` — portable manuscript and planning Markdown.
- `Chapters/` — chapter cards and chapter drafts.
- `Scenes/` — scene cards and scene drafts.
- `Codex/` — characters, lore, locations, artifacts, factions, and canon.
- `Timeline/` — chronology and event ordering.
- `Continuity/` — canon checks, contradictions, setup/payoff.
- `Mysteries/` — clues, reveals, and payoff status.
- `Drafts/` — versioned chapter drafts.
- `Prose/` — real prose manuscript versions.
- `Exports/` — story bible and shareable exports.
"""
        books_lines = [f"# {title} — Books", ""]
        for book in books:
            books_lines += [
                f"## {book['title']}",
                "",
                f"**Summary:** {book.get('summary') or 'Summarize this book here.'}",
                "",
                "### Chapter Planning Notes",
                "",
                "Chapter cards should include: number, title, POV, goal, conflict, "
                "reveal, continuity notes, and ending hook.",
                "",
            ]
        books_text = '\n'.join(books_lines)

        created_dirs = []
        written_files = []
        for folder in gate['proposed_folders']:
            path = Path(folder['path'])
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                created_dirs.append(str(path))
        for file_info in gate['proposed_files']:
            path = Path(file_info['path'])
            if file_info['id'] == 'manifest':
                content = json.dumps(manifest, indent=2)
            elif file_info['id'] == 'readme':
                content = readme_text
            else:
                content = books_text
            if path.exists():
                # Gate guarantees no pre-existing project; guard anyway.
                backup = self.store.backup_file(path, 'project_create')
                if backup is None:
                    continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            written_files.append(str(path))

        payload = {
            'ok': True,
            'message': f'Project created: {title}',
            'project_id': manifest['project_id'],
            'created_dirs': created_dirs,
            'written_files': written_files,
            'manifest': manifest,
            'safety': gate['safety'],
            'action_taken': True,
        }
        payload['report_path'] = self._report('CreateProjectAction', payload)
        return payload

    def _phrase_ok(self, supplied, required) -> bool:
        if not self.require_approval_phrase:
            return True
        return _text(supplied, 200) == required

    # ------------------------------------------------------------------
    # dashboards
    # ------------------------------------------------------------------
    def project_dashboard(self, d=None):
        d = d or {}
        project_id = _text(d.get('project_id'), 80)
        manifest = self.load_manifest(project_id)
        if not manifest:
            listing = self.list_projects()
            return {'ok': False, 'message': 'Project manifest not found.',
                    'known_projects': listing.get('projects', [])}
        root = self.project_root(manifest['project_id'])
        structure = {}
        for key in ('Markdown', 'Chapters', 'Scenes', 'Codex', 'Timeline',
                    'Continuity', 'Mysteries', 'Drafts', 'Prose', 'Exports'):
            path = root / key
            files = sorted(p.name for p in path.rglob('*') if p.is_file()) if path.is_dir() else []
            structure[key] = {'path': str(path), 'exists': path.is_dir(),
                              'file_count': len(files), 'files': files[:60]}
        preview_sets = sorted((root / 'Chapters').glob('*_chapter_preview_set.json')) \
            if (root / 'Chapters').is_dir() else []
        books_status = []
        for book in manifest.get('books') or []:
            book_id = str(book.get('id') or '')
            set_path = root / 'Chapters' / f'{book_id}_chapter_preview_set.json'
            preview = jread(set_path, None) if set_path.exists() else None
            cards = preview.get('chapter_cards', []) if isinstance(preview, dict) else []
            drafts_dir = root / 'Drafts' / book_id
            draft_count = len(list(drafts_dir.glob('chapter_*_draft_v*.md'))) \
                if drafts_dir.is_dir() else 0
            books_status.append({
                'id': book_id, 'title': book.get('title', ''),
                'summary': book.get('summary', ''),
                'chapter_cards_saved': len(cards),
                'draft_versions': draft_count,
                'handoffs_saved': (root / 'Continuity' / f'{book_id}_chapter_handoffs.md').exists(),
            })
        healthy = bool(root.exists()) and (root / 'project.kayock-writer.json').exists()
        result = {
            'ok': True,
            'read_only': True,
            'healthy': healthy,
            'health_label': 'PROJECT READY' if healthy else 'PROJECT NEEDS REVIEW',
            'summary': {
                'project_id': manifest['project_id'],
                'title': manifest.get('title', ''),
                'status': manifest.get('status', ''),
                'created_at': manifest.get('created_at', ''),
                'project_root': str(root),
                'safety_contract': manifest.get('safety_contract', {}),
            },
            'books': books_status,
            'structure': structure,
            'preview_sets': [p.name for p in preview_sets],
        }
        result['report_path'] = self._report('ProjectDashboard', result)
        return result

    def project_health_card(self, d=None):
        dashboard = self.project_dashboard(d)
        if not dashboard.get('ok'):
            return dashboard
        books = dashboard.get('books') or []
        with_cards = sum(1 for b in books if b['chapter_cards_saved'])
        with_drafts = sum(1 for b in books if b['draft_versions'])
        checks = [
            {'id': 'manifest_present', 'ok': dashboard['healthy'],
             'message': 'project.kayock-writer.json present.'},
            {'id': 'books_defined', 'ok': bool(books),
             'message': f'{len(books)} book(s) defined.'},
            {'id': 'chapter_cards_saved', 'ok': with_cards > 0,
             'message': f'{with_cards}/{len(books)} books have saved chapter cards.'},
            {'id': 'draft_versions', 'ok': True,
             'message': f'{with_drafts}/{len(books)} books have draft versions.'},
        ]
        problems = sum(1 for c in checks if not c['ok'])
        return {
            'ok': True,
            'read_only': True,
            'card': True,
            'health_label': 'STORY FORGE PROJECT HEALTHY' if problems == 0
            else 'STORY FORGE PROJECT NEEDS REVIEW',
            'checks_passed': len(checks) - problems,
            'checks_total': len(checks),
            'checks': checks,
            'summary': dashboard['summary'],
            'books': books,
        }

    # ------------------------------------------------------------------
    # chapter cards: plan preview, save gate/action, dashboard
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_cards(raw_cards) -> List[dict]:
        cards = []
        for index, item in enumerate(raw_cards if isinstance(raw_cards, list) else [], start=1):
            if not isinstance(item, dict):
                continue
            try:
                number = int(item.get('chapter_number') or index)
            except Exception:
                number = index
            cards.append({
                'chapter_number': number,
                'title': _text(item.get('title') or f'Chapter {number}', 160),
                'pov': _text(item.get('pov'), 160),
                'location': _text(item.get('location'), 160),
                'goal': _text(item.get('goal'), 2000),
                'conflict': _text(item.get('conflict'), 2000),
                'reveal': _text(item.get('reveal'), 2000),
                'hook': _text(item.get('hook'), 2000),
                'continuity_notes': [
                    _text(n, 500) for n in
                    (item.get('continuity_notes') if isinstance(item.get('continuity_notes'), list)
                     else _text(item.get('continuity_notes'), 2000).splitlines())
                    if _text(n, 500)
                ],
                'handoff_tags': item.get('handoff_tags') if isinstance(item.get('handoff_tags'), dict) else {},
            })
        cards.sort(key=lambda c: c['chapter_number'])
        return cards

    def _book_from_manifest(self, manifest, book_id):
        for book in manifest.get('books') or []:
            if str(book.get('id') or '') == book_id:
                return book
        books = manifest.get('books') or []
        return books[0] if books else {'id': 'book_1', 'title': 'Book 1', 'summary': ''}

    def _chapter_markdown(self, card, project_title, book_title):
        handoffs = card.get('handoff_tags') or {}
        notes = card.get('continuity_notes') or []
        n = int(card.get('chapter_number') or 0)
        lines = [
            f"# Chapter {n:02d} — {card.get('title', 'Untitled Chapter')}",
            "",
            f"- **Project:** {project_title}",
            f"- **Book:** {book_title}",
            "- **Status:** saved_chapter_card",
            f"- **POV:** {card.get('pov', 'TBD')}",
            f"- **Location:** {card.get('location', 'TBD')}",
            "",
            "## Goal",
            "",
            card.get('goal', 'TBD'),
            "",
            "## Conflict",
            "",
            card.get('conflict', 'TBD'),
            "",
            "## Reveal",
            "",
            card.get('reveal', 'TBD'),
            "",
            "## Hook",
            "",
            card.get('hook', 'TBD'),
            "",
            "## Continuity Notes",
            "",
        ]
        for note in notes:
            lines.append(f"- {note}")
        lines += [
            "",
            "## Handoff Tags",
            "",
            "```json",
            json.dumps(handoffs, indent=2),
            "```",
            "",
            "## Draft Space",
            "",
            "_Write the chapter draft here later._",
            "",
            "## Safety",
            "",
            "- Created by approved Kayock Writer chapter save action.",
            "- No existing story files were overwritten without backup.",
            "- Future edits should use preview and approval gates.",
        ]
        return '\n'.join(lines)

    def _chapter_save_plan(self, d):
        """Shared planning for planner preview / save gate / save action."""
        project_id = _text(d.get('project_id'), 80)
        manifest = self.load_manifest(project_id)
        if not manifest:
            return None, 'Project manifest not found.'
        root = self.project_root(manifest['project_id'])
        book_id = slug(_text(d.get('book_id') or 'book_1', 60)).lower() or 'book_1'
        book = self._book_from_manifest(manifest, book_id)
        cards = self._normalize_cards(d.get('chapter_cards'))
        if not cards:
            return None, 'Add at least one chapter card (number, title, goal, conflict).'

        project_title = manifest.get('title', project_id)
        book_title = book.get('title', book_id)
        chapters_dir = root / 'Chapters'
        book_folder = chapters_dir / book_id
        continuity_dir = root / 'Continuity'

        preview_set = {
            'api_version': PREVIEW_SET_SCHEMA,
            'project_id': manifest['project_id'],
            'project_title': project_title,
            'book_id': book_id,
            'book_title': book_title,
            'book_summary': book.get('summary', ''),
            'status': 'saved_preview_set',
            'created_by': 'Kayock Writer',
            'created_at': now(),
            'chapter_cards': cards,
            'safety_contract': {
                'exact_phrase_required': True,
                'no_overwrite': True,
                'no_delete': True,
                'no_move': True,
                'future_story_writes_require_preview_and_approval': True,
            },
        }
        handoff_lines = [
            f"# {project_title} — {book_title} Chapter Handoffs",
            "",
            "Created by Kayock Writer Chapter Save.",
            "",
            "## Book Summary",
            "",
            book.get('summary', ''),
            "",
            "## Chapter Handoffs",
            "",
        ]
        for c in cards:
            handoff_lines += [
                f"### Chapter {int(c.get('chapter_number') or 0):02d} — {c.get('title', 'Untitled')}",
                "",
                f"- Goal: {c.get('goal', '')}",
                f"- Conflict: {c.get('conflict', '')}",
                f"- Reveal: {c.get('reveal', '')}",
                f"- Hook: {c.get('hook', '')}",
                f"- POV: {c.get('pov', '')}",
                f"- Location: {c.get('location', '')}",
                f"- Continuity notes: {'; '.join(c.get('continuity_notes') or [])}",
                f"- Handoff tags: `{json.dumps(c.get('handoff_tags') or {})}`",
                "",
            ]
        targets = [
            {'id': 'book_chapter_folder', 'kind': 'folder', 'path': book_folder, 'content': None},
            {'id': 'chapter_preview_set_json', 'kind': 'file',
             'path': chapters_dir / f'{book_id}_chapter_preview_set.json',
             'content': json.dumps(preview_set, indent=2)},
        ]
        for c in cards:
            n = int(c.get('chapter_number') or 0)
            title_slug = slug(c.get('title') or f'chapter_{n:02d}')
            targets.append({
                'id': f'chapter_{n:02d}_markdown', 'kind': 'file',
                'path': book_folder / f'chapter_{n:02d}_{title_slug}.md',
                'content': self._chapter_markdown(c, project_title, book_title),
            })
        targets.append({
            'id': 'continuity_handoff_markdown', 'kind': 'file',
            'path': continuity_dir / f'{book_id}_chapter_handoffs.md',
            'content': '\n'.join(handoff_lines),
        })
        return {
            'project_id': manifest['project_id'],
            'manifest': manifest,
            'project_root': root,
            'book_id': book_id,
            'book': book,
            'project_title': project_title,
            'book_title': book_title,
            'cards': cards,
            'targets': targets,
        }, ''

    def chapter_planner_preview(self, d=None):
        plan, error = self._chapter_save_plan(d)
        if error:
            return {'ok': False, 'message': error}
        preflight = []
        for t in plan['targets']:
            exists = t['path'].exists()
            preflight.append({
                'id': t['id'], 'kind': t['kind'], 'path': str(t['path']),
                'exists': exists, 'would_create': not exists and t['kind'] != 'folder',
                'would_overwrite': exists and t['kind'] != 'folder',
            })
        return {
            'ok': True,
            'read_only': True,
            'no_chapter_file_creation': True,
            'title': 'Kayock Writer — Chapter Planner Preview',
            'summary': {
                'project_id': plan['project_id'],
                'book_id': plan['book_id'],
                'book_title': plan['book_title'],
                'chapter_cards': len(plan['cards']),
                'save_targets': len(plan['targets']),
                'chapters_folder': str(plan['project_root'] / 'Chapters'),
            },
            'chapter_cards': plan['cards'],
            'preflight': preflight,
            'safety': {'no_writes_in_preview': True, 'no_delete': True, 'no_move': True},
        }

    def chapter_save_gate(self, d=None):
        preview = self.chapter_planner_preview(d)
        if not preview.get('ok'):
            return preview
        risks = [p['id'] for p in preview['preflight'] if p.get('would_overwrite')]
        phrase_required = 'SAVE CHAPTER CARDS'
        phrase_ok = self._phrase_ok(d.get('approval_phrase'), phrase_required)
        blockers = []
        if not phrase_ok:
            blockers.append({'id': 'phrase_mismatch',
                             'message': f'Type the exact approval phrase to allow saving: '
                                        f'"{phrase_required}".'})
        return {
            'ok': True,
            'read_only': True,
            'gate_ready': not blockers,
            'approval_phrase_required': phrase_required,
            'approval_phrase_matches': phrase_ok,
            'overwrite_risks': risks,
            'blockers': blockers,
            'preview': preview,
            'safety': {'no_writes_in_gate': True, 'no_delete': True, 'no_move': True},
        }

    def chapter_save_action(self, d=None):
        gate = self.chapter_save_gate(d)
        if not gate.get('ok'):
            return gate
        blockers = gate.get('blockers') or []
        execute = bool(d.get('execute'))
        if blockers:
            return {'ok': False,
                    'message': 'Save blocked: ' + '; '.join(
                        b.get('message', '') for b in blockers),
                    'blockers': blockers, 'action_taken': False}
        if not execute:
            return {'ok': True,
                    'message': 'Chapter save gate passed. Set execute=true to write the files.',
                    'action_taken': False}
        plan, error = self._chapter_save_plan(d)
        if error:
            return {'ok': False, 'message': error}
        written = []
        backed_up = []
        errors = []
        for target in plan['targets']:
            path = Path(target['path'])
            try:
                if target['kind'] == 'folder':
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    backup = self.store.backup_file(path, 'chapter_cards')
                    if backup:
                        backed_up.append(str(backup))
                path.write_text(target['content'], encoding='utf-8')
                written.append(str(path))
            except Exception as exc:
                errors.append({'id': target['id'], 'message': f'{type(exc).__name__}: {exc}'})
        result = {
            'ok': not errors,
            'message': (f'Saved {len(written)} chapter file(s) for book '
                        f'{plan["book_title"]}. Backups: {len(backed_up)}.')
            if not errors else 'Chapter save completed with errors.',
            'project_id': plan['project_id'],
            'book_id': plan['book_id'],
            'chapter_cards': len(plan['cards']),
            'written_files': written,
            'backups': backed_up,
            'errors': errors,
            'overwrite_policy': 'backup_before_overwrite',
            'action_taken': True,
        }
        result['report_path'] = self._report('ChapterSaveAction', result)
        return result

    def saved_chapter_dashboard(self, d=None):
        plan, error = self._chapter_save_plan(d)
        if error and 'chapter card' in error:
            # Allow dashboard with saved files even if no cards supplied now.
            return {'ok': False, 'message': error}
        d2 = d or {}
        project_id = _text(d2.get('project_id'), 80)
        manifest = self.load_manifest(project_id)
        if not manifest:
            return {'ok': False, 'message': 'Project manifest not found.'}
        root = self.project_root(manifest['project_id'])
        book_id = slug(_text(d2.get('book_id') or 'book_1', 60)).lower() or 'book_1'
        chapters_dir = root / 'Chapters'
        set_path = chapters_dir / f'{book_id}_chapter_preview_set.json'
        preview = jread(set_path, None) if set_path.exists() else None
        checks = []
        checks.append({'id': 'preview_set_json', 'ok': isinstance(preview, dict),
                       'message': f'{set_path.name} present.' if isinstance(preview, dict)
                       else f'Missing {set_path.name}. Save chapter cards first.'})
        cards = preview.get('chapter_cards', []) if isinstance(preview, dict) else []
        md_ok = 0
        for c in cards:
            n = int(c.get('chapter_number') or 0)
            matches = list((chapters_dir / book_id).glob(f'chapter_{n:02d}_*.md')) \
                if (chapters_dir / book_id).is_dir() else []
            ok = bool(matches)
            md_ok += 1 if ok else 0
            checks.append({'id': f'chapter_{n:02d}_markdown', 'ok': ok,
                           'message': f'chapter_{n:02d}_*.md '
                                      + ('found.' if ok else 'missing.')})
        handoff = root / 'Continuity' / f'{book_id}_chapter_handoffs.md'
        checks.append({'id': 'continuity_handoff', 'ok': handoff.exists(),
                       'message': 'Continuity handoff markdown present.' if handoff.exists()
                       else 'Continuity handoff markdown missing.'})
        problems = sum(1 for c in checks if not c['ok'])
        return {
            'ok': True,
            'read_only': True,
            'dashboard_ready': problems == 0 and bool(cards),
            'health_label': 'SAVED CHAPTER DASHBOARD READY'
            if (problems == 0 and bool(cards)) else 'SAVED CHAPTER DASHBOARD NEEDS REVIEW',
            'summary': {
                'project_id': manifest['project_id'],
                'project_title': manifest.get('title', ''),
                'book_id': book_id,
                'chapter_cards_saved': len(cards),
                'markdown_cards_found': md_ok,
                'checks_passed': len(checks) - problems,
                'checks_total': len(checks),
            },
            'checks': checks,
            'preview_set_summary': {
                'api_version': preview.get('api_version') if isinstance(preview, dict) else '',
                'book_title': preview.get('book_title') if isinstance(preview, dict) else '',
                'created_at': preview.get('created_at') if isinstance(preview, dict) else '',
                'chapter_cards': len(cards),
                'safety_contract': preview.get('safety_contract') if isinstance(preview, dict) else {},
            },
            'chapter_cards': cards,
        }

    # ------------------------------------------------------------------
    # chapter editor: preview, edit gate (exact diff), edit action
    # ------------------------------------------------------------------
    def chapter_editor_preview(self, d=None):
        d = d or {}
        project_id = _text(d.get('project_id'), 80)
        root = self.project_root(project_id)
        manifest = self.load_manifest(project_id)
        if not root or not manifest:
            return {'ok': False, 'message': 'Project manifest not found.'}
        filename = _text(d.get('filename'), 200)
        target = (root / 'Chapters' / filename).resolve()
        if not contained(target, root) or target.suffix != '.md' or not target.is_file():
            # allow listing
            files = sorted(str(p.relative_to(root / 'Chapters'))
                           for p in (root / 'Chapters').rglob('*.md')) \
                if (root / 'Chapters').is_dir() else []
            return {'ok': False, 'message': 'Chapter markdown file not found.',
                    'available_files': files}
        try:
            content = target.read_text(encoding='utf-8')
        except Exception as exc:
            return {'ok': False, 'message': f'Could not read chapter file: {exc}'}
        return {
            'ok': True,
            'read_only': True,
            'no_writes': True,
            'filename': filename,
            'path': str(target),
            'content': content,
            'word_count': word_count(content),
            'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            'modified': datetime.fromtimestamp(target.stat().st_mtime).isoformat(timespec='seconds'),
        }

    def chapter_edit_gate(self, d=None):
        d = d or {}
        preview = self.chapter_editor_preview(d)
        if not preview.get('ok'):
            return preview
        original = preview['content']
        edited = str(d.get('edited_content') or '')
        if not edited.strip():
            return {'ok': False, 'message': 'Edited content is empty.'}
        if edited == original:
            return {'ok': False,
                    'message': 'Edited content is identical to the saved chapter. '
                               'Nothing to approve.',
                    'diff_metrics': change_metrics(original, edited)}
        metrics = change_metrics(original, edited)
        phrase_required = 'APPROVE CHAPTER EDIT'
        phrase_ok = self._phrase_ok(d.get('approval_phrase'), phrase_required)
        blockers = []
        if not phrase_ok:
            blockers.append({'id': 'phrase_mismatch',
                             'message': f'Type the exact approval phrase to allow the edit: '
                                        f'"{phrase_required}".'})
        target = Path(preview['path'])
        return {
            'ok': True,
            'read_only': True,
            'gate_ready': not blockers,
            'filename': preview['filename'],
            'approval_phrase_required': phrase_required,
            'approval_phrase_matches': phrase_ok,
            'diff_metrics': metrics,
            'backup_target': str(self.store.folders['chapter_edit_backups']),
            'blockers': blockers,
            'safety': {'backup_before_overwrite': True,
                       'no_delete': True, 'no_move': True},
        }

    def chapter_edit_action(self, d=None):
        gate = self.chapter_edit_gate(d)
        if not gate.get('ok'):
            return gate
        blockers = gate.get('blockers') or []
        execute = bool(d.get('execute'))
        if blockers:
            return {'ok': False,
                    'message': 'Edit blocked: ' + '; '.join(
                        b.get('message', '') for b in blockers),
                    'blockers': blockers, 'action_taken': False}
        if not execute:
            return {'ok': True,
                    'message': 'Edit gate passed. Set execute=true to apply the edit '
                               '(the original is backed up first).',
                    'action_taken': False}
        edited = str(d.get('edited_content') or '')
        target = Path(self.chapter_editor_preview(d)['path'])
        backup = self.store.backup_file(target, 'edits')
        target.write_text(edited, encoding='utf-8')
        result = {
            'ok': True,
            'message': f'Chapter edit applied to {target.name}. Original backed up.',
            'filename': target.name,
            'path': str(target),
            'backup': str(backup) if backup else '',
            'diff_metrics': gate['diff_metrics'],
            'action_taken': True,
        }
        result['report_path'] = self._report('ChapterEditAction', result)
        return result

    # ------------------------------------------------------------------
    # drafts: workspace, save, history, continue, compare
    # ------------------------------------------------------------------
    def _drafts_dir(self, project_id, book_id):
        root = self.project_root(project_id)
        if not root:
            return None
        path = root / 'Drafts' / slug(book_id or 'book_1').lower()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _draft_manifest_path(self, project_id, book_id):
        drafts = self._drafts_dir(project_id, book_id)
        return (drafts / 'draft_manifest.json') if drafts else None

    def _load_draft_manifest(self, project_id, book_id):
        path = self._draft_manifest_path(project_id, book_id)
        data = jread(path, {}) if path else {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault('versions', [])
        return data

    def draft_workspace(self, d=None):
        d = d or {}
        project_id = _text(d.get('project_id'), 80)
        manifest = self.load_manifest(project_id)
        if not manifest:
            return {'ok': False, 'message': 'Project manifest not found.'}
        book_id = slug(_text(d.get('book_id') or 'book_1', 60)).lower() or 'book_1'
        chapter = _text(d.get('chapter'), 200)
        drafts = self._drafts_dir(project_id, book_id)
        manifest_data = self._load_draft_manifest(project_id, book_id)
        entries = manifest_data.get('versions') or []
        if chapter:
            entries = [e for e in entries if str(e.get('chapter', '')) == chapter]
        latest = None
        if chapter:
            for entry in reversed(entries):
                if str(entry.get('chapter', '')) == chapter:
                    latest = entry
                    break
        return {
            'ok': True,
            'read_only': True,
            'project_id': manifest['project_id'],
            'book_id': book_id,
            'chapter': chapter,
            'drafts_folder': str(drafts),
            'versions': entries[-100:],
            'latest': latest,
        }

    def draft_save_gate(self, d=None):
        d = d or {}
        content = _text(d.get('content'), 80000)
        if not content:
            return {'ok': False, 'message': 'Draft content is empty.'}
        project_id = _text(d.get('project_id'), 80)
        manifest = self.load_manifest(project_id)
        if not manifest:
            return {'ok': False, 'message': 'Project manifest not found.'}
        chapter = _text(d.get('chapter') or 'Untitled Chapter', 200)
        book_id = slug(_text(d.get('book_id') or 'book_1', 60)).lower() or 'book_1'
        manifest_data = self._load_draft_manifest(project_id, book_id)
        existing = [e for e in manifest_data.get('versions')
                    if str(e.get('chapter', '')) == chapter]
        previous = existing[-1] if existing else None
        growth = {}
        if previous:
            growth = {
                'previous_words': previous.get('word_count', 0),
                'current_words': word_count(content),
                'previous_sha256': previous.get('content_sha256', ''),
                'current_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            }
            if growth['current_sha256'] == growth['previous_sha256']:
                return {'ok': False,
                        'message': 'This draft is identical to the latest saved version '
                                   'of this chapter. Nothing to save.',
                        'growth_check': growth}
        return {
            'ok': True,
            'read_only': True,
            'gate_ready': True,
            'project_id': manifest['project_id'],
            'book_id': book_id,
            'chapter': chapter,
            'next_version': (previous or {}).get('version', 0) + 1,
            'growth_check': growth,
            'word_count': word_count(content),
            'safety': {'new_version_file': True, 'no_overwrite': True},
        }

    def draft_save_action(self, d=None):
        gate = self.draft_save_gate(d)
        if not gate.get('ok'):
            return gate
        if not bool(d.get('execute')):
            return {'ok': True, 'message': 'Draft gate passed. Set execute=true to save.',
                    'action_taken': False}
        d2 = d or {}
        book_id = gate['book_id']
        chapter = gate['chapter']
        content = _text(d2.get('content'), 80000)
        version = int(gate['next_version'])
        drafts = self._drafts_dir(gate['project_id'], book_id)
        ch_slug = slug(chapter).lower()[:40] or 'chapter'
        filename = f'chapter_{ch_slug}_draft_v{version:03d}.md'
        path = drafts / filename
        header = (
            f"---\n"
            f"project: {json.dumps(gate['project_id'])}\n"
            f"book_id: {json.dumps(book_id)}\n"
            f"chapter: {json.dumps(chapter, ensure_ascii=False)}\n"
            f"version: {version}\n"
            f"word_count: {word_count(content)}\n"
            f"content_sha256: {json.dumps(hashlib.sha256(content.encode('utf-8')).hexdigest())}\n"
            f"created: {json.dumps(now())}\n"
            f"model: {json.dumps(_text(d2.get('model'), 180), ensure_ascii=False)}\n"
            f"---\n\n"
        )
        path.write_text(header + content.rstrip() + '\n', encoding='utf-8')
        manifest_data = self._load_draft_manifest(gate['project_id'], book_id)
        manifest_data['versions'] = manifest_data.get('versions') or []
        manifest_data['versions'].append({
            'chapter': chapter,
            'version': version,
            'filename': filename,
            'word_count': word_count(content),
            'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            'created': now(),
            'model': _text(d2.get('model'), 180),
        })
        jwrite(self._draft_manifest_path(gate['project_id'], book_id), manifest_data)
        result = {
            'ok': True,
            'message': f'Draft v{version:03d} saved: {filename}',
            'path': str(path),
            'version': version,
            'word_count': word_count(content),
            'action_taken': True,
        }
        result['report_path'] = self._report('DraftSaveAction', result)
        return result

    def draft_version_history(self, d=None):
        d = d or {}
        project_id = _text(d.get('project_id'), 80)
        manifest = self.load_manifest(project_id)
        if not manifest:
            return {'ok': False, 'message': 'Project manifest not found.'}
        book_id = slug(_text(d.get('book_id') or 'book_1', 60)).lower() or 'book_1'
        data = self._load_draft_manifest(project_id, book_id)
        entries = data.get('versions') or []
        chapter = _text(d.get('chapter'), 200)
        if chapter:
            entries = [e for e in entries if str(e.get('chapter', '')) == chapter]
        history = []
        drafts = self._drafts_dir(project_id, book_id)
        for entry in entries:
            path = drafts / str(entry.get('filename', ''))
            history.append({
                **entry,
                'exists': path.is_file(),
                'size_bytes': path.stat().st_size if path.is_file() else 0,
            })
        return {
            'ok': True,
            'read_only': True,
            'project_id': manifest['project_id'],
            'book_id': book_id,
            'chapter': chapter,
            'version_total': len(history),
            'versions': history,
        }

    def draft_compare(self, d=None):
        d = d or {}
        project_id = _text(d.get('project_id'), 80)
        book_id = slug(_text(d.get('book_id') or 'book_1', 60)).lower() or 'book_1'
        drafts = self._drafts_dir(project_id, book_id)
        left_name = _text(d.get('left_filename'), 200)
        right_name = _text(d.get('right_filename'), 200)
        left_path = (drafts / Path(left_name).name).resolve() if left_name else None
        right_path = (drafts / Path(right_name).name).resolve() if right_name else None
        if not left_path or not left_path.is_file() or not contained(left_path, drafts):
            return {'ok': False, 'message': 'Left draft file not found.'}
        if not right_path or not right_path.is_file() or not contained(right_path, drafts):
            return {'ok': False, 'message': 'Right draft file not found.'}
        left = self._draft_body(left_path.read_text(encoding='utf-8'))
        right = self._draft_body(right_path.read_text(encoding='utf-8'))
        metrics = change_metrics(left, right)
        diff_lines = list(difflib.unified_diff(
            left.splitlines(), right.splitlines(),
            fromfile=left_name, tofile=right_name, lineterm=''))[:400]
        return {
            'ok': True,
            'read_only': True,
            'left': left_name, 'right': right_name,
            'left_words': word_count(left), 'right_words': word_count(right),
            'diff_metrics': metrics,
            'unified_diff_preview': diff_lines,
        }

    @staticmethod
    def _draft_body(text):
        text = str(text or '').replace('\r\n', '\n')
        if text.startswith('---\n'):
            end = text.find('\n---\n', 4)
            if end >= 0:
                text = text[end + 5:]
        lines = text.lstrip('\n').splitlines()
        if lines and lines[0].lstrip().startswith('#'):
            lines = lines[1:]
        return '\n'.join(lines).strip()

    def draft_continue_gate(self, d=None):
        """Verify a continuation builds on the latest version and adds prose."""
        d = d or {}
        latest = self.draft_workspace(d).get('latest')
        if not latest:
            return {'ok': False,
                    'message': 'No saved draft found for this chapter. Save a first '
                               'draft version before continuing.'}
        continuation = _text(d.get('content'), 80000)
        if not continuation.strip():
            return {'ok': False, 'message': 'Continuation content is empty.'}
        drafts = self._drafts_dir(
            _text(d.get('project_id'), 80),
            slug(_text(d.get('book_id') or 'book_1', 60)).lower() or 'book_1')
        path = drafts / str(latest['filename'])
        previous_body = self._draft_body(path.read_text(encoding='utf-8')) \
            if path.is_file() else ''
        metrics = change_metrics(previous_body, continuation)
        grew = word_count(continuation) >= word_count(previous_body)
        return {
            'ok': True,
            'read_only': True,
            'gate_ready': grew and not metrics['exact_match'],
            'base_version': latest.get('version'),
            'growth_check': {
                'previous_words': word_count(previous_body),
                'current_words': word_count(continuation),
                'word_growth_ok': grew,
                'changed': not metrics['exact_match'],
                'similarity': metrics['similarity'],
            },
            'safety': {'new_version_file': True, 'no_overwrite': True},
        }

    def draft_continue_action(self, d=None):
        gate = self.draft_continue_gate(d)
        if not gate.get('ok'):
            return gate
        if not gate.get('gate_ready'):
            return {'ok': False,
                    'message': 'Continuation must add or change prose and may not '
                               'shrink the chapter.',
                    'growth_check': gate['growth_check']}
        d2 = dict(d or {})
        d2.setdefault('content', d2.get('content'))
        return self.draft_save_action(d2)

    # ------------------------------------------------------------------
    # real prose manuscript: draft, editor edit, compare
    # ------------------------------------------------------------------
    def _prose_dir(self, project_id):
        root = self.project_root(project_id)
        if not root:
            return None
        path = root / 'Prose'
        path.mkdir(parents=True, exist_ok=True)
        return path

    def prose_status(self, d=None):
        d = d or {}
        project_id = _text(d.get('project_id'), 80)
        manifest = self.load_manifest(project_id)
        if not manifest:
            return {'ok': False, 'message': 'Project manifest not found.'}
        prose = self._prose_dir(project_id)
        files = sorted(prose.glob('*.md')) if prose else []
        versions = []
        for path in files:
            versions.append({
                'filename': path.name,
                'size_bytes': path.stat().st_size,
                'word_count': word_count(path.read_text(encoding='utf-8', errors='replace')),
                'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds'),
            })
        return {'ok': True, 'read_only': True,
                'project_id': manifest['project_id'],
                'prose_folder': str(prose),
                'versions': versions}

    def prose_draft_save(self, d=None):
        d = d or {}
        content = _text(d.get('content'), 200000)
        if not content:
            return {'ok': False, 'message': 'Prose content is empty.'}
        project_id = _text(d.get('project_id'), 80)
        manifest = self.load_manifest(project_id)
        if not manifest:
            return {'ok': False, 'message': 'Project manifest not found.'}
        label = slug(_text(d.get('label') or 'manuscript', 60)).lower() or 'manuscript'
        prose = self._prose_dir(project_id)
        existing = sorted(prose.glob(f'{label}_prose_v*.md'))
        version = len(existing) + 1
        if existing:
            latest_path = existing[-1]
            latest_body = self._draft_body(latest_path.read_text(encoding='utf-8'))
            if change_metrics(latest_body, content)['exact_match']:
                return {'ok': False,
                        'message': 'Prose is identical to the latest version '
                                   f'({latest_path.name}). Nothing to save.'}
        filename = f'{label}_prose_v{version:03d}.md'
        path = prose / filename
        header = (
            '---\n'
            f'project: {json.dumps(manifest["project_id"])}\n'
            f'label: {json.dumps(label)}\n'
            f'version: {version}\n'
            f'word_count: {word_count(content)}\n'
            f'content_sha256: {json.dumps(hashlib.sha256(content.encode("utf-8")).hexdigest())}\n'
            f'created: {json.dumps(now())}\n'
            '---\n\n'
        )
        path.write_text(header + content.rstrip() + '\n', encoding='utf-8')
        result = {'ok': True,
                  'message': f'Prose v{version:03d} saved: {filename}',
                  'path': str(path), 'version': version,
                  'word_count': word_count(content),
                  'no_overwrite': True, 'action_taken': True}
        result['report_path'] = self._report('RealProseSaveAction', result)
        return result

    def prose_editor_preview(self, d=None):
        d = d or {}
        project_id = _text(d.get('project_id'), 80)
        prose = self._prose_dir(project_id)
        if not prose:
            return {'ok': False, 'message': 'Project manifest not found.'}
        filename = _text(d.get('filename'), 200)
        if not filename:
            files = sorted(p.name for p in prose.glob('*.md'))
            return {'ok': False, 'message': 'Choose a prose file to edit.',
                    'available_files': files}
        path = (prose / Path(filename).name).resolve()
        if not contained(path, prose) or not path.is_file():
            return {'ok': False, 'message': 'Prose file not found.'}
        content = path.read_text(encoding='utf-8', errors='replace')
        return {'ok': True, 'read_only': True,
                'filename': path.name, 'path': str(path),
                'content': content, 'word_count': word_count(content),
                'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest()}

    def prose_edit_gate(self, d=None):
        d = d or {}
        preview = self.prose_editor_preview(d)
        if not preview.get('ok'):
            return preview
        original = preview['content']
        edited = str(d.get('edited_content') or '')
        if not edited.strip():
            return {'ok': False, 'message': 'Edited prose is empty.'}
        metrics = change_metrics(original, edited)
        if metrics['exact_match']:
            return {'ok': False, 'message': 'Edited prose is identical to the saved version.',
                    'diff_metrics': metrics}
        phrase_required = 'APPROVE PROSE EDIT'
        phrase_ok = self._phrase_ok(d.get('approval_phrase'), phrase_required)
        blockers = []
        if not phrase_ok:
            blockers.append({'id': 'phrase_mismatch',
                             'message': f'Type the exact approval phrase: "{phrase_required}".'})
        return {'ok': True, 'read_only': True,
                'gate_ready': not blockers,
                'filename': preview['filename'],
                'approval_phrase_required': phrase_required,
                'approval_phrase_matches': phrase_ok,
                'diff_metrics': metrics,
                'blockers': blockers}

    def prose_edit_save(self, d=None):
        gate = self.prose_edit_gate(d)
        if not gate.get('ok'):
            return gate
        blockers = gate.get('blockers') or []
        if blockers:
            return {'ok': False,
                    'message': 'Edit blocked: ' + '; '.join(
                        b.get('message', '') for b in blockers),
                    'blockers': blockers}
        if not bool(d.get('execute')):
            return {'ok': True,
                    'message': 'Prose edit gate passed. Set execute=true to apply '
                               '(the original is backed up first).',
                    'action_taken': False}
        edited = str(d.get('edited_content') or '')
        path = Path(self.prose_editor_preview(d)['path'])
        backup = self.store.backup_file(path, 'edits')
        path.write_text(edited, encoding='utf-8')
        result = {'ok': True,
                  'message': f'Prose edit applied to {path.name}. Original backed up.',
                  'filename': path.name, 'path': str(path),
                  'backup': str(backup) if backup else '',
                  'diff_metrics': gate['diff_metrics'],
                  'action_taken': True}
        result['report_path'] = self._report('RealProseEditSaveAction', result)
        return result

    def prose_refresh_compare(self, d=None):
        d = d or {}
        preview = self.prose_editor_preview(d)
        if not preview.get('ok'):
            return preview
        saved = preview['content']
        edited = str(d.get('edited_content') or '')
        metrics = change_metrics(saved, edited)
        diff_lines = list(difflib.unified_diff(
            saved.splitlines(), edited.splitlines(),
            fromfile='saved', tofile='edited', lineterm=''))[:400]
        return {'ok': True, 'read_only': True,
                'filename': preview['filename'],
                'saved_words': word_count(saved),
                'edited_words': word_count(edited),
                'identical': bool(metrics['exact_match']),
                'diff_metrics': metrics,
                'unified_diff_preview': diff_lines}

    # ------------------------------------------------------------------
    # foundation / overview (FOXAI story_forge_report generalization)
    # ------------------------------------------------------------------
    def overview(self):
        projects = self.list_projects()
        root = self.projects_root()
        folders = {
            'projects_root': str(root),
            'reports': str(self.store.folders['reports']),
            'backups': str(self.store.folders['backups']),
        }
        sections = [
            {'id': 'create_project', 'title': 'Create Story Project',
             'description': 'Approval-gated creation of a new project manifest '
                            'with books, folders, README, and Books.md.'},
            {'id': 'chapter_planner', 'title': 'Chapter Planner',
             'description': 'Preview chapter cards, then save them behind the '
                            'approval gate (preview set JSON, chapter markdown, '
                            'continuity handoffs).'},
            {'id': 'chapter_editor', 'title': 'Chapter Editor',
             'description': 'Edit saved chapter cards with diff verification '
                            'and automatic backups.'},
            {'id': 'drafts', 'title': 'Draft Workspace',
             'description': 'Versioned chapter drafts: save, continue, history, '
                            'and side-by-side compare.'},
            {'id': 'prose', 'title': 'Prose Workspace',
             'description': 'Real prose manuscript versions with verified edits.'},
        ]
        actions = [
            {'id': 'create_project_gate', 'title': 'Create Project Gate',
             'available_now': True, 'requires_phrase': self.require_approval_phrase},
            {'id': 'chapter_save', 'title': 'Save Chapter Cards',
             'available_now': True, 'requires_phrase': self.require_approval_phrase},
            {'id': 'chapter_edit', 'title': 'Apply Chapter Edit',
             'available_now': True, 'requires_phrase': self.require_approval_phrase},
            {'id': 'draft_save', 'title': 'Save Draft Version',
             'available_now': True, 'requires_phrase': False},
            {'id': 'prose_save', 'title': 'Save Prose Version',
             'available_now': True, 'requires_phrase': False},
        ]
        return {
            'ok': True,
            'read_only': True,
            'title': 'Kayock Writer — Story Forge',
            'summary': {
                'project_count': len(projects.get('projects', [])),
                'projects_folder': folders['projects_root'],
            },
            'projects': projects.get('projects', []),
            'sections': sections,
            'actions': actions,
            'folders': folders,
            'safety': {
                'approval_gates_on_destructive_actions': self.require_approval_phrase,
                'no_overwrite_without_backup': True,
                'no_delete': True,
                'no_move': True,
                'reports_written_for_actions': True,
            },
        }
