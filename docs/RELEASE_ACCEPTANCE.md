# Kayock Writer — Release Acceptance Checklist

**Scope:** Draft PR #1 (feature/writer-v1.2-foundation), including the v2.0 Editorial Council, controlled revision, and publishing features.

**Status: DEVELOPMENT ONLY — not released.** This checklist does not authorize merging, installations, automatic edits, model changes, or release tags.

## Automated GitHub Actions gates

| Gate | Required evidence |
| --- | --- |
| Python tests on Linux Python 3.9 | Success on exact PR head |
| Python tests on Linux Python 3.12 | Success on exact PR head |
| Python tests on Windows Python 3.12 | Success on exact PR head |
| Real Chromium UI smoke test | Success on exact PR head |
| JavaScript syntax and route regression | No failures |
| Canonical draft integrity | Old versions preserved; stale previews refused |
| Book package integrity | Valid DOCX/EPUB ZIP and direct PDF content |
| Credential isolation | Cross-endpoint API key not forwarded |
| Disposable Linux installer | Repeated temp-dir installs preserve existing config/manuscripts; symlink target refused |
| Windows and Linux copied-source launch | Temporary copy starts localhost-only without real models or existing user data |
| Independent PDF reader | Poppler renders synthetic PDF pages and extracts expected author text |
| Synthetic proof bundle | CI uploads example DOCX/EPUB/PDF, optional-cover DOCX/EPUB, rendered PDF and EPUB page PNGs, and extracted PDF text for inspection |
| Optional JPEG cover through browser | CI uploads synthetic JPEG via actual browser control; independently checks DOCX/EPUB cover assets and PDF image XObject |
| Unicode TrueType PDF through browser | CI selects system DejaVuSans TTF, previews/export PDF with Omega, verifies embedded font and uses Poppler to extract/render glyph; **font and font-embedded PDF not uploaded as artifacts** |
| EPUB XHTML reading proof | CI independently checks EPUB 3 mimetype/spine/TOC, then Chromium renders title, cover, chapters and follows TOC link. **Not a dedicated EPUB e-reader test** |

The new browser-smoke GitHub Actions job exercises the **actual browser UI and HTTP server**. It launches a temporary sample Story Forge project and a deterministic **mock model**. The job clicks through independent Council reviews, an author-marked decision, optional synthesis, a verified revision preview and acceptance, and real DOCX/EPUB/PDF browser downloads. It confirms that edits after preview disable export and checks for uncaught JavaScript errors.

The final CI job also runs the disposable staging tests in
tests/test_install_staging.py. It verifies the real optional Linux
source-copy helper in a temporary installation and separately launches
an isolated copied-source Writer server on Windows and Linux. **There
is no native Windows installer**, and this does not prove in-place
upgrades of a real installation.

On a successful browser-smoke job, the CI runner uses Poppler to render
the sample book PDF to page PNGs and independently extract its text.
The job uploads a **seven-day synthetic publishing proof artifact**
named **kayock-writer-synthetic-publishing-proofs** with the default
DOCX/EPUB/PDF, optional-cover DOCX/EPUB, rendered PDF and EPUB
page screenshots, and extracted PDF text. A separately extracted EPUB
title, table of contents, CSS and chapter set is included solely for
XHTML browser proof. An optional system TrueType font is selected through
Writer's browser controls for a Unicode PDF test, but the test font and
font-embedded PDF remain CI-private and are not uploaded as artifacts.
No user manuscripts or author-supplied artwork are included.

The added Chromium EPUB step verifies that the title, selected JPEG cover,
two chapter pages, and first table-of-contents link actually render.
This is **not** the same as opening the EPUB file in a dedicated e-reader;
that manual acceptance gate remains open.

For an optional **single-real-model smoke test** and the manual proof
procedure, see [Real Model Acceptance](REAL_MODEL_ACCEPTANCE.md).
A separate, owner-reported single-real-model acceptance was subsequently performed on the isolated Linux test copy; see the dated results below. GitHub CI itself still uses a mock and never calls the author's models.

The browser job runs only on CI; Playwright and Chromium are **development testing tools** and are not part of the installed Kayock Writer runtime. No production configs, actual user writing, private voice profiles, online endpoints or model credentials are loaded. A failed run may upload a screenshot containing only synthetic fixture text.

