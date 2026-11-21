# Kayock Writer v1.1.0

A standalone, browser-based creative writing suite for the LAN — extracted and
upgraded from [FOXAI](https://github.com/kayock/FOXAI_) (commit `b510e5c38c0a1fa41f61b6c65e74ce1812f1ecdb`).

One app, one dashboard, one left-hand navigation tree:

| Forge | What it does |
|---|---|
| **Poetry Forge** | Poem creator, poem polisher, Selected Lines & Stanza Workshop (three verified replacement passages), poem archive with version groups, voice-recording folders, legacy/dedication flags |
| **Short Story Forge** | Short-story creator and polisher (story-specific focus presets, substantive-change verification), story drafts merged into the same archive |
| **Novel Forge** | Universes: premise, characters, locations, artifacts, timeline, mysteries, scenes, notes — with structured card builders, JSON + Markdown persistence, Story Bible export (JSON/MD/TXT) |
| **Story Forge** | Approval-gated story projects: manifest (`kayock.writer.project.v1`), chapter cards + continuity handoffs, chapter editor with diff verification and backups, versioned drafts, prose manuscript workspace |
| **The Weaver** | Weave 2–4 sources into one new poem, short story, clean prose, or Twine-ready passages — with planner source-map, contamination rejection, and copy-similarity warnings |
| **My Writing** | Every saved poem, story, and version — searchable, grouped, read-only |

All ten literary voice profiles are preserved:

- **Eric — Poet/Narrator** (with optional private source poems — see below)
- **Eric — Short Fiction** (source-derived craft fingerprint)
- Edgar Allan Poe — Gothic Lyric · Beneath the Beats — West Coast Voice ·
  Dust and Duty — Last Gunslinger Voice · The Forsaken Flame — Exile’s Voice
- Robin Hood — The Merry Outlaw · Zorro — The Masked Fox ·
  Dracula — The Ancient Count · Sherlock Holmes — The Consulting Mind

## New in v1.1.0

- **Editorial & Craft Handoff** provides optional non-destructive critiques and suggested revisions, plus browser downloads as HTML, Markdown or plain text. Link to your existing Craft Suite homepage without requiring it. See [Craft Suite notes](docs/CRAFT_SUITE.md).
- **Linux install helper**, installable from a Git clone; no systemd services started or modified by default. See [Installation](docs/INSTALL.md).
- Private poems are intentionally **not included in the public source package**. Author keeps the voice add-on separately.

## Quick start

Requires **Python 3.9+** and any **OpenAI-compatible model endpoint**
(llama.cpp `llama-server`, LM Studio, Ollama, llamafile, vLLM, …).

```bash
# 1. Start a model server, e.g. llama.cpp:
#    llama-server -m your-model.gguf --port 8080

# 2. Start Kayock Writer:
python kayock_writer.py --base-url http://127.0.0.1:8080

# 3. Open http://localhost:8765 — LAN users: http://<this-machine-IP>:8765
```

Full instructions: [docs/INSTALL.md](docs/INSTALL.md) ·
Feature parity and limitations: [docs/PARITY.md](docs/PARITY.md) ·
Private voice pack: [docs/PRIVATE_VOICE_PACK.md](docs/PRIVATE_VOICE_PACK.md)

## Configuration

Everything is configurable via `config.json`, environment variables, or CLI
flags (CLI wins, then env, then config file, then defaults):

```bash
python kayock_writer.py --host 0.0.0.0 --port 8765 \
    --data-dir ./KayockWriterData \
    --base-url http://127.0.0.1:8080 --model local-model
```

Model settings can also be changed live in **Settings → Model endpoint**
(saved to `config.json`, takes effect immediately). The API key is read from
`KAYOCK_MODEL_API_KEY` (preferred) or the config file, and is never logged or
sent to the browser.

See `config.example.json` for the full reference.

## Storage (all app-owned, no FOXAI paths)

```
<data_dir>/
├── Projects/KayockWriter/     poems, short stories, recordings, weaver outputs
│   └── <StoryProject>/        Story Forge projects (manifest, chapters, drafts, prose)
├── NovelForge/                Novel Forge universes (+ Markdown/, Exports/)
├── Reports/KayockWriter/      action receipts
├── Backups/KayockWriter/      automatic pre-overwrite backups
└── voice_packs/               optional private voice packs
```

FOXAI `NovelForge/*.json` universe files can be copied into `<data_dir>/NovelForge/`
directly — the schema is unchanged. FOXAI poem/story draft markdown files can be
copied into the corresponding `Projects/KayockWriter/.../Drafts` folders.

## Tests and verification

```bash
python tests/verify_kayock_writer.py   # fast offline self-check (18 checks)
python tests/run_tests.py              # 53-test suite incl. a mock model endpoint
```

The test suite starts a bundled mock OpenAI-compatible server, so the full
workflows are exercised with no real model and no network access.

## Provenance and license notice

Kayock Writer is an extraction of FOXAI writing-tool code. The upstream
`LICENSE` is a personal-project placeholder, **not** an open-source grant —
see [LICENSE_NOTES.md](LICENSE_NOTES.md) before redistributing. The Eric
poems in `addons/private_eric_poet_narrator/` are copyrighted and private.
