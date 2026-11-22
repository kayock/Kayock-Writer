"""Isolated, deterministic Writer browser-test server.

Used ONLY by GitHub Actions browser checks. All files are seeded in a new
TemporaryDirectory; inference is stubbed in memory. Never binds to the LAN,
reads a production config, loads private writing or talks to online models.
"""
from __future__ import annotations

import json
import signal
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.config import Config, DEFAULT_CONFIG
from app.server import serve
from app.storage import Store, jwrite
from app.storyforge import StoryForge

CHAPTER_A = "The lantern glowed above the quiet shore.\n\nA bell rang at dusk."
CHAPTER_B = "Beyond the harbor, the sea went still.\n\nNight arrived."


def seed(temp: Path):
    store=Store(temp / "writer")
    root=store.folder("projects") / "ReleaseFixture"
    root.mkdir(parents=True, exist_ok=True)
    jwrite(root / "project.kayock-writer.json", {
        "project_id":"ReleaseFixture", "title":"Fixture Book Project",
        "books":[{"id":"book_1","title":"Fixture Manuscript"}]
    })
    forge=StoryForge(store)
    for chapter, text in [("Chapter One",CHAPTER_A),("Chapter Two",CHAPTER_B)]:
        saved=forge.draft_save_action({
            "project_id":"ReleaseFixture","book_id":"book_1",
            "chapter":chapter,"content":text,"execute":True
        })
        if not saved.get("ok"):
            raise RuntimeError("Unable to create fixture chapter: "+repr(saved))
    return store


def main():
    with tempfile.TemporaryDirectory(prefix="kayock-release-browser-") as temp:
        folder=Path(temp)
        store=seed(folder)
        cfg=Config(json.loads(json.dumps(DEFAULT_CONFIG)),
                   path=folder / "browser-config.json")
        cfg.set("paths.data_dir",str(store.root))
        cfg.set("server.host","127.0.0.1")
        cfg.set("server.port",0)
        cfg.set("model.base_url","http://127.0.0.1:1")
        cfg.set("model.model","fixture-reviewer")
        cfg.set("model.api_key","")
        cfg.set("writing.default_author","Browser Fixture Author")
        server=serve(cfg)
        app=server.RequestHandlerClass.app
        app.provider.health=lambda timeout=3.0: {"online":True,"via":"isolated fixture"}
        def fixture_stream(messages, *, max_tokens, temperature, cancellation):
            # This is deterministic mock text, not real inference.
            if cancellation.cancelled():
                yield {"type":"cancelled"}
                return
            system=messages[0]["content"]
            if "editorial coordinator" in system.lower():
                response=("CONSENSUS (WITH EVIDENCE)\nKeep the lantern image.\n"
                          "DISAGREEMENTS\nNo canonical change is proposed.\n"
                          "HIGH-IMPACT OPTIONS FOR THE AUTHOR\nUse a careful edit.")
            elif "Story Architect" in system:
                response=("OBSERVATIONS WITH SHORT EVIDENCE\nThe bell marks dusk.\n"
                          "PRIORITIZED SUGGESTIONS\nPreserve the lantern image.\n"
                          "QUESTIONS FOR THE AUTHOR\nWhat happens next?")
            else:
                response=("OBSERVATIONS WITH SHORT EVIDENCE\nThe opening has a distinct rhythm.\n"
                          "PRIORITIZED SUGGESTIONS\nKeep the author's short sentences.\n"
                          "QUESTIONS FOR THE AUTHOR\nIs the pause intentional?")
            yield {"type":"token","text":response}
            yield {"type":"done"}
        app.provider.stream_chat=fixture_stream
        def fixture_chat(messages, *, max_tokens, temperature):
            return {"ok":True,"text":"FIXTURE ONLY: optional editorial comments."}
        app.provider.chat=fixture_chat
        endpoint="http://127.0.0.1:"+str(server.server_address[1])
        print("READY "+endpoint,flush=True)
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
            server.server_close()


if __name__=="__main__":
    main()
