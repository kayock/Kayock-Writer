#!/usr/bin/env python3
"""Focused v1.1.0 tests; no live writer or Craft Suite services required."""
from __future__ import annotations
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.config import Config, DEFAULT_CONFIG
from app.server import App
from app.editorial import editorial_review
from app.ui import render_page
from tests.mock_provider import start_mock_server

class UpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock = start_mock_server('127.0.0.1',0)
        cls.base_url=f'http://127.0.0.1:{cls.mock.server_address[1]}'
    @classmethod
    def tearDownClass(cls):
        cls.mock.shutdown();cls.mock.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),path=Path(self.tmp.name)/'config.json')
        cfg.set('paths.data_dir',str(Path(self.tmp.name)/'data'))
        cfg.set('model.base_url',self.base_url)
        cfg.set('server.allow_folder_open',False)
        self.app=App(cfg)
    def tearDown(self):self.tmp.cleanup()

    def test_editorial_review_never_writes(self):
        original='A moonlight garden grows quietly.\n\nThe shadows answer.'
        res=self.app.editorial({'text':original,'mode':'review','writing_type':'poem'})
        self.assertTrue(res['ok'],res)
        self.assertEqual(res['saved'],False)
        self.assertTrue(res['source_unchanged'])
        self.assertEqual(list(Path(self.tmp.name).glob('data/**/Drafts/*.md')),[])
    def test_editorial_suggestion_is_separate(self):
        res=self.app.editorial({'text':'A forgotten road.','mode':'suggestion','writing_type':'prose'})
        self.assertTrue(res['ok'],res)
        self.assertFalse(res['saved'])
        self.assertIn('text',res)
    def test_editorial_validation_and_no_truncation(self):
        for payload in ({'text':''},{'text':'x' * 80001},{'text':'hello','mode':'invalid'},{'text':'ok','writing_type':'invalid'}):
            self.assertFalse(self.app.editorial(payload)['ok'])
    def test_craft_link_is_optional_and_validated(self):
        self.assertFalse(self.app.save_craft_settings({'craft_suite_url':'file:///etc/passwd'})['ok'])
        self.assertFalse(self.app.save_craft_settings({'craft_suite_url':'https://user:pass@localhost:9000'})['ok'])
        self.assertTrue(self.app.save_craft_settings({'craft_suite_url':'https://127.0.0.1:8743'})['ok'])
        cfg=json.loads((Path(self.tmp.name)/'config.json').read_text('utf8'))
        self.assertEqual(cfg['integrations']['craft_suite_url'],'https://127.0.0.1:8743')
        self.assertTrue(self.app.save_craft_settings({'craft_suite_url':''})['ok'])
    def test_ui_has_handoff(self):
        html=render_page()
        for expected in ('pg-finishing','finishText','cfgCraftUrl','finishingReview()', 'finishingOpenCraft()', 'finishingExport('):
            self.assertIn(expected,html)

@unittest.skipUnless(sys.platform.startswith("linux"), "Linux-only installer test")
class InstallerTests(unittest.TestCase):
    def test_linux_install_is_preserving_and_repeatable(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'installed'
            env={**os.environ,'KAYOCK_WRITER_INSTALL_DIR':str(dest)}
            script=str(ROOT/'deploy'/'install-linux.sh')
            for i in range(2):
                if i:
                    (dest/'config.json').write_text('{"private":"keep"}',encoding='utf8')
                    (dest/'KayockWriterData').mkdir(exist_ok=True)
                    (dest/'KayockWriterData'/'my_poem.md').write_text('Never overwrite',encoding='utf8')
                done=subprocess.run(['bash',script],env=env,text=True,capture_output=True,timeout=10)
                self.assertEqual(done.returncode,0,done.stderr)
            self.assertEqual((dest/'config.json').read_text('utf8'),'{"private":"keep"}')
            self.assertEqual((dest/'KayockWriterData'/'my_poem.md').read_text('utf8'),'Never overwrite')
            self.assertTrue((dest/'app'/'editorial.py').is_file())
            self.assertFalse((dest/'addons'/'private_eric_poet_narrator').exists())

if __name__=='__main__':unittest.main(verbosity=2)
