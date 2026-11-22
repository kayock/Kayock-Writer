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

The new browser-smoke GitHub Actions job exercises the **actual browser UI and HTTP server**. It launches a temporary sample Story Forge project and a deterministic **mock model**. The job clicks through independent Council reviews, an author-marked decision, optional synthesis, a verified revision preview and acceptance, and real DOCX/EPUB/PDF browser downloads. It confirms that edits after preview disable export and checks for uncaught JavaScript errors.

The browser job runs only on CI; Playwright and Chromium are **development testing tools** and are not part of the installed Kayock Writer runtime. No production configs, actual user writing, private voice profiles, online endpoints or model credentials are loaded. A failed run may upload a screenshot containing only synthetic fixture text.

To reproduce this browser smoke test on an isolated test workstation with Python 3.12 and Node 24:

~~~sh
npm install --no-save --ignore-scripts playwright@1.65.1
npx playwright install --with-deps chromium
node tests/browser_release_smoke.cjs
~~~

The script starts and stops its **own temporary local fixture server**. Never point it at a real user installation.

## Mandatory human acceptance gates (not yet verified)

For each gate, record a date, Pass / Fail / Not tested, and the actual result. **All are currently Not tested.** Passing CI alone does not complete these gates.

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

## Known limitations

- CI's browser integration is **real Chromium UI testing with an artificial model**, not an evaluation of real AI response quality, local model loading, performance or endpoint connectivity.
- The Council uses a sequential series of per-role model requests. Multiple slow models can create long total runtimes; no model automatically starts.
- “Approved for consideration” on the Decision Board never changes manuscript files. An additional, explicit author-controlled revision approval is needed to append a version.
- DOCX/EPUB/PDF tests validate structure and downloads but not professional page layout or reader compatibility. A user-selected Unicode TrueType PDF has only simple left-to-right rendering; complex-script shaping, fallback and color emoji are not supported.
- Release readiness remains blocked on human acceptance, especially real-model, actual document viewer and installation/rollback tests.

## Release decision record

- Development PR: https://github.com/kayock/Kayock-Writer/pull/1
- Exact candidate commit: record after all checks
- Final Actions run: record after all checks
- Manual test result: NOT TESTED
- Owner approval to merge: NOT GIVEN
- Release decision: HOLD DRAFT

Do not mark a release complete based on GitHub automation alone.
