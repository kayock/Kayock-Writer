# Kayock Writer — One-Session Real-Model and Publishing Acceptance

This is a **manual acceptance procedure**, not an automatic integration
or release instruction. **Nothing here has been executed against the
author's machines, models, manuscripts or installed services.**

The purpose is to validate the real-world behavior that mock-based GitHub
CI cannot establish. Do not run anything unless the author explicitly
chooses to start a short test. Preserve their current model selection,
timeouts, context window, authentication settings and working services.

## Preparation: keep the test isolated

- Use a **separate disposable Writer data directory**, not the author's
  real writing library. Use an existing trusted Writer test instance or
  start the candidate on a separately chosen localhost port; do not
  stop or overwrite a running installation.
- Use only a model endpoint **already intentionally running**. This
  procedure does not start, load, download, or unload models.
- Avoid hosted API costs unless the author explicitly selects a hosted
  provider; the first pass is intended for an already-running local model.
- Do not import real manuscripts, connected accounts, private Voice DNA,
  Story Bible content, passwords or API keys just to test the pipeline.
- Do **not** change model maximum context, output budget or timeout to
  satisfy the test. Record the model's existing settings and any failure.
- Backups and a separate rollback plan are prerequisites to any test
  against existing user data. Never perform a destructive upgrade as
  part of exploratory validation.

## Controlled test A — ONE reviewer and manual Stop

1. Open the candidate in the browser and enter this **synthetic** passage
   in the Finishing Desk:

   > The bell rang once across the empty harbor. Mira closed the gate.

   Give it the title **Harbor Smoke Test**.
2. Keep Story Bible and Voice DNA **OFF**. Select **only Story Architect**
   in the Editorial Council. Keep the default active model, or select
   one specific already-saved profile intentionally. Do not select
   multiple Council roles or synthesis for this first check.
3. Click **Run selected Council reviews** once and verify the confirmation
   describes exactly **one** model request.
4. Observe whether streaming tokens appear; confirm the reviewer
   references the synthetic passage and its own model label.
5. Record success, endpoint name/model ID (no secrets), whether Stop
   works during generation, and whether a complete nonempty report
   appears. If a call stalls, use **Stop Council**; do not keep it
   running or retry automatically. If it fails, record the exact error
   and stop the acceptance test.
6. Verify the original two sentences are unchanged, no manuscript
   was saved, and no project or canon entry was created.

**Only if test A passes and the author agrees**, do a second author-
initiated test of an optional synthesis or a second saved model profile.
Do not sweep the entire model inventory. The existing application
timeouts, contexts, and resource-management policy remain unchanged.

## Controlled test B — real-model Council acceptance

On an explicitly authorized test session:
- Run two selected roles sequentially. Confirm each uses the assigned
  saved profile and they do not influence each other's prompt.
- If a second endpoint requires credentials, report a normal failure
  rather than copying credentials from the current endpoint.
- Click synthesis separately; confirm disagreements are visible and
  no suggestion becomes a manuscript edit.
- Export a small author Decision Board; its Approved-for-consideration
  status is advisory only.

Use synthetic input for all model calls. Do not infer response quality
from a mock-only CI pass.

## Controlled test C — visual publishing proof

Download the synthetic proof bundle from the **successful exact-commit
GitHub Actions browser-smoke job**. Open the workflow run, then in
Artifacts select **kayock-writer-synthetic-publishing-proofs**. The bundle
contains a small fictional example book as DOCX, EPUB and PDF, plus PDF
page PNG renders and extracted PDF text produced by an independent
reader on the CI runner. The artifact is retained for seven days.

Review:
1. In **Microsoft Word or a compatible DOCX viewer**, inspect title,
   contents, chapter order, text accuracy, page breaks, and optional
   cover placeholders. A ZIP test alone cannot prove these.
2. In **an actual EPUB reader**, inspect EPUB navigation, chapter order,
   metadata, and paragraph/line breaks.
3. In **an actual PDF viewer**, inspect every rendered page, selection
   and text search, wrapping, page numbers and margins.
4. For author-selected cover/TTF fonts, make **separate** opt-in tests
   with files the author owns and has rights to embed. No fonts are
   shipped in GitHub artifacts.
5. Record the reader application and version, OS, observations and
   Pass / Fail. Attach a screenshot **only of synthetic text** if there
   is a rendering defect.

## Controlled test D — installation/rollback, only with explicit approval

The automated test_install_staging.py validates Linux helper
behavior on a disposable install, symlink refusal, and clean copied-
source startup on Linux and Windows. **It does not validate upgrading
a real running installation**, and Windows has no native installer in
this repository. Never claim that those gates passed based on staging.

For real environments, choose a separate test destination, back up all
current config and writing data, record hashes, start the test copy
without replacing the running copy, and verify rollback of both code
and data. Any upgrade of an actual installation needs separate explicit
author approval.

## Acceptance record

| Gate | Result | Notes |
| --- | --- | --- |
| Actual one-role local model request | Not tested | Requires deliberate author-selected endpoint |
| Cancellation on actual model | Not tested | Do not test by running hours-long prompts |
| Optional alternate saved model profile | Not tested | Only after first local test passes |
| Real Word/EPUB/PDF visual inspection | Not tested | Synthetic artifact available from exact-head CI success |
| Actual Windows install/upgrade | Not tested | No native Windows installer in repository |
| Actual Linux install/upgrade/rollback | Not tested | CI staging is not a real upgrade |
| Explicit owner approval for merge/release | Not given | Keep PR draft |

This procedure does not change the application's authentication policy,
provider configuration, timeouts, contexts, active services, or saved data.