To reproduce this browser smoke test on an isolated test workstation with Python 3.12 and Node 24:

~~~sh
npm install --no-save --ignore-scripts playwright@1.65.1
npx playwright install --with-deps chromium
node tests/browser_release_smoke.cjs
~~~

The script starts and stops its **own temporary local fixture server**. Never point it at a real user installation.

## Mandatory human acceptance gates (partially verified)

For each gate, record a date, Pass / Fail / Not tested, and the actual result. The isolated Linux acceptance findings reported below are **not a production upgrade or release approval**. Unlisted gates remain Not tested. Passing CI alone does not complete these gates.

| Gate | What to verify |
| --- | --- |
| Windows clean install | Starts from release candidate with the chosen data directory |
| Linux clean install | Runs on documented Python-only runtime and existing local configuration |
| Existing-user upgrade | Backup, migrations, unchanged original manuscripts, tested rollback |
| Actual local model | **PASS for one live streamed review** (see November 22 report); cancellation was NOT TESTED because review finished normally |
| Actual online model, only if chosen by author | Explicit consent for any private references, no leaked credentials |
| Council per-role model mapping | Endpoint/model name/timeout correctly used; offline endpoints fail gracefully |
| Voice DNA and Story Bible | No private content shared without explicit author opt-in |
| Author Decision Board | No automatic acceptance, notes exported only on request |
| Controlled Revision Workspace | Full diff, exact approval, new version saved, prior versions recoverable |
| Word document | Opens and visually preserves paragraphs, heading breaks and cover |
| EPUB reader | Reads all chapters, TOC, author metadata and cover, correct ordering |
| PDF viewer | Pages, margins, line wrapping, searchability and optional cover/font checked |
| Accessibility | Keyboard navigation, visible focus, labels, zoom and mobile layout |
| LAN and security | Existing auth/permissions unchanged; no unrequested security gates |
| Real-world long manuscript | Page and memory limits; no silent content loss or truncation |
| Final README / installation | Instructions match the final merge commit |
| Explicit owner release approval | No merge or tag before author approval |

## Isolated Linux candidate acceptance — reported November 22, 2026

The owner shared a Cursor-generated acceptance report from a **separate Linux
development-branch installation**. These are reported local test results, not
checks independently executed in this GitHub Actions run. The report states
that the previous existing Writer installation was left unchanged, with no
new systemd service, startup task, firewall rule, API key or timeout change.

| Check | Reported status | Evidence and remaining qualification |
| --- | --- | --- |
| Isolated Linux installation and startup | PASS | Separate development copy returned HTTP 200; no existing installation overwritten |
| Story Forge, chapter history and recovery | PASS | Synthetic project; original chapter version hashes survived v001/v002/v003; recovery suite passed |
| Editorial Council UI | PASS, **mock only** | Exactly one selected role; streamed mock response is not evidence of real-model accuracy |
| Real local model inference | **PASS (subsequent real-model check)** | Initial localhost-only check was NOT TESTED. Later one live Story Architect review on Portable Ollama llama3.2:3b streamed successfully, 0.915 s first token, 18.488 s total; no cancellation needed |
| Controlled revision | PASS | Explicit preview/approval appended v003 while earlier versions remained unchanged |
| Author Decision Board | PASS | Manual approve-for-consideration exported JSON; no manuscript write |
| DOCX | PASS | Synthetic two-chapter file visually inspected in LibreOffice |
| EPUB 3 | Structural PASS; **e-reader NOT TESTED** | Correct navigation and Cyrillic text; no actual reader inspection |
| PDF | PASS, restricted edition | Western-text PDF visually inspected; Cyrillic appropriately refused by basic PDF font |
| JPEG cover and optional Unicode TrueType PDF in actual browser | **CI browser PASS; installed UI NOT TESTED** | Automated fixture uploads synthetic cover and system font through actual browser controls, checks exports and Poppler glyph extraction; not a claim about the installed test copy |
| Windows installation and existing-user upgrade/rollback | **NOT TESTED** | Temporary CI copied-source launch is not a Windows installer or production upgrade |
| Narrow-screen UI | **PASS on updated isolated installation** | Commit 1e45fe6 tested at 390×844: measured sidebar started below header; Home, Story Forge, Editorial navigation clickable; desktop navigation also passed |
| Saved chapter version menu after acceptance | **PASS on updated isolated installation** | Explicit save from Chapter 01 v3 to v4 immediately updated chapter selector to v4 · 33 words; older chapter hashes unchanged |

