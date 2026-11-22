# Kayock Writer — Streaming + Living Canon (development branch)

This document describes the first implemented slices of the v1.2/v1.3 upgrade.
The application version is **not** bumped and the branch remains a draft until
all planned release acceptance criteria are met.

## Live editorial review

The Finishing Desk now offers:

- **Stream review**: streamed model output appears token by token in the
  read-only result area. Uses the same prompts, validation, model, timeout,
  and token budget as Classic review.
- **Stop**: asks the server to cancel the current generation, interrupting
  the upstream HTTP connection where supported.
- **Classic review**: retains the original non-streaming endpoint and behavior.

The original passage is never overwritten or saved by either endpoint.
Partial responses are only in the browser's unsaved result area.

### Protocol

POST `/api/writer/editorial/stream` with the same JSON as
`/api/writer/editorial/review`:

```json
{
  "text": "An original passage...",
  "title": "Chapter draft",
  "writing_type": "prose",
  "mode": "review",
  "direction": "Focus on pacing and preserve voice."
}
```

The response is `text/event-stream`. Event types:

- `start`: contains `generation_id`.
- `token`: contains a `text` delta.
- `done`: completed successfully, `saved: false`, `source_unchanged: true`.
- `cancelled`: stopped before completion; partial text is not saved.
- `error`: rejected or interrupted stream; never report successful completion.

POST `/api/generation/{generation_id}/cancel` (empty JSON acceptable) to
cancel an active generation. A stopped or unknown generation returns
`ok: false`.

Streaming currently applies to **Editorial & Craft Handoff** only; other
Forges keep their proven non-streaming behavior until separately upgraded.
Unsupported providers should use **Classic review**, not an implicit retry
that might duplicate work.

## Living Story Bible: manual, evidence-linked canon

Novel Forge offers a **Canon Review** panel when a saved universe is selected.

1. The author proposes a fact and supplies an evidence source and short
   supporting excerpt.
2. The fact remains `proposed` and cannot be treated as established canon.
3. The author explicitly approves or rejects it.
4. Only `approved` records are returned by the canon store's
   `approved_context` interface for future context assembly.

Each fact may include a chapter, fictional-world time, and narrative order.
These fields are recorded separately to support nonlinear storytelling.
Evidence is **author-supplied** at present; no automatic quote verification
or contradiction checking is claimed.

### Canon API

- GET `/api/novelforge/canon?name=Saved_Universe`: list canon records.
- POST `/api/novelforge/canon/propose`: create a proposed fact.
- POST `/api/novelforge/canon/review`: change a proposed fact's state once.

Example proposal:

```json
{
  "universe": "Saved_Universe",
  "kind": "character",
  "subject": "Elena",
  "claim": "Her scar is on her left arm.",
  "source": "Book 1, Chapter 3",
  "quote": "She touched the scar on her left arm.",
  "chapter": "03",
  "world_time": "Day 4",
  "narrative_order": "Book 1, Chapter 3"
}
```

Approve by submitting `universe`, `fact_id`, and
`decision: "approved"`, or reject with `decision: "rejected"`.

Records are stored separately under `NovelForge/.canon/<universe>/facts.json`.
No existing universe JSON, manuscript, or Forge approval contract is altered
when proposing, accepting, or rejecting a fact. Rename operations relocate
the canon records; deletion of the parent universe **retains** separate canon
records for recovery and reports that fact in the response.

The canon records are **not yet injected into model prompts**. Automated
extraction, source verification, timeline query, evidence-aware context
assembly, and contradiction detection are future milestones.

## Safety and testing

No model downloads, services, authentication gates, provider changes, timeout
changes, cloud dependencies, or migrations are introduced. Core remains
Python standard library only.

Offline GitHub Actions runs on Linux/Python 3.9, Linux/Python 3.12, and
Windows/Python 3.12:

```bash
python tests/run_tests.py
python tests/test_upgrade.py
python tests/test_foundation.py
python tests/test_canon_api.py
python tests/test_streaming.py
python tests/verify_kayock_writer.py
python tests/check_ui_js.py
```

The JavaScript syntax check uses Node only when available in the test
environment, not in the runtime. All model calls in tests use local mock
servers. Real local-model performance and browser usability still require
optional integration testing on the author's hardware before release.
