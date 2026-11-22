"""Kayock Writer LAN server — stdlib ThreadingHTTPServer.

Route table mirrors FOXAI's Kayock Writer surface (Handler.do_GET / do_POST)
with the FOXAI-specific subsystems removed and the model endpoint made
configurable. JSON API, single-page UI at `/`, health at `/api/status`.
"""
from __future__ import annotations

import json
import threading
import uuid
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import __version__, APP_NAME, voices
from .config import Config, save_config
from .canon import CanonStore
from .context import preview as preview_canon
from .continuity import check as check_continuity
from .editorial import editorial_review, prepare_editorial
from urllib.parse import urlsplit
from .novelforge import NovelForge
from .recovery import UniverseRecovery
from .model_profiles import ModelProfiles
from .timeline import chronology, character_knowledge
from .poetry import PoetryForge
from .provider import Cancellation, Provider
from .storage import Store
from .storyforge import StoryForge
from .weaver import Weaver

MAX_BODY_BYTES = 9 * 1024 * 1024  # matches FOXAI mission JSON limit


class App:
    """Wires config → storage → provider → forge modules."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.store = Store(cfg.data_dir())
        self.provider = Provider(cfg)
        self._generation_lock = threading.Lock()
        self._active_generations = {}

        voices.apply_private_voice_pack(cfg.data_dir())
        self.poetry = PoetryForge(
            self.store, self.provider,
            default_author=cfg.default_author,
            archive_limit=cfg.archive_limit,
            allow_folder_open=cfg.allow_folder_open,
        )
        self.weaver = Weaver(self.store, self.provider, default_author=cfg.default_author)
        self.novelforge = NovelForge(self.store)
        self.recovery = UniverseRecovery(self.store, self.novelforge)
        self.model_profiles = ModelProfiles(self.store)
        self.canon = CanonStore(self.store)
        self.storyforge = StoryForge(
            self.store,
            require_approval_phrase=cfg.require_approval_phrase,
            default_author=cfg.default_author,
        )

    def status(self) -> Dict[str, Any]:
        health = self.provider.health(timeout=3.0)
        return {
            'ok': True,
            'app': APP_NAME,
            'version': __version__,
            'model': {
                'base_url': self.provider.base_url(),
                'model': self.provider.display_model(),
                'online': bool(health.get('online')),
                'health_via': health.get('via', ''),
            },
            'data_dir': str(self.store.root),
            'voice_pack': voices.private_pack_status(),
        }

    def save_model_settings(self, d: Dict[str, Any]) -> Dict[str, Any]:
        model = self.cfg.data.setdefault('model', {})
        for key in ('base_url', 'chat_path', 'health_path', 'health_kind', 'model',
                    'api_key', 'timeout_seconds'):
            if key in d and d[key] is not None:
                value = str(d[key]) if key != 'timeout_seconds' else d[key]
                if key == 'api_key' and str(value) == '':
                    continue  # empty means "leave unchanged"
                if key == 'api_key':
                    model[key] = str(value)
                else:
                    model[key] = value
        try:
            save_config(self.cfg)
        except Exception as exc:
            return {'ok': False, 'message': f'Could not persist config: {exc}'}
        return {
            'ok': True,
            'message': 'Model endpoint settings saved.',
            'base_url': self.provider.base_url(),
            'model': self.provider.display_model(),
            'api_key_set': bool(self.cfg.api_key()),
        }

    def save_craft_settings(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Save an optional browser link. Does not call Craft Suite or alter it."""
        url = str(d.get('craft_suite_url') or '').strip()
        parts = urlsplit(url) if url else None
        if url and (parts.scheme not in ('http', 'https') or not parts.netloc
                    or parts.username or parts.password):
            return {'ok': False, 'message': 'Enter a full http(s) Craft Suite URL without credentials.'}
        self.cfg.set('integrations.craft_suite_url', url)
        try:
            save_config(self.cfg)
        except Exception as exc:
            return {'ok': False, 'message': f'Could not save Craft Suite link: {exc}'}
        return {'ok': True, 'message': 'Optional Craft Suite link saved. No connection was made.',
                'craft_suite_url': url}

    def editorial_canon_context(self, d: Dict[str, Any]) -> str:
        """Only an explicit opt-in adds approved story facts to model prompts."""
        if d.get('use_canon') is not True:
            return ''
        universe = self._existing_universe(d.get('universe', ''))
        limit = d.get('canon_limit', 12)
        if isinstance(limit, bool):
            raise ValueError('Canon limit must be a whole number.')
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ValueError('Canon limit must be a whole number.')
        return preview_canon(
            self.canon.approved_context(universe),
            str(d.get('text') or ''), limit
        )['context_text']

    def editorial(self, d: Dict[str, Any]) -> Dict[str, Any]:
        return editorial_review(
            self.provider, d,
            max_tokens=self.cfg.get('writing.editorial_max_tokens', 4000),
            canon_context=self.editorial_canon_context(d),
        )

    def canon_context_preview(self, d: Dict[str, Any]) -> Dict[str, Any]:
        universe = self._existing_universe(d.get('universe', ''))
        limit = d.get('limit', 12)
        if isinstance(limit, bool):
            raise ValueError('Fact limit must be a whole number.')
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise ValueError('Fact limit must be a whole number.')
        result = preview_canon(
            self.canon.approved_context(universe), str(d.get('query') or ''), limit
        )
        result['universe'] = universe
        result['read_only'] = True
        return result

    def canon_continuity_check(self, d: Dict[str, Any]) -> Dict[str, Any]:
        universe = self._existing_universe(d.get('universe', ''))
        result = check_continuity(
            d.get('text'), self.canon.approved_context(universe),
            world_time=d.get('world_time', ''),
        )
        result['universe'] = universe
        return result

    def canon_chronology(self, d: Dict[str, Any]) -> Dict[str, Any]:
        universe = self._existing_universe(d.get('universe', ''))
        result = chronology(self.canon.approved_context(universe))
        result['universe'] = universe
        return result

    def canon_knowledge(self, d: Dict[str, Any]) -> Dict[str, Any]:
        universe = self._existing_universe(d.get('universe', ''))
        result = character_knowledge(
            self.canon.approved_context(universe),
            d.get('character'), d.get('at_world_time', ''),
        )
        result['universe'] = universe
        return result

    def _existing_universe(self, name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Choose a saved universe first.')
        p = self.novelforge.novel_path(name)
        if p is None or not p.is_file():
            raise ValueError('Save or load the universe before editing canon.')
        return p.stem

    def universe_write(self, function, *args):
        """Serialize app HTTP mutations with restore previews and replacement."""
        with self.recovery._lock:
            return function(*args)

    def recovery_backups(self, name: str) -> Dict[str, Any]:
        return self.recovery.list_backups(name)

    def recovery_preview(self, d: Dict[str, Any]) -> Dict[str, Any]:
        return self.recovery.preview(d.get('universe', ''), d.get('backup_id', ''))

    def recovery_restore(self, d: Dict[str, Any]) -> Dict[str, Any]:
        return self.recovery.restore(d.get('universe', ''),
                                     d.get('backup_id', ''),
                                     d.get('confirmation_token', ''))

    def canon_list(self, name: str) -> Dict[str, Any]:
        return self.canon.list_facts(self._existing_universe(name))

    def canon_propose(self, d: Dict[str, Any]) -> Dict[str, Any]:
        name = self._existing_universe(d.get('universe', ''))
        return self.canon.propose(
            name, str(d.get('kind') or ''), str(d.get('subject') or ''),
            str(d.get('claim') or ''),
            [{'source': str(d.get('source') or ''), 'quote': str(d.get('quote') or '')}],
            chapter=str(d.get('chapter') or ''),
            world_time=str(d.get('world_time') or ''),
            narrative_order=str(d.get('narrative_order') or ''),
            known_by=d.get('known_by', []),
            learned_time=str(d.get('learned_time') or ''),
        )

    def rename_universe_with_canon(self, d: Dict[str, Any]) -> Dict[str, Any]:
        old_name = self._existing_universe(d.get('name', ''))
        new_title = str(d.get('new_title') or '').strip()
        if not new_title:
            raise ValueError('New universe title required.')
        target = self.novelforge.novel_path(new_title)
        if target is None:
            raise ValueError('Invalid universe title.')
        if target.stem != old_name and target.exists():
            raise ValueError('A universe with that title already exists.')
        self.canon.prepare_relocation(old_name, target.stem)
        result = self.novelforge.rename_universe(d)
        if result.get('ok'):
            self.canon.relocate(old_name, target.stem)
        return result

    def delete_universe_preserving_canon(self, name: str) -> Dict[str, Any]:
        key = self._existing_universe(name)
        result = self.novelforge.delete_universe(name)
        if result.get('ok') and self.canon._root(key).exists():
            result['canon_retained'] = True
            result['message'] += ' Separate canon review records were retained for recovery.'
        return result

    def canon_review(self, d: Dict[str, Any]) -> Dict[str, Any]:
        name = self._existing_universe(d.get('universe', ''))
        fact_id = str(d.get('fact_id') or '')
        return self.canon.review(name, fact_id, str(d.get('decision') or ''))

    def register_generation(self, generation_id: str, token: Cancellation) -> None:
        with self._generation_lock:
            self._active_generations[generation_id] = token

    def forget_generation(self, generation_id: str) -> None:
        with self._generation_lock:
            self._active_generations.pop(generation_id, None)

    def cancel_generation(self, generation_id: str) -> Dict[str, Any]:
        with self._generation_lock:
            token = self._active_generations.get(generation_id)
        if token is None:
            return {'ok': False, 'message': 'Generation not found or already finished.'}
        token.cancel()
        return {'ok': True, 'cancelled': True, 'generation_id': generation_id}

    def test_model_settings(self) -> Dict[str, Any]:
        health = self.provider.health(timeout=5.0)
        if health.get('ok'):
            probe = self.provider.chat(
                [{'role': 'user', 'content': 'Reply with the single word: ready.'}],
                max_tokens=8, temperature=0.0)
            health['chat_probe'] = {'ok': bool(probe.get('ok')),
                                    'reply': probe.get('text', '')[:80] if probe.get('ok') else '',
                                    'message': '' if probe.get('ok') else probe.get('message', '')}
        return health


class Handler(BaseHTTPRequestHandler):
    server_version = f"KayockWriter/{__version__}"
    app: App = None  # injected by serve()

    # -- plumbing ----------------------------------------------------------
    def log_message(self, fmt, *args):  # quiet, brief
        pass

    def _send(self, body: bytes, content_type: str, code: int = 200,
              cache: str = 'no-store'):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json_response(self, payload: Any, code: int = 200):
        body = json.dumps(payload, indent=2, ensure_ascii=False).encode('utf-8')
        self._send(body, 'application/json; charset=utf-8', code)

    def body(self) -> Dict[str, Any]:
        try:
            n = int(self.headers.get('Content-Length', '0') or 0)
        except Exception:
            n = 0
        if n < 0 or n > MAX_BODY_BYTES:
            raise ValueError('JSON request exceeds the 9 MB limit.')
        if not n:
            return {}
        raw = self.rfile.read(n).decode('utf-8', errors='strict')
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f'Invalid JSON request: {exc}')
        return data if isinstance(data, dict) else {}

    def _guard(self, fn, *args):
        """Run an endpoint; convert exceptions into JSON errors."""
        try:
            self.json_response(fn(*args))
        except ValueError as exc:
            self.json_response({'ok': False, 'message': str(exc)}, code=400)
        except Exception as exc:
            self.json_response({
                'ok': False,
                'message': f'Server error: {type(exc).__name__}: {exc}',
            }, code=500)

    def _stream_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Write and flush a single SSE event; caller handles disconnected clients."""
        frame = (f"event: {event_type}\n"
                 f"data: {json.dumps(payload, ensure_ascii=False)}\n\n")
        self.wfile.write(frame.encode("utf-8"))
        self.wfile.flush()

    def _editorial_stream(self, payload: Dict[str, Any]) -> None:
        """On-demand, read-only editorial streaming; never saves a manuscript."""
        try:
            canon_context = self.app.editorial_canon_context(payload)
            prepared = prepare_editorial(
                payload, max_tokens=self.app.cfg.get('writing.editorial_max_tokens', 4000),
                canon_context=canon_context)
        except ValueError as exc:
            self.json_response({'ok': False, 'message': str(exc)}, code=400)
            return
        if not prepared['ok']:
            self.json_response(prepared, code=400)
            return
        token = Cancellation()
        generation_id = uuid.uuid4().hex
        self.app.register_generation(generation_id, token)
        self.close_connection = True
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-transform')
            self.send_header('Connection', 'close')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self._stream_event('start', {'generation_id': generation_id, 'ok': True})
            received = []
            for event in self.app.provider.stream_chat(
                    prepared['messages'], max_tokens=prepared['max_tokens'],
                    temperature=prepared['temperature'], cancellation=token):
                kind = event.get('type')
                if kind == 'token':
                    received.append(event['text'])
                    self._stream_event('token', {'text': event['text']})
                elif kind == 'done':
                    text = ''.join(received)
                    if not text.strip():
                        self._stream_event('error', {'message': 'Model returned an empty response.'})
                    elif prepared['mode'] == 'suggestion' and text.strip() == prepared['draft'].strip():
                        self._stream_event('error', {'message': 'No changes suggested; original is unchanged.'})
                    else:
                        self._stream_event('done', {
                            'ok': True, 'saved': False, 'source_unchanged': True,
                            'message': 'Review complete. Original writing unchanged.'
                        })
                elif kind == 'cancelled':
                    self._stream_event('cancelled', {
                        'ok': True, 'saved': False, 'message': 'Generation stopped; partial suggestion not saved.'
                    })
                elif kind == 'error':
                    self._stream_event('error', {'ok': False,
                                                 'message': event.get('message', 'Streaming failed.')})
        except (BrokenPipeError, ConnectionResetError, OSError):
            token.cancel()
        finally:
            self.app.forget_generation(generation_id)
            token.cancel()

    # -- routes ---------------------------------------------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        q1 = lambda key: (qs.get(key, [''])[0])

        app = self.app
        if path == '/' or path == '/index.html':
            from .ui import render_page
            self._send(render_page().encode('utf-8'), 'text/html; charset=utf-8')
            return
        if path == '/api/status':
            self._guard(app.status)
            return
        if path == '/api/voices':
            self.json_response({'ok': True, 'voices': voices.voice_catalog()})
            return
        if path == '/api/voice/pack/status':
            self.json_response(voices.private_pack_status())
            return
        if path == '/api/config':
            self.json_response({'ok': True, 'config': app.cfg.public_view()})
            return
        if path == '/api/model/health':
            self._guard(lambda: app.provider.health(timeout=5.0))
            return
        if path == '/api/model/capabilities':
            self._guard(app.provider.advertised_capabilities)
            return
        if path == '/api/model/profiles':
            self._guard(app.model_profiles.list)
            return
        # Poetry Forge / archive
        if path == '/api/writer/poetry/archive':
            self._guard(app.poetry.archive)
            return
        if path == '/api/writer/poetry/archive/read':
            self._guard(app.poetry.archive_read, q1('name'))
            return
        if path == '/api/writer/poetry/recordings/open':
            self._guard(app.poetry.recordings_open, q1('title'))
            return
        # Novel Forge
        if path == '/api/novelforge/list':
            self._guard(app.novelforge.list_universes)
            return
        if path == '/api/novelforge/read':
            self._guard(app.novelforge.read_universe, q1('name'))
            return
        if path == '/api/novelforge/backups':
            self._guard(app.recovery_backups, q1('name'))
            return
        if path == '/api/novelforge/canon':
            self._guard(app.canon_list, q1('name'))
            return
        # Story Forge reads
        if path == '/api/writer/story/overview':
            self._guard(app.storyforge.overview)
            return
        if path == '/api/writer/story/projects':
            self._guard(app.storyforge.list_projects)
            return
        if path == '/api/writer/story/dashboard':
            self._guard(app.storyforge.project_dashboard, {'project_id': q1('project_id')})
            return
        if path == '/api/writer/story/health_card':
            self._guard(app.storyforge.project_health_card, {'project_id': q1('project_id')})
            return
        if path == '/api/writer/story/saved_chapter_dashboard':
            self._guard(app.storyforge.saved_chapter_dashboard,
                        {'project_id': q1('project_id'), 'book_id': q1('book_id')})
            return
        if path == '/api/writer/story/chapter_editor_preview':
            self._guard(app.storyforge.chapter_editor_preview,
                        {'project_id': q1('project_id'), 'filename': q1('filename')})
            return
        if path == '/api/writer/story/draft_workspace':
            self._guard(app.storyforge.draft_workspace,
                        {'project_id': q1('project_id'), 'book_id': q1('book_id'),
                         'chapter': q1('chapter')})
            return
        if path == '/api/writer/story/draft_version_history':
            self._guard(app.storyforge.draft_version_history,
                        {'project_id': q1('project_id'), 'book_id': q1('book_id'),
                         'chapter': q1('chapter')})
            return
        if path == '/api/writer/story/prose_status':
            self._guard(app.storyforge.prose_status, {'project_id': q1('project_id')})
            return
        self.json_response({'ok': False, 'message': f'Unknown route: {path}'}, code=404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            d = self.body()
        except ValueError as exc:
            self.json_response({'ok': False, 'message': str(exc)}, code=400)
            return
        app = self.app

        if path == '/api/writer/editorial/stream':
            self._editorial_stream(d)
            return
        if path.startswith('/api/generation/') and path.endswith('/cancel'):
            generation_id = path[len('/api/generation/'):-len('/cancel')].strip('/')
            if not generation_id or '/' in generation_id:
                self.json_response({'ok': False, 'message': 'Invalid generation ID'}, code=400)
            else:
                self._guard(app.cancel_generation, generation_id)
            return
        # Poetry Forge / Short Story Forge
        if path == '/api/writer/poetry/create':
            self._guard(app.poetry.create, d)
            return
        if path == '/api/writer/poetry/polish':
            self._guard(app.poetry.polish, d)
            return
        if path == '/api/writer/poetry/revise-selection':
            self._guard(app.poetry.revise_selection, d)
            return
        if path == '/api/writer/poetry/save':
            self._guard(app.poetry.save, d)
            return
        if path == '/api/writer/poetry/recordings/prepare':
            self._guard(app.poetry.recordings_prepare, d)
            return
        if path == '/api/writer/poetry/legacy':
            self._guard(app.poetry.legacy_update, d)
            return
        # Weaver
        if path == '/api/writer/weaver/generate':
            self._guard(app.weaver.generate, d)
            return
        if path == '/api/writer/weaver/save':
            self._guard(app.weaver.save, d)
            return
        # Novel Forge
        if path == '/api/novelforge/save':
            self._guard(app.universe_write, app.novelforge.save_universe, d)
            return
        if path == '/api/novelforge/duplicate':
            self._guard(app.universe_write, app.novelforge.duplicate_universe, d)
            return
        if path == '/api/novelforge/rename':
            self._guard(app.universe_write, app.rename_universe_with_canon, d)
            return
        if path == '/api/novelforge/delete':
            self._guard(app.universe_write, app.delete_universe_preserving_canon, d.get('name', ''))
            return
        if path == '/api/novelforge/export':
            self._guard(app.novelforge.export_story_bible, d)
            return
        if path == '/api/novelforge/backups/preview':
            self._guard(app.recovery_preview, d)
            return
        if path == '/api/novelforge/backups/restore':
            self._guard(app.recovery_restore, d)
            return
        if path == '/api/novelforge/canon/propose':
            self._guard(app.canon_propose, d)
            return
        if path == '/api/novelforge/canon/review':
            self._guard(app.canon_review, d)
            return
        if path == '/api/novelforge/canon/context':
            self._guard(app.canon_context_preview, d)
            return
        if path == '/api/novelforge/canon/continuity':
            self._guard(app.canon_continuity_check, d)
            return
        if path == '/api/novelforge/canon/chronology':
            self._guard(app.canon_chronology, d)
            return
        if path == '/api/novelforge/canon/knowledge':
            self._guard(app.canon_knowledge, d)
            return
        # Story Forge actions
        story_routes = {
            '/api/writer/story/create_project_gate': app.storyforge.create_project_gate,
            '/api/writer/story/create_project_action': app.storyforge.create_project_action,
            '/api/writer/story/chapter_planner_preview': app.storyforge.chapter_planner_preview,
            '/api/writer/story/chapter_save_gate': app.storyforge.chapter_save_gate,
            '/api/writer/story/chapter_save_action': app.storyforge.chapter_save_action,
            '/api/writer/story/chapter_edit_gate': app.storyforge.chapter_edit_gate,
            '/api/writer/story/chapter_edit_action': app.storyforge.chapter_edit_action,
            '/api/writer/story/draft_save_gate': app.storyforge.draft_save_gate,
            '/api/writer/story/draft_save_action': app.storyforge.draft_save_action,
            '/api/writer/story/draft_continue_gate': app.storyforge.draft_continue_gate,
            '/api/writer/story/draft_continue_action': app.storyforge.draft_continue_action,
            '/api/writer/story/draft_compare': app.storyforge.draft_compare,
            '/api/writer/story/prose_draft_save': app.storyforge.prose_draft_save,
            '/api/writer/story/prose_editor_preview': app.storyforge.prose_editor_preview,
            '/api/writer/story/prose_edit_gate': app.storyforge.prose_edit_gate,
            '/api/writer/story/prose_edit_save': app.storyforge.prose_edit_save,
            '/api/writer/story/prose_refresh_compare': app.storyforge.prose_refresh_compare,
        }
        if path in story_routes:
            self._guard(story_routes[path], d)
            return
        # Settings
        if path == '/api/writer/editorial/review':
            self._guard(app.editorial, d)
            return
        if path == '/api/config/craft_suite':
            self._guard(app.save_craft_settings, d)
            return
        if path == '/api/config/model':
            self._guard(app.save_model_settings, d)
            return
        if path == '/api/config/model/test':
            self._guard(app.test_model_settings)
            return
        if path == '/api/model/profiles/save':
            self._guard(app.model_profiles.save, d.get('name'), d.get('settings'))
            return
        if path == '/api/model/profiles/delete':
            self._guard(app.model_profiles.delete, d.get('profile_id'))
            return
        self.json_response({'ok': False, 'message': f'Unknown route: {path}'}, code=404)


def serve(cfg: Config) -> ThreadingHTTPServer:
    app = App(cfg)
    handler = type('BoundHandler', (Handler,), {'app': app})
    server = ThreadingHTTPServer((cfg.host, cfg.port), handler)
    server.daemon_threads = True
    return server