Local test environment reportedly ran 26 Python test modules (220 tests),
18 application self-checks and the isolated Chromium fixture successfully.
Python 3.14.4 emitted ResourceWarnings when handling expected HTTP errors,
without test failures. This was the **initial** isolated-acceptance pass;
the later real-model and UI retest results are documented below.

### Real-model Editorial Council acceptance — reported November 22, 2026

The owner shared Cursor's test report for the updated isolated installation
(commit `1e45fe6`). The test used **Ubuntu Station for Writer** and
**Ubuntu Portable** (`10.0.0.45`) for inference, via existing Ollama at
`http://10.0.0.45:11434`, model `llama3.2:3b` (3.2B, Q4_K_M).
The model was **loaded on demand**, not already resident; no download was made.
Only one Story Architect reviewer request was executed using the synthetic
passage about Mira closing the gate at the empty harbor. Story Bible,
Voice DNA, synthesis, and other reviewers were disabled.

| Evidence | Reported result |
| --- | --- |
| Real endpoint and model identification | PASS — Portable Ollama, `llama3.2:3b`; Writer showed `Active: llama3.2:3b` |
| Actual Editorial Council streaming | PASS — first token in **0.915 seconds** |
| One completed real-model review | PASS — **18.488 seconds** total; content discussed the harbor, bell, Mira, and gate |
| External 60-second limit | PASS — finished before limit; cancellation **NOT TESTED** |
| Number of model generation requests | **1**, no retries |
| Manuscript and project integrity | PASS — chapter v1–v4, Chapter 02 v1, draft manifest, project file unchanged; 27 data files retained |
| Test Writer model configuration restored | PASS — original SHA-256 `29ee10e6eb9a8f350c20ddeac9d4121edda946212fbaf94a564ae0189c0afc67`; localhost endpoint, 420s timeout, no key |
| Portable loaded-model state restored | PASS — Ollama returned an empty loaded-model list after the test |
| Existing Writer production installation | PASS — port 8768 left unchanged; test copy remains on port 18765 |

These results are **reported from Cursor on the user's isolated machines**;
GitHub Actions does not independently execute real model inference. No real
model is needed to repeat this acceptance gate unless a new defect requires it.

**Outstanding release gates:** dedicated EPUB reader inspection, optional
cover/font visual review on an installed user-approved test copy if desired,
release-target installation and upgrade/rollback where applicable,
long-manuscript and accessibility checks, and explicit owner approval.
The development application may still display the prior released
`1.1.0` version string until versioning is finalized; do not label
the draft as a released v2.0 build.

## Known limitations

- CI's browser integration is **real Chromium UI testing with an artificial model**, not an evaluation of real AI response quality, local model loading, performance or endpoint connectivity.
- The Council uses a sequential series of per-role model requests. Multiple slow models can create long total runtimes; no model automatically starts.
- “Approved for consideration” on the Decision Board never changes manuscript files. An additional, explicit author-controlled revision approval is needed to append a version.
- DOCX/EPUB/PDF tests validate structure and downloads but not professional page layout or reader compatibility. A user-selected Unicode TrueType PDF has only simple left-to-right rendering; complex-script shaping, fallback and color emoji are not supported.
- Release readiness remains blocked on remaining human acceptance, particularly actual EPUB reader verification, optional publishing visuals and **production** installation/rollback tests. The reported one-model live Editorial Council acceptance passed; cancellation was not exercised. Passing disposable installation staging is not a claim that a running installation was upgraded or rolled back.

## Release decision record

- Development PR: https://github.com/kayock/Kayock-Writer/pull/1
- Exact candidate commit: record after all checks
- Final Actions run: record after all checks
- Manual test result: PARTIAL isolated Linux acceptance reported; one real-model Editorial Council review PASS; other release gates still open
- Owner approval to merge: NOT GIVEN
- Release decision: HOLD DRAFT

Do not mark a release complete based on GitHub automation alone.
