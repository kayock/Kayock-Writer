#!/usr/bin/env python3
"""Kayock Writer test suite (stdlib unittest, no third-party dependencies).

Covers: voice profiles & prompt builders, private pack import, Poetry Forge
creator/polisher/selection/save/archive/legacy, Weaver, Novel Forge CRUD and
story-bible export, Story Forge gates/actions/drafts/prose, and the HTTP
server (route smoke tests, LAN binding, model endpoint configuration,
path-traversal guards).

Run:  python tests/run_tests.py            (uses a temp data dir)
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tests.mock_provider import start_mock_server  # noqa: E402

from app import voices  # noqa: E402
from app.config import DEFAULT_CONFIG, Config, load_config, save_config  # noqa: E402
from app.novelforge import NovelForge  # noqa: E402
from app.poetry import PoetryForge  # noqa: E402
from app.provider import Provider  # noqa: E402
from app.server import serve  # noqa: E402
from app.storage import Store  # noqa: E402
from app.storyforge import StoryForge  # noqa: E402
from app.weaver import Weaver  # noqa: E402


def make_cfg(data_dir: Path, base_url: str) -> Config:
    cfg = Config(json.loads(json.dumps(DEFAULT_CONFIG)))
    cfg.set('model.base_url', base_url)
    cfg.set('model.health_kind', 'openai_models')
    cfg.set('paths.data_dir', str(data_dir))
    cfg.set('server.allow_folder_open', False)
    cfg.path = Path(data_dir) / 'config.json'  # keep save_config writes local
    return cfg


class MockEndpoint:
    """Shared mock model server for the whole run."""

    server = None
    base_url = ''

    @classmethod
    def start(cls):
        cls.server = start_mock_server('127.0.0.1', 0)
        port = cls.server.server_address[1]
        cls.base_url = f'http://127.0.0.1:{port}'

    @classmethod
    def stop(cls):
        if cls.server:
            cls.server.shutdown()


def setUpModule():
    MockEndpoint.start()


def tearDownModule():
    MockEndpoint.stop()


class TempStore:
    def __enter__(self):
        self.dir = Path(tempfile.mkdtemp(prefix='kayock_test_'))
        return Store(self.dir)

    def __exit__(self, *exc):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


# ==========================================================================
# voices
# ==========================================================================
class VoiceProfileTests(unittest.TestCase):
    def setUp(self):
        # The bundled add-on pack may have been auto-loaded by App-based tests
        # running earlier in the suite; each test here starts pack-free.
        voices.ERIC_POET_NARRATOR_PROFILE['sources'] = []

    def tearDown(self):
        voices.ERIC_POET_NARRATOR_PROFILE['sources'] = []

    def test_all_profiles_present(self):
        expected = {
            'eric_poet_narrator', 'eric_short_fiction',
            'edgar_allan_poe_gothic_lyric', 'beneath_the_beats_west_coast_voice',
            'dust_and_duty_last_gunslinger', 'the_forsaken_flame_exiles_voice',
            'robin_hood_merry_outlaw', 'zorro_masked_fox',
            'dracula_ancient_count', 'sherlock_holmes_consulting_mind',
        }
        self.assertEqual(set(voices.POETRY_VOICE_PROFILES), expected)

    def test_names_map_to_ids(self):
        for profile_id, profile in voices.POETRY_VOICE_PROFILES.items():
            resolved = voices._writer_voice_profile_id(profile['name'])
            self.assertEqual(resolved, profile_id, profile['name'])

    def test_eric_poet_prompt_without_private_pack(self):
        prompt = voices.build_writer_voice_prompt('eric_poet_narrator',
                                                  'Strong Eric voice', 'poem')
        self.assertIn('ERIC — POET/NARRATOR VOICE PROFILE', prompt)
        self.assertIn('Strong Eric voice', prompt)
        self.assertNotIn('Protected read-only source poems', prompt)  # poem text excluded
        self.assertNotIn('Protected read-only source poems', prompt)
        self.assertIn('Non-copying rules', prompt)

    def test_eric_poet_prompt_story_mode(self):
        prompt = voices.build_writer_voice_prompt('eric_poet_narrator',
                                                  'Recognizably Eric', 'short_story')
        self.assertIn('short fiction prose', prompt)
        self.assertIn('Do not force rhyme', prompt)

    def test_eric_short_fiction_prompt(self):
        prompt = voices.build_writer_voice_prompt('eric_short_fiction',
                                                  'Full Eric story voice', 'short_story')
        self.assertIn('ERIC — SHORT FICTION VOICE PROFILE', prompt)
        self.assertIn('memorable final', prompt.lower())

    def test_archetype_prompt_strength_rules(self):
        prompt = voices.build_writer_voice_prompt('robin_hood_merry_outlaw',
                                                  'Merry Outlaw Full Force', 'poem')
        self.assertIn('ROBIN HOOD — THE MERRY OUTLAW', prompt)
        self.assertIn('full outlaw energy', prompt.lower())

    def test_poe_prompt_story_format_override(self):
        prompt = voices.build_writer_voice_prompt('edgar_allan_poe_gothic_lyric',
                                                  'Gothic Lyric', 'short_story')
        self.assertIn('Do not introduce verse', prompt)

    def test_compact_voice_prompt(self):
        guide = voices.poetry_compact_voice_prompt('eric_poet_narrator',
                                                   'Strong Eric voice')
        self.assertIn('COMPACT VOICE GUIDE', guide)
        guide2 = voices.poetry_compact_voice_prompt('dracula_ancient_count', '')
        self.assertIn('Dracula', guide2)

    def test_private_pack_import_and_cleanup(self):
        pack = {
            'id': 'eric_poet_narrator', 'private': True,
            'sources': [{'title': 'Test Source Poem', 'author': 'Test Author',
                         'text': 'Line one of a test source.\nLine two follows here.'}],
        }
        with TempStore() as store:
            pack_dir = store.root / 'voice_packs'
            pack_dir.mkdir(parents=True)
            (pack_dir / 'eric_poet_narrator_private.json').write_text(
                json.dumps(pack), encoding='utf-8')
            status = voices.apply_private_voice_pack(store.root)
            self.assertTrue(status['loaded'])
            self.assertEqual(status['sources'], 1)
            prompt = voices.build_writer_voice_prompt('eric_poet_narrator',
                                                      'Recognizably Eric', 'poem')
            self.assertIn('Protected read-only source poems', prompt)
            self.assertIn('Test Source Poem', prompt)
            self.assertIn('Line one of a test source.', prompt)
        # restore module state for other tests
        voices.ERIC_POET_NARRATOR_PROFILE['sources'] = []

    def test_private_pack_rejects_bad_profile_id(self):
        with TempStore() as store:
            pack_dir = store.root / 'voice_packs'
            pack_dir.mkdir(parents=True)
            (pack_dir / 'eric_poet_narrator_private.json').write_text(
                json.dumps({'id': 'someone_else', 'sources': []}), encoding='utf-8')
            status = voices.apply_private_voice_pack(store.root)
            self.assertFalse(status['loaded'])
        voices.ERIC_POET_NARRATOR_PROFILE['sources'] = []


# ==========================================================================
# poetry / short story forge
# ==========================================================================
class PoetryForgeTests(unittest.TestCase):
    def _forge(self):
        cfg = make_cfg(Path(tempfile.mkdtemp(prefix='kayock_pf_')), MockEndpoint.base_url)
        store = Store(cfg.data_dir())
        return PoetryForge(store, Provider(cfg)), cfg, store

    def test_create_requires_seed(self):
        forge, cfg, store = self._forge()
        d = forge.create({'theme': '', 'emotion': ''})
        self.assertFalse(d['ok'])
        self.assertIn('Add at least a theme', d['message'])

    def test_create_poem_with_voice(self):
        forge, cfg, store = self._forge()
        d = forge.create({
            'writing_type': 'poem', 'theme': 'home and memory',
            'emotion': 'haunted', 'imagery': 'a porch light in snow',
            'voice': 'Eric — Poet/Narrator', 'voice_strength': 'Strong Eric voice',
            'length': 'short', 'opening_line': 'The porch light held its breath.',
        })
        self.assertTrue(d['ok'], d.get('message'))
        self.assertEqual(d['writing_type'], 'poem')
        self.assertEqual(d['voice_profile'], 'Eric — Poet/Narrator')
        self.assertTrue(d['settings']['opening_line'])
        self.assertIn('porch', d['poem'])
        self.assertTrue(d['suggested_title'])

    def test_create_short_story_with_short_fiction_voice(self):
        forge, cfg, store = self._forge()
        d = forge.create({
            'writing_type': 'short_story', 'theme': 'a debt paid after midnight',
            'voice': 'Eric — Short Fiction',
            'voice_strength': 'Full Eric story voice', 'length': 'short',
        })
        self.assertTrue(d['ok'], d.get('message'))
        self.assertEqual(d['voice_profile'], 'Eric — Short Fiction')
        self.assertNotIn('\n\nPOETRY', d.get('poem', '').upper())

    def test_short_fiction_voice_rejected_for_poems(self):
        forge, cfg, store = self._forge()
        d = forge.create({'theme': 'x', 'voice': 'Eric — Short Fiction',
                          'writing_type': 'poem'})
        self.assertTrue(d['ok'])
        self.assertEqual(d['voice_profile'], '')  # profile dropped for poem mode

    def test_polish_poem(self):
        forge, cfg, store = self._forge()
        d = forge.polish({'poem': 'The first line stands.\nThe second one waits.',
                          'focus': 'Light touch', 'voice': 'My natural voice'})
        self.assertTrue(d['ok'], d.get('message'))
        self.assertEqual(d['focus'], 'Light touch')

    def test_polish_story_substantive_change(self):
        forge, cfg, store = self._forge()
        body = ('Marcus counted the streetlights twice and waited. The stranger '
                'arrived with the lantern and paid the debt. The porch went dark '
                'before dawn. He kept the lantern anyway. Nobody asked about the man. '
                'The town slept through all of it. Morning came the same as always.')
        d = forge.polish({'writing_type': 'short_story', 'poem': body,
                          'focus': 'Balanced story polish'})
        self.assertTrue(d['ok'], d.get('message'))
        self.assertTrue(d['substantive_change'])
        self.assertIn('change_metrics', d)

    def test_polish_story_rejects_unchanged(self):
        # The mock returns unchanged text on the first attempt and appends a
        # revised sentence on retry; simulate a model that never changes by
        # monkey-patching the chat method.
        forge, cfg, store = self._forge()
        original_chat = forge.chat

        def echo_only(messages, max_tokens=900, temperature=0.82):
            user = next(m['content'] for m in messages if m['role'] == 'user')
            body = user.split('PRIMARY AUTHORITY:\n', 1)[-1]
            body = body.split('\n\nRETRY REQUIREMENT', 1)[0]  # ignore retry suffix
            return {'ok': True, 'poem': body.strip(), 'model_name': 'mock'}

        forge.chat = echo_only
        body = 'Same words over and over. ' * 30
        d = forge.polish({'writing_type': 'short_story', 'poem': body,
                          'focus': 'Balanced story polish'})
        self.assertFalse(d['ok'])
        self.assertTrue(d['unchanged_output'])
        self.assertEqual(d['polish_attempts'], 2)
        forge.chat = original_chat

    def test_revise_selection_positions(self):
        forge, cfg, store = self._forge()
        poem = 'first line here\nsecond line there\nthird line waits\nfourth line ends'
        d = forge.revise_selection({
            'poem': poem, 'selection': 'second line there',
            'selection_start': poem.index('second line there'),
            'selection_end': poem.index('second line there') + len('second line there'),
            'focus': 'stronger imagery', 'voice': 'Eric — Poet/Narrator',
        })
        self.assertTrue(d['ok'], d.get('message'))
        self.assertEqual(len(d['alternatives']), 3)
        self.assertTrue(d['whole_poem_unchanged'])
        normalized = lambda s: ' '.join(s.split()).casefold()
        for alt in d['alternatives']:
            self.assertNotEqual(normalized(alt), normalized('second line there'),
                                'unchanged selection returned as an option')
            self.assertNotIn('first line here', alt)   # context lines not repeated
            self.assertNotIn('fourth line ends', alt)

    def test_revise_selection_mismatch_rejected(self):
        forge, cfg, store = self._forge()
        d = forge.revise_selection({'poem': 'abcdef', 'selection': 'zzz',
                                    'selection_start': 0, 'selection_end': 3})
        self.assertFalse(d['ok'])
        self.assertIn('changed after the passage was captured', d['message'])

    def test_save_and_archive_roundtrip(self):
        forge, cfg, store = self._forge()
        r = forge.save({
            'poem': 'Saved poem body.', 'title': 'Archive Roundtrip',
            'writing_type': 'poem', 'version_kind': 'original',
            'settings': {'theme': 'testing', 'voice': 'Eric — Poet/Narrator'},
        })
        self.assertTrue(r['ok'], r.get('message'))
        path = Path(r['path'])
        self.assertTrue(path.exists())
        text = path.read_text(encoding='utf-8')
        self.assertTrue(text.startswith('---\n'))
        self.assertIn('content_type: "poem"', text)
        self.assertIn('voice_profile_sources_read_only: true', text)

        archive = forge.archive()
        self.assertTrue(archive['ok'])
        group = next(g for g in archive['groups']
                     if g['title'] == 'Archive Roundtrip')
        self.assertEqual(group['version_counts']['original'], 1)
        self.assertTrue(group['is_eric_voice'])

        read = forge.archive_read(group['latest_any'])
        self.assertTrue(read['ok'])
        self.assertEqual(read['poem'], 'Saved poem body.')
        self.assertEqual(read['theme'], 'testing')

    def test_short_story_save_and_merged_archive(self):
        forge, cfg, store = self._forge()
        r = forge.save({'poem': 'Story body.', 'title': 'Merged Story',
                        'writing_type': 'short_story', 'version_kind': 'draft'})
        self.assertTrue(r['ok'])
        self.assertIn('ShortStories', r['path'])
        archive = forge.archive()
        group = next(g for g in archive['groups'] if g['title'] == 'Merged Story')
        self.assertEqual(group['content_type'], 'short_story')

    def test_story_polisher_dedup(self):
        forge, cfg, store = self._forge()
        base = {'writing_type': 'short_story', 'source_mode': 'polisher',
                'title': 'Dedup Story'}
        r1 = forge.save({**base, 'poem': 'Identical body.', 'version_kind': 'polished'})
        r2 = forge.save({**base, 'poem': 'Identical body. ', 'version_kind': 'polished'})
        self.assertTrue(r1['ok'] and r2['ok'])
        self.assertFalse(r1['deduplicated'])
        self.assertTrue(r2['deduplicated'])
        self.assertEqual(r2['path'], r1['path'])

    def test_legacy_flags(self):
        forge, cfg, store = self._forge()
        forge.save({'poem': 'x', 'title': 'Flag Poem'})
        d = forge.legacy_update({'title': 'Flag Poem', 'field': 'for_akaysha',
                                 'value': True})
        self.assertTrue(d['ok'])
        archive = forge.archive()
        group = next(g for g in archive['groups'] if g['title'] == 'Flag Poem')
        self.assertTrue(group['for_akaysha'])
        bad = forge.legacy_update({'title': 'Flag Poem', 'field': 'nope',
                                   'value': True})
        self.assertFalse(bad['ok'])

    def test_recordings_prepare(self):
        forge, cfg, store = self._forge()
        d = forge.recordings_prepare({'title': 'Recording Poem'})
        self.assertTrue(d['ok'])
        self.assertTrue((Path(d['folder']) / 'README_RECORDINGS.txt').exists())
        snapshot = forge._recording_snapshot('Recording Poem')
        self.assertIn('master_policy', snapshot)


# ==========================================================================
# weaver
# ==========================================================================
class WeaverTests(unittest.TestCase):
    def _weaver(self):
        cfg = make_cfg(Path(tempfile.mkdtemp(prefix='kayock_wv_')), MockEndpoint.base_url)
        store = Store(cfg.data_dir())
        return Weaver(store, Provider(cfg)), store

    def test_needs_two_sources(self):
        weaver, store = self._weaver()
        d = weaver.generate({'sources': [{'title': 'A', 'content': 'only one'}]})
        self.assertFalse(d['ok'])
        self.assertIn('at least two', d['message'])

    def test_generate_and_save_clean_prose(self):
        weaver, store = self._weaver()
        d = weaver.generate({
            'sources': [{'title': 'First Poem', 'content': 'memory of the porch light'},
                        {'title': 'Second Story', 'content': 'the debt paid at midnight'}],
            'mode': 'shared_soul', 'output_type': 'clean_prose',
            'voice': 'Eric — Poet/Narrator', 'length': 'short',
        })
        self.assertTrue(d['ok'], d.get('message'))
        self.assertEqual(d['output_type'], 'clean_prose')
        self.assertTrue(d['source_map'].get('shared_threads'))
        self.assertEqual(len(d['provenance']['sources']), 2)
        r = weaver.save({'output': d['output'], 'output_type': 'clean_prose',
                         'title': d['title'], 'provenance': d['provenance'],
                         'mode': d['mode'], 'voice': d['voice'],
                         'length': d['length'], 'direction': ''})
        self.assertTrue(r['ok'])
        path = Path(r['created_files'][0])
        self.assertTrue(path.exists())
        self.assertIn('Woven prose begins here', path.read_text(encoding='utf-8'))

    def test_generate_twine(self):
        weaver, store = self._weaver()
        d = weaver.generate({
            'sources': [{'title': 'A', 'content': 'x' * 40}, {'title': 'B', 'content': 'y' * 40}],
            'output_type': 'twine',
        })
        self.assertTrue(d['ok'], d.get('message'))
        self.assertIn(':: Start', d['output'])

    def test_annotation_contamination_retry(self):
        weaver, store = self._weaver()
        original_chat = weaver.chat
        calls = {'n': 0}

        def contaminated_chat(messages, max_tokens=900, temperature=0.82):
            system = next((m['content'] for m in messages if m['role'] == 'system'), '')
            if 'a creative synthesis tool' in system:  # generation stage only
                calls['n'] += 1
                if calls['n'] == 1:
                    return {'ok': True, 'poem': 'Source 1: this is labeled contamination'}
                return {'ok': True, 'poem': 'Clean final output at last.'}
            return {'ok': True, 'poem': json.dumps({'suggested_title': 'T'})}  # planner

        weaver.chat = contaminated_chat
        d = weaver.generate({'sources': [{'title': 'A', 'content': 'x' * 40},
                                         {'title': 'B', 'content': 'y' * 40}]})
        self.assertTrue(d['ok'])
        self.assertEqual(d['attempts'], 2)
        weaver.chat = original_chat


# ==========================================================================
# novel forge
# ==========================================================================
class NovelForgeTests(unittest.TestCase):
    def _forge(self):
        with TempStore() as store:
            yield NovelForge(store), store

    def run(self, result=None):
        gen = self._forge()
        self.forge, self.store = next(gen)
        try:
            super().run(result)
        finally:
            gen.close()

    def test_crud_roundtrip(self):
        f = self.forge
        r = f.save_universe({'universe': 'Test Universe',
                             'premise': 'A city that forgot its god.',
                             'characters': 'Anthony — protagonist\nKayock — ancient protector',
                             'locations': 'Pueblo tunnels', 'artifacts': 'Crystal skulls',
                             'timeline': 'Book 1: Anthony learns the prophecy',
                             'mysteries': 'What did the ex become?', 'scenes': 'Opening',
                             'notes': 'N/A'})
        self.assertTrue(r['ok'], r.get('message'))
        data = json.loads(Path(r['path']).read_text(encoding='utf-8'))
        self.assertEqual(data['version'], '0.1')
        self.assertEqual(len(data['characters']), 2)
        self.assertTrue(Path(r['markdown']).exists())

        listing = f.list_universes()
        self.assertEqual(listing['universes'][0]['universe'], 'Test Universe')

        read = f.read_universe(r['name'])
        self.assertEqual(read['premise'], 'A city that forgot its god.')

        dup = f.duplicate_universe({'name': r['name']})
        self.assertTrue(dup['ok'])
        self.assertIn('Copy', dup['universe']['universe'])

        ren = f.rename_universe({'name': r['name'], 'new_title': 'Renamed Universe'})
        self.assertTrue(ren['ok'])
        self.assertFalse(Path(r['path']).exists())  # old file gone

        deleted = f.delete_universe(ren['name'])
        self.assertTrue(deleted['ok'])

    def test_extra_keys_survive_save(self):
        f = self.forge
        r = f.save_universe({'universe': 'Extras', 'premise': 'x'})
        path = Path(r['path'])
        data = json.loads(path.read_text(encoding='utf-8'))
        data['character_cards'] = [{'name': 'Anthony', 'role': 'protagonist'}]
        path.write_text(json.dumps(data), encoding='utf-8')
        r2 = f.save_universe({'universe': 'Extras', 'premise': 'y',
                              'characters': 'Anthony'})
        data2 = json.loads(path.read_text(encoding='utf-8'))
        self.assertIn('character_cards', data2)  # additive round-trip
        self.assertEqual(data2['premise'], 'y')

    def test_traversal_rejected(self):
        f = self.forge
        # slug() strips slashes, so traversal input cannot escape the vault:
        # the resolved path must remain inside the NovelForge folder.
        for bad in ('../../etc/passwd', '..\\..\\windows\\system32', '/etc/passwd'):
            p = f.novel_path(bad)
            if p is not None:
                self.assertTrue(
                    str(p).startswith(str(f.novel_root())),
                    f'{bad} escaped the vault: {p}')
                rel_parts = p.relative_to(f.novel_root()).parts
                self.assertNotIn('..', rel_parts,
                                 f'{bad} produced a traversal component: {rel_parts}')

    def test_export_story_bible(self):
        f = self.forge
        r = f.export_story_bible({
            'universe': 'Test Universe',
            'summary': {'characters': 2, 'locations': 1, 'artifacts': 1,
                        'timeline': 1, 'mysteries': 1, 'readiness': 'draft'},
            'codex': {'characters': ['Anthony']},
            'story_bible': '# Bible body',
        })
        self.assertTrue(r['ok'])
        for key in ('json', 'markdown', 'text'):
            self.assertTrue(Path(r[key]).exists(), key)


# ==========================================================================
# story forge
# ==========================================================================
class StoryForgeTests(unittest.TestCase):
    def _forge(self, data_dir=None):
        store = Store(data_dir or Path(tempfile.mkdtemp(prefix='kayock_sf_')))
        return StoryForge(store, require_approval_phrase=True), store

    def _create_project(self, forge):
        base = {
            'title': 'Test Saga',
            'books': [{'id': 'book_1', 'title': 'Book 1', 'summary': 'A beginning.'},
                      {'id': 'book_2', 'title': 'Book 2', 'summary': 'A middle.'}],
        }
        gate = forge.create_project_gate({**base, 'approval_phrase': 'CREATE STORY PROJECT'})
        self.assertTrue(gate['gate_ready'], gate.get('blockers'))
        action = forge.create_project_action({**base, 'execute': True,
                                              'approval_phrase': 'CREATE STORY PROJECT'})
        self.assertTrue(action['ok'], action.get('message'))
        return action

    def test_create_gate_blocks_wrong_phrase(self):
        forge, store = self._forge()
        gate = forge.create_project_gate({'title': 'Saga X',
                                          'approval_phrase': 'wrong phrase'})
        self.assertFalse(gate['gate_ready'])
        self.assertFalse(gate['approval_phrase_matches'])
        action = forge.create_project_action({'title': 'Saga X', 'execute': True,
                                              'approval_phrase': 'wrong phrase'})
        self.assertFalse(action['ok'])

    def test_create_gate_blocks_existing_project(self):
        forge, store = self._forge()
        self._create_project(forge)
        gate = forge.create_project_gate({'title': 'Test Saga',
                                          'approval_phrase': 'CREATE STORY PROJECT'})
        self.assertFalse(gate['gate_ready'])
        self.assertTrue(any(b['id'] == 'project_exists' for b in gate['blockers']))

    def test_create_action_writes_manifest(self):
        forge, store = self._forge()
        action = self._create_project(forge)
        manifest_path = Path(action['written_files'][0])
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(manifest['api_version'], 'kayock.writer.project.v1')
        self.assertEqual(manifest['status'], 'active_project')
        self.assertEqual(len(manifest['books']), 2)
        self.assertIn('safety_contract', manifest)
        listing = forge.list_projects()
        self.assertEqual(len(listing['projects']), 1)

    def test_chapter_save_flow(self):
        forge, store = self._forge()
        self._create_project(forge)
        cards = [
            {'chapter_number': 1, 'title': 'The Prophecy', 'pov': 'Anthony',
             'location': 'Pueblo', 'goal': 'Learn the truth',
             'conflict': 'Nobody believes him', 'reveal': 'The skull hums',
             'hook': 'The ex is not dead', 'continuity_notes': ['Skull found in ch 1'],
             'handoff_tags': {'prophecy': 'book_1'}},
            {'chapter_number': 2, 'title': 'The Debt', 'pov': 'Kayock',
             'location': 'The lair', 'goal': 'Protect the boy', 'conflict': 'The council',
             'reveal': 'He knew all along', 'hook': 'Blood in the vats',
             'continuity_notes': [], 'handoff_tags': {}},
        ]
        payload = {'project_id': 'Test_Saga', 'book_id': 'book_1',
                   'chapter_cards': cards}
        preview = forge.chapter_planner_preview(payload)
        self.assertTrue(preview['ok'])
        self.assertEqual(preview['summary']['chapter_cards'], 2)
        self.assertTrue(all(not p['exists'] for p in preview['preflight']))

        gate = forge.chapter_save_gate({**payload, 'approval_phrase': 'SAVE CHAPTER CARDS'})
        self.assertTrue(gate['gate_ready'], gate['blockers'])

        action = forge.chapter_save_action({**payload,
                                            'approval_phrase': 'SAVE CHAPTER CARDS',
                                            'execute': True})
        self.assertTrue(action['ok'], action.get('message'))
        self.assertEqual(len(action['written_files']), 4)  # set json + 2 cards + handoff

        dashboard = forge.saved_chapter_dashboard(payload)
        self.assertTrue(dashboard['dashboard_ready'], dashboard['checks'])

        # Re-save backs up instead of failing.
        action2 = forge.chapter_save_action({**payload,
                                             'approval_phrase': 'SAVE CHAPTER CARDS',
                                             'execute': True})
        self.assertTrue(action2['ok'])
        self.assertTrue(action2['backups'])

    def test_chapter_edit_flow(self):
        forge, store = self._forge()
        self._create_project(forge)
        payload = {'project_id': 'Test_Saga', 'book_id': 'book_1',
                   'chapter_cards': [{'chapter_number': 1, 'title': 'The Prophecy',
                                      'goal': 'Learn', 'conflict': 'Doubt',
                                      'reveal': 'Humming skull', 'hook': 'The ex'}]}
        forge.chapter_save_action({**payload, 'approval_phrase': 'SAVE CHAPTER CARDS',
                                   'execute': True})
        listing = forge.chapter_editor_preview({'project_id': 'Test_Saga'})
        self.assertFalse(listing['ok'])  # no filename given: lists files instead
        files = listing.get('available_files') or []
        self.assertTrue(files, 'no chapter files listed')
        filename = files[0]
        preview = forge.chapter_editor_preview({'project_id': 'Test_Saga',
                                                'filename': filename})
        self.assertTrue(preview['ok'], preview.get('message'))
        original = preview['content']
        edited = original.replace('## Goal', '## Goal (revised)')

        gate = forge.chapter_edit_gate({'project_id': 'Test_Saga',
                                        'filename': filename,
                                        'edited_content': original})
        self.assertFalse(gate['ok'])  # identical edit rejected

        gate = forge.chapter_edit_gate({'project_id': 'Test_Saga',
                                        'filename': filename,
                                        'edited_content': edited,
                                        'approval_phrase': 'APPROVE CHAPTER EDIT'})
        self.assertTrue(gate['gate_ready'], gate['blockers'])
        self.assertGreater(gate['diff_metrics']['changed_words'], 0)

        wrong = forge.chapter_edit_action({'project_id': 'Test_Saga',
                                           'filename': filename,
                                           'edited_content': edited,
                                           'approval_phrase': 'nope', 'execute': True})
        self.assertFalse(wrong['ok'])

        action = forge.chapter_edit_action({'project_id': 'Test_Saga',
                                            'filename': filename,
                                            'edited_content': edited,
                                            'approval_phrase': 'APPROVE CHAPTER EDIT',
                                            'execute': True})
        self.assertTrue(action['ok'], action.get('message'))
        self.assertTrue(action['backup'])
        self.assertIn('(revised)', Path(action['path']).read_text(encoding='utf-8'))

    def test_draft_version_flow(self):
        forge, store = self._forge()
        self._create_project(forge)
        base = {'project_id': 'Test_Saga', 'book_id': 'book_1',
                'chapter': 'Chapter 01 — The Prophecy'}
        v1 = forge.draft_save_action({**base, 'content': 'First draft text here. ' * 20,
                                      'execute': True})
        self.assertTrue(v1['ok'], v1.get('message'))
        self.assertEqual(v1['version'], 1)

        # identical draft rejected
        dup_gate = forge.draft_save_gate({**base, 'content': 'First draft text here. ' * 20})
        self.assertFalse(dup_gate['ok'])

        v2 = forge.draft_save_action({**base,
                                      'content': 'First draft text here. ' * 20 +
                                                 'The scene grew longer tonight.',
                                      'execute': True})
        self.assertTrue(v2['ok'])
        self.assertEqual(v2['version'], 2)

        history = forge.draft_version_history(base)
        self.assertEqual(history['version_total'], 2)
        self.assertTrue(all(v['exists'] for v in history['versions']))

        compare = forge.draft_compare({**base,
                                       'left_filename': history['versions'][0]['filename'],
                                       'right_filename': history['versions'][1]['filename']})
        self.assertTrue(compare['ok'])
        self.assertEqual(compare['diff_metrics']['changed_words'], 5)

    def test_draft_continue_flow(self):
        forge, store = self._forge()
        self._create_project(forge)
        base = {'project_id': 'Test_Saga', 'book_id': 'book_1', 'chapter': 'Ch A'}
        forge.draft_save_action({**base, 'content': 'Beginning of the chapter. ' * 10,
                                 'execute': True})
        gate = forge.draft_continue_gate({**base, 'content': 'Beginning of the chapter. ' * 10})
        self.assertTrue(gate['ok'])
        self.assertFalse(gate['gate_ready'])  # no growth

        grown = forge.draft_continue_action(
            {**base, 'content': 'Beginning of the chapter. ' * 10 + ' Then the turn came.',
             'execute': True})
        self.assertTrue(grown['ok'], grown.get('message'))

        shrunk = forge.draft_continue_gate({**base, 'content': 'Short.'})
        self.assertFalse(shrunk['gate_ready'])

    def test_prose_flow(self):
        forge, store = self._forge()
        self._create_project(forge)
        r1 = forge.prose_draft_save({'project_id': 'Test_Saga',
                                     'label': 'manuscript',
                                     'content': 'Prose opening. ' * 15})
        self.assertTrue(r1['ok'])
        dup = forge.prose_draft_save({'project_id': 'Test_Saga', 'label': 'manuscript',
                                      'content': 'Prose opening. ' * 15})
        self.assertFalse(dup['ok'])  # identical prose rejected
        r2 = forge.prose_draft_save({'project_id': 'Test_Saga', 'label': 'manuscript',
                                     'content': 'Prose opening. ' * 15 + ' More prose followed.'})
        self.assertTrue(r2['ok'])
        self.assertEqual(r2['version'], 2)

        edited = 'Prose opening, lightly polished. ' + 'Prose opening. ' * 14
        gate = forge.prose_edit_gate({'project_id': 'Test_Saga',
                                      'filename': r1['path'].split('/')[-1]
                                      if isinstance(r1['path'], str) else 'manuscript_prose_v001.md',
                                      'edited_content': edited,
                                      'approval_phrase': 'APPROVE PROSE EDIT'})
        self.assertTrue(gate['gate_ready'], gate.get('blockers'))
        action = forge.prose_edit_save({'project_id': 'Test_Saga',
                                        'filename': 'manuscript_prose_v001.md',
                                        'edited_content': edited,
                                        'approval_phrase': 'APPROVE PROSE EDIT',
                                        'execute': True})
        self.assertTrue(action['ok'], action.get('message'))
        self.assertTrue(action['backup'])
        compare = forge.prose_refresh_compare({'project_id': 'Test_Saga',
                                               'filename': 'manuscript_prose_v001.md',
                                               'edited_content': edited})
        self.assertTrue(compare['ok'])
        self.assertTrue(compare['identical'])

    def test_overview_and_dashboard(self):
        forge, store = self._forge()
        self._create_project(forge)
        overview = forge.overview()
        self.assertEqual(overview['summary']['project_count'], 1)
        self.assertEqual(len(overview['sections']), 5)
        dash = forge.project_dashboard({'project_id': 'Test_Saga'})
        self.assertTrue(dash['healthy'])
        self.assertEqual(len(dash['books']), 2)
        health = forge.project_health_card({'project_id': 'Test_Saga'})
        self.assertEqual(health['checks_total'], 4)


# ==========================================================================
# config / provider
# ==========================================================================
class ConfigProviderTests(unittest.TestCase):
    def test_config_precedence_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps({'model': {'base_url': 'http://file:1',
                                                  'model': 'file-model'}}))
            cfg = load_config(path)
            self.assertEqual(cfg.get('model.base_url'), 'http://file:1')
            self.assertEqual(cfg.get('server.port'), 8765)  # default kept
            cfg.set('server.port', 9999)
            save_config(cfg)
            cfg2 = load_config(path)
            self.assertEqual(cfg2.get('server.port'), 9999)
            self.assertEqual(cfg2.get('model.base_url'), 'http://file:1')

    def test_provider_health_and_chat(self):
        cfg = make_cfg(Path(tempfile.mkdtemp()), MockEndpoint.base_url)
        p = Provider(cfg)
        health = p.health(timeout=3)
        self.assertTrue(health['online'])
        result = p.chat([{'role': 'user', 'content': 'hello'}], max_tokens=32)
        self.assertTrue(result['ok'])
        self.assertTrue(result['text'])

    def test_provider_offline(self):
        cfg = make_cfg(Path(tempfile.mkdtemp()), 'http://127.0.0.1:59999')
        p = Provider(cfg)
        health = p.health(timeout=2)
        self.assertFalse(health['online'])
        chat = p.chat([{'role': 'user', 'content': 'x'}], max_tokens=8)
        self.assertFalse(chat['ok'])
        self.assertIn('could not reach', chat['message'])


# ==========================================================================
# HTTP server
# ==========================================================================
class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='kayock_srv_'))
        cfg = make_cfg(cls.tmp, MockEndpoint.base_url)
        cfg.set('server.host', '127.0.0.1')
        cfg.set('server.port', 0)
        cls.server = serve(cfg)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return json.loads(r.read().decode('utf-8'))

    def post(self, path, payload):
        req = urllib.request.Request(self.base + path,
                                     data=json.dumps(payload).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))

    def test_ui_served(self):
        with urllib.request.urlopen(self.base + '/', timeout=10) as r:
            html = r.read().decode('utf-8')
        self.assertIn('Kayock Writer', html)
        self.assertIn('Novel Forge', html)
        self.assertIn('Poetry Forge', html)
        self.assertIn('Short Story Forge', html)
        self.assertIn('<meta name="viewport"', html)

    def test_status_and_voices(self):
        status = self.get('/api/status')
        self.assertTrue(status['ok'])
        self.assertTrue(status['model']['online'])
        voices_list = self.get('/api/voices')
        self.assertEqual(len(voices_list['voices']), 10)

    def test_poetry_create_via_http(self):
        d = self.post('/api/writer/poetry/create',
                      {'writing_type': 'poem', 'theme': 'lan test',
                       'voice': 'Eric — Poet/Narrator'})
        self.assertTrue(d['ok'])
        archive = self.get('/api/writer/poetry/archive')
        self.assertTrue(archive['ok'])

    def test_novelforge_via_http(self):
        r = self.post('/api/novelforge/save',
                      {'universe': 'HTTP Universe', 'premise': 'p',
                       'characters': 'A — lead'})
        self.assertTrue(r['ok'])
        listing = self.get('/api/novelforge/list')
        self.assertTrue(any(u['name'] == 'HTTP_Universe'
                            for u in listing['universes']))

    def test_story_overview_via_http(self):
        d = self.get('/api/writer/story/overview')
        self.assertTrue(d['ok'])
        self.assertIn('sections', d)

    def test_unknown_route_404(self):
        import urllib.error
        try:
            with urllib.request.urlopen(self.base + '/api/nope', timeout=10) as r:
                d = json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            d = json.loads(exc.read().decode('utf-8'))
        self.assertFalse(d['ok'])
        self.assertIn('Unknown route', d['message'])

    def test_invalid_json_400(self):
        req = urllib.request.Request(self.base + '/api/writer/poetry/save',
                                     data=b'not json{',
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read().decode('utf-8'))
            self.assertFalse(d['ok'])
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)

    def test_model_endpoint_reconfiguration(self):
        r = self.post('/api/config/model', {'base_url': MockEndpoint.base_url,
                                            'model': 'renamed-model'})
        self.assertTrue(r['ok'])
        status = self.get('/api/status')
        self.assertEqual(status['model']['model'], 'renamed-model')
        self.post('/api/config/model', {'model': 'local-model'})


class LANBindingTests(unittest.TestCase):
    def test_binds_lan_address(self):
        tmp = Path(tempfile.mkdtemp(prefix='kayock_lan_'))
        cfg = make_cfg(tmp, MockEndpoint.base_url)
        cfg.set('server.host', '0.0.0.0')
        cfg.set('server.port', 0)
        server = serve(cfg)
        host, port = server.server_address[:2]
        self.assertEqual(host, '0.0.0.0')
        self.assertGreater(port, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # Connect via loopback while bound to 0.0.0.0 (LAN-reachable proof).
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/status',
                                        timeout=10) as r:
                d = json.loads(r.read().decode('utf-8'))
            self.assertTrue(d['ok'])
        finally:
            server.shutdown()
            server.server_close()
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
