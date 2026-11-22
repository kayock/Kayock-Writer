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
| Synthetic proof bundle | CI uploads example DOCX/EPUB/PDF, PDF page PNGs and extracted text for human inspection |

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
named **kayock-writer-synthetic-publishing-proofs** with the DOCX,
EPUB, PDF, rendered PDF pages, and extracted text. No user manuscripts
or licensed author-supplied font files are included.

For an optional **single-real-model smoke test** and the manual proof
procedure, see [Real Model Acceptance](REAL_MODEL_ACCEPTANCE.md).
It has not been executed against author machines or endpoints.

The browser job runs only on CI; Playwright and Chromium are **development testing tools** and are not part of the installed Kayock Writer runtime. No production configs, actual user writing, private voice profiles, online endpoints or model credentials are loaded. A failed run may upload a screenshot containing only synthetic fixture text.

To reproduce this browser smoke test on an isolated test workstation with Python 3.12 and Node 24:

~~~sh
npm install --no-save --ignore-scripts playwright@1.65.1
npx playwright install --with-deps chromium
node tests/browser_release_smoke.cjs
~~~

The script starts and stops its **own temporary local fixture server**. Never point it at a real user installation.

## Mandatory human acceptance gates (not yet verified)

For each gate, record a date, Pass / Fail / Not tested, and the actual result. The isolated Linux acceptance findings reported below are **not a production upgrade or release approval**. Unlisted gates remain Not tested. Passing CI alone does not complete these gates.

| Gate | What to verify |
| --- | --- |
| Windows clean install | Starts from release candidate with the chosen data directory |
| Linux clean install | Runs on documented Python-only runtime and existing local configuration |
| Existing-user upgrade | Backup, migrations, unchanged original manuscripts, tested rollback |
| Actual local model | Streaming review works without unreasonable waiting; Stop cancels |
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
| Real local model inference | **NOT TESTED** | Selected localhost endpoint refused connections; running Ollama listed no loaded model; no model was started or retried |
| Controlled revision | PASS | Explicit preview/approval appended v003 while earlier versions remained unchanged |
| Author Decision Board | PASS | Manual approve-for-consideration exported JSON; no manuscript write |
| DOCX | PASS | Synthetic two-chapter file visually inspected in LibreOffice |
| EPUB 3 | Structural PASS; **e-reader NOT TESTED** | Correct navigation and Cyrillic text; no actual reader inspection |
| PDF | PASS, restricted edition | Western-text PDF visually inspected; Cyrillic appropriately refused by basic PDF font |
| JPEG cover and optional Unicode TrueType PDF in actual browser | **NOT TESTED** | Automated cover/Unicode regression tests passed, but real browser options not exercised |
| Windows installation and existing-user upgrade/rollback | **NOT TESTED** | Temporary CI copied-source launch is not a Windows installer or production upgrade |
| Narrow-screen UI | Issue reported | Appbar blocked navigation clicks until widening the browser; development-branch responsive fix and Chromium regression added, **local retest still pending** |
| Saved chapter version menu after acceptance | Issue reported | Menu showed v002 after v003 save until refresh; development-branch immediate-label fix and regression added, **local retest still pending** |

Local test environment reportedly ran 26 Python test modules (220 tests),
18 application self-checks and the isolated Chromium fixture successfully.
Python 3.14.4 emitted ResourceWarnings when handling expected HTTP errors,
without test failures. No real-model test was performed.

**Outstanding release gates:** one bounded real-model request, actual EPUB
reader inspection, browser verification of cover/font, Windows install if
required for distribution, upgrade/rollback, and explicit owner approval.
The development application may still display the prior released
`1.1.0` version string until versioning is finalized; do not label
the draft as a released v2.0 build.

## Known limitations

- CI's browser integration is **real Chromium UI testing with an artificial model**, not an evaluation of real AI response quality, local model loading, performance or endpoint connectivity.
- The Council uses a sequential series of per-role model requests. Multiple slow models can create long total runtimes; no model automatically starts.
- “Approved for consideration” on the Decision Board never changes manuscript files. An additional, explicit author-controlled revision approval is needed to append a version.
- DOCX/EPUB/PDF tests validate structure and downloads but not professional page layout or reader compatibility. A user-selected Unicode TrueType PDF has only simple left-to-right rendering; complex-script shaping, fallback and color emoji are not supported.
- Release readiness remains blocked on human acceptance, especially real-model, actual document viewer and **production** installation/rollback tests. Passing disposable installation staging is not a claim that a running installation was upgraded or rolled back.

## Release decision record

- Development PR: https://github.com/kayock/Kayock-Writer/pull/1
- Exact candidate commit: record after all checks
- Final Actions run: record after all checks
- Manual test result: PARTIAL isolated Linux acceptance reported; real model and release gates still open
- Owner approval to merge: NOT GIVEN
- Release decision: HOLD DRAFT

Do not mark a release complete based on GitHub automation alone.
