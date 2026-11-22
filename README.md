# Kayock Writer

**A private-first creative writing studio for your own AI models.**

[![Tests](https://github.com/kayock/Kayock-Writer/actions/workflows/tests.yml/badge.svg)](https://github.com/kayock/Kayock-Writer/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Zero third-party Python dependencies](https://img.shields.io/badge/Python_dependencies-0-555)
![Version 1.1.0](https://img.shields.io/badge/Release-v1.1.0-7953CF)

Kayock Writer brings **Poetry Forge, Short Story Forge, Novel Forge, Story Forge, and The Weaver** together in one responsive, browser-accessible workspace. Draft with a literary voice, revise selected passages, organize entire fictional universes, and save your work on storage you control.

It is a **standalone extraction of the writing tools from [FOXAI](https://github.com/kayock/FOXAI_)**, not a FOXAI plugin. Run it on Windows, Linux, or macOS with **Python 3.9+**, no pip installations, and a reachable **OpenAI-compatible chat model endpoint**. A model is not bundled or started for you.

> [!IMPORTANT]
> **LAN security:** v1.1.0 has **no built-in user login or HTTPS**. Anyone who can reach the Writer web port may be able to read or modify writing and settings. Use it only on a trusted LAN, or bind to \`127.0.0.1\` for local-only access. **Do not expose it directly to the public internet.**

## Development release-readiness verification

The development branch now includes a dedicated **real Chromium browser smoke
test** in GitHub Actions. It exercises the actual Finishing Desk interface
against a disposable sample manuscript and mock model: Council roles,
author decisions, optional synthesis, explicitly approved revision and
DOCX/EPUB/PDF browser downloads. Playwright and Chromium are installed
**only in CI**; Writer's Python runtime remains dependency-free.

This is not real-model validation or final release approval. GitHub
also tests an **isolated Linux source installation** and **Windows/Linux
copied-source launch**, checking that custom config/manuscripts remain
untouched. The browser job independently renders a synthetic book PDF
and uploads a short-lived **DOCX/EPUB/PDF visual proof bundle**.
Actual local-model behavior, real-world upgrade/rollback, and human
visual proofing in Word, e-readers and PDF viewers still require
hands-on acceptance. See the
[Release Acceptance Checklist](docs/RELEASE_ACCEPTANCE.md)
and [one-session Real Model Acceptance](docs/REAL_MODEL_ACCEPTANCE.md) for all
remaining gates, with no claimed result for tests that have not run.

## Development branch preview — not yet a release

The [open draft pull request](https://github.com/kayock/Kayock-Writer/pull/1)
contains ongoing v1.2–v1.5 development work. **The released version
remains v1.1.0 on `main`**; these development features are not yet
included in the default `git clone` installation.

The development branch adds author-controlled recovery, streaming
editorial review, approved Story Bible facts with chronology and
relationships, safe model presets, a visual Story Forge corkboard,
independent alternative drafts, and explicit reviewed acceptance
as new chapter versions. Its Finishing Desk now also offers private,
opt-in Voice DNA references, developmental/voice audit modes, and
DOCX/EPUB publishing.

**New v2.0 preview — Editorial Council:** In the Finishing Desk, select
up to three specialized reviewers and explicitly run their independent,
sequential reviews through the already configured model. Read each
report in its own panel, stop the run if needed, and optionally request
one separately confirmed synthesis. No reviewer automatically starts
another project, changes canon, edits a manuscript, or saves a draft.
Each chosen role makes a full model call; synthesis makes one more.

**Per-role model assignments and manual decisions (v2.0 preview):**
Authors can choose a saved Writer Model Profile independently for
each Council reviewer and for synthesis. Model choices are scoped to
that run and never change the active model; credentials for the
active endpoint are not sent to a different endpoint. The separate
Author Decision Board lets the writer highlight individual reviewer
recommendations, mark them Approved for consideration, Rejected,
Deferred or Pending, and explicitly download a JSON record. These
decisions do **not** apply any manuscript edits.

**Controlled Revision Workspace (v2.0 preview):** You can load the
latest verified saved Story Forge chapter, edit a separate proposed
revision, preview its unified diff, and explicitly approve writing a
**new canonical draft version**. Earlier saved versions remain
untouched; changing the source history or proposal after preview
invalidates approval. Council suggestions can inform your choices,
but neither a recommendation nor a decision-board approval is
automatically applied. No model is called during revision acceptance.

**New publishing workflow under development:** Open
**Editorial & Craft Handoff → Full-Book Assembly & Publishing**,
choose a Story Forge project and book, select the exact saved
version of each chapter, adjust their reading order, and preview.
Only then can you download a verified **book DOCX, EPUB 3, or basic PDF**.
No source manuscript file is changed by preview or export.

The book publisher also supports an **optional author-selected JPEG
cover** embedded in DOCX, EPUB and PDF. Common private JPEG metadata
(EXIF/XMP, Photoshop tags and comments) is stripped before packaging.
Covers are never saved into the writing library.

The default PDF renderer uses standard PDF Courier fonts and Windows-1252.
For many additional Unicode glyphs, the author may **optionally supply
a licensed TrueType (.ttf) font for that PDF export**. Writer embeds it
only in the download, without bundling, downloading or saving the font.
This is a simple left-to-right glyph renderer without complex-script
shaping, bidirectional reordering, color emoji or font fallback.
Unsupported glyphs are rejected rather than replaced. **Use DOCX or
EPUB for complex scripts**, and visually proof each book before publishing.

These features run without new mandatory Python dependencies. Automated
tests use mock data and run on Linux and Windows; they do not replace
real-model, browser, Word, e-reader or visual PDF acceptance testing.
The pull request is deliberately left in draft until that validation
and release approval are complete.

[Development details and API notes](docs/STREAMING_AND_CANON.md)

## At a glance

| Workspace | What you can do |
| :-- | :-- |
| 🪶 **Poetry Forge** | Create poems with guided controls for form, rhyme, rhythm, imagery, and literary voice. Polish existing poems, revise selected lines with three alternatives, and browse versioned drafts. |
| 📖 **Short Story Forge** | Generate or polish short fiction with story-specific guidance, chosen voices, and checks that a revision actually changes the text. |
| 🌌 **Novel Forge** | Build universes with characters, settings, artifacts, timelines, mysteries, scenes, and notes. Manage universe files and export a story bible. |
| 📚 **Story Forge** | Organize longer projects, plan chapters, track continuity handoffs, edit drafts, and manage manuscript prose with approval-gated saves and backup-aware editing. |
| 🧵 **The Weaver** | Combine 2–4 source texts into fresh poetry, fiction, prose, or Twine-ready passages with source mapping and reuse warnings. |
| 🗂️ **My Writing** | Search and revisit saved poems, stories, and version groups. |
| ✍️ **Editorial & Craft Handoff** | Request optional critique or suggested revisions **without overwriting the original**, then download HTML, Markdown, or text for further editing. |

One application, one left-hand navigation tree, and an independent writing-data folder. The forges work together but **do not require the rest of FOXAI**.

## Quick start

### Option A — Run from GitHub (Windows, Linux, macOS)

**Requirements:** Git, Python **3.9+**, and a model server with an OpenAI-compatible chat API.

\`\`\`bash
git clone https://github.com/kayock/Kayock-Writer.git
cd Kayock-Writer
python3 kayock_writer.py --base-url http://127.0.0.1:8080 --model local-model
\`\`\`

On Windows, use \`py\` or \`python\` in place of \`python3\` if appropriate.

Open **http://localhost:8765** on the machine hosting Writer. From another device on your trusted LAN, open **http://SERVER-LAN-IP:8765**, replacing \`SERVER-LAN-IP\` with that machine's address.

The \`--base-url\` above is only an **example**: it points to the model server, **not** to Writer's browser address. The model can be on the same machine or another reachable host.

Examples of compatible endpoints:

| Model server | Example base URL |
| :-- | :-- |
| llama.cpp \`llama-server\` | \`http://127.0.0.1:8080\` |
| LM Studio | \`http://127.0.0.1:1234\` |
| Ollama (OpenAI-compatible API) | \`http://127.0.0.1:11434\` |
| A model server elsewhere on your LAN | \`http://MODEL-SERVER-IP:PORT\` |

Choose the real model identifier expected by your server with \`--model\`. For servers needing authentication, set \`KAYOCK_MODEL_API_KEY\` in Writer's environment.

### Option B — Install a separate copy on Linux

\`\`\`bash
git clone https://github.com/kayock/Kayock-Writer.git
cd Kayock-Writer
bash deploy/install-linux.sh
cd "$HOME/Applications/KayockWriter"
python3 kayock_writer.py --base-url http://127.0.0.1:8080 --model local-model
\`\`\`

The install helper **copies the application** to \`~/Applications/KayockWriter\` by default. It does **not** use sudo, create or restart services, alter firewalls, start models, or enable autostart. Existing \`config.json\`, private add-ons, and writing data are preserved. Set \`KAYOCK_WRITER_INSTALL_DIR\` to choose another destination.

There is no need to run the helper if you prefer to run directly from the cloned repository.

**Full instructions:** [Installation & troubleshooting](docs/INSTALL.md) · [Example configuration](config.example.json)

## Your literary voice library

Writer includes **10 literary writing profiles**—instructions for how text is composed, **not text-to-speech voices**.

| Original writer voices | Literary & archetype voices |
| :-- | :-- |
| **Eric — Poet/Narrator** | Edgar Allan Poe — Gothic Lyric |
| **Eric — Short Fiction** | Beneath the Beats — West Coast Voice |
| | Dust and Duty — Last Gunslinger Voice |
| | The Forsaken Flame — Exile's Voice |
| | Robin Hood — The Merry Outlaw |
| | Zorro — The Masked Fox |
| | Dracula — The Ancient Count |
| | Sherlock Holmes — The Consulting Mind |

The profiles guide cadence, imagery, tone, narrative structure, and originality boundaries. They are intended to help create **new writing**, rather than reproduce passages from reference works.

**Private author add-on:** The public repository includes the Eric Poet/Narrator *style profile* but **does not contain the four original reference poems**. The author can install a separately supplied private voice pack locally to restore the full source-informed prompt. Never commit that pack or include it in a public release. When installed, its poems are sent as prompt context to the **configured model endpoint**—only use an endpoint you trust with that material.

[Private voice pack instructions](docs/PRIVATE_VOICE_PACK.md)

## Write, revise, keep the original

Kayock Writer distinguishes **generation**, **suggestion**, and **approved changes**.

- **Poetry / short fiction:** Create with guided prompts, polish a draft, or request alternatives for a selected passage. Saved drafts use metadata and version grouping.
- **Novel building:** Maintain a universe's premise, cast, places, events, secrets, and scenes. Export story-bible content as **JSON, Markdown, or plain text**.
- **Long-form Story Forge:** Use project and chapter workflows with preview-and-approval gates, continuity notes, versioned drafts, and backups before applicable edits.
- **Editorial & Craft Handoff (v1.1.0):** Ask the current model for critique or a suggested passage. Suggestions remain separate until you manually choose to use them.

The interface is a writing workspace, not a replacement for editorial judgment: review generated material and backups before relying on them.

## Optional Craft Suite workflow

Writer can help you prepare prose or poetry for further formatting in **Craft Suite / WordCraft**:

1. Draft or open material in a Forge.
2. Open **Editorial & Craft Handoff** for optional feedback and revision suggestions.
3. Export **HTML**, **Markdown**, or **TXT**. HTML includes print-friendly styling and preserves poetry line/stanza breaks.
4. Open your separately configured Craft Suite homepage and **import the exported file manually**.

**No Craft Suite installation is required.** The optional link opens its homepage; v1.1.0 does **not** claim direct WordCraft API transfer, DOCX creation, or automatic two-way synchronization.

[Craft Suite handoff details](docs/CRAFT_SUITE.md)

## Configuration and data

Common launch options:

\`\`\`bash
# Accessible only from this machine
python3 kayock_writer.py --host 127.0.0.1 --port 8765

# Use a custom data directory and model server
python3 kayock_writer.py \
  --host 0.0.0.0 --port 8765 \
  --data-dir ./KayockWriterData \
  --base-url http://127.0.0.1:8080 \
  --model local-model

# Check model reachability and configuration without launching Writer
python3 kayock_writer.py --check
\`\`\`

Settings can be supplied by **CLI flags → environment variables → \`config.json\` → defaults**, in that order. Model endpoint settings can also be changed from Writer's **Settings** page. A configured model API key is not sent to the browser; prefer the \`KAYOCK_MODEL_API_KEY\` environment variable instead of saving secrets in \`config.json\`.

By default, the app stores its work in \`./KayockWriterData/\`:

\`\`\`text
KayockWriterData/
├── Projects/
│   └── KayockWriter/         # Poems, stories, recordings, story projects
├── NovelForge/               # Universes and story-bible exports
├── Reports/KayockWriter/     # Operation reports / receipts
├── Backups/KayockWriter/     # Pre-overwrite backups
└── voice_packs/              # Optional private author profiles
\`\`\`

You may **copy** compatible existing FOXAI universe JSON files, poem/story Markdown drafts, and Story Forge project folders into the matching locations. Copy rather than move, and back up originals before migrating. Writer does not need FOXAI to be installed or running.

[Configuration reference](docs/INSTALL.md#3-configuration-reference) · [FOXAI parity and known differences](docs/PARITY.md)

## Verify the installation

These checks run with Python's standard library; the workflow tests use a **bundled mock model server**, not a real model:

\`\`\`bash
python3 tests/verify_kayock_writer.py   # 18 self-verification checks
python3 tests/run_tests.py              # 53 original tests
python3 tests/test_upgrade.py           # 6 v1.1.0 upgrade tests
\`\`\`

GitHub Actions runs these checks on **Python 3.9 and 3.12** on pushes and pull requests. See [CI results](https://github.com/kayock/Kayock-Writer/actions/workflows/tests.yml). Local test success does not itself confirm the model server, microphone, or other LAN services in your particular installation.

## Updating from GitHub

When a new version is available, the recommended source-based workflow is:

\`\`\`bash
cd Kayock-Writer
git pull --ff-only
\`\`\`

If you originally used the Linux install helper, run \`bash deploy/install-linux.sh\` again from the updated clone to copy the newer application files. **The helper does not restart the app or touch existing processes.** Stop/restart your own Writer instance when you are ready to use the updated code, after backing up your writing data.

## Notes on security, provenance and licensing

- **No login and HTTP by default:** only expose the web UI to trusted devices. To restrict it to the host, start with \`--host 127.0.0.1\`. Remote internet access would require your own properly configured access controls and TLS termination.
- **Endpoint privacy:** writing prompts are sent to the model endpoint **you configure**. If that endpoint is cloud-hosted or shared, your text may leave your machine.
- **Source provenance:** extracted from [FOXAI](https://github.com/kayock/FOXAI_) at commit \`b510e5c38c0a1fa41f61b6c65e74ce1812f1ecdb\`; FOXAI itself remains separate. Some Story Forge workflows were adapted rather than copied byte-for-byte.
- **License:** this Kayock Writer repository is under the [MIT License](LICENSE). That license does **not** relicense all of FOXAI or the privately held poems. See [LICENSE_NOTES.md](LICENSE_NOTES.md).

---

**Built by Kayock.** A place for poems, stories, imagined worlds, and writing that stays yours.
