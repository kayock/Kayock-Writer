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

## Approved-only context and continuity (next v1.3 slice)

Novel Forge now offers a **Canon Retrieval & Continuity Workshop**:

- **Retrieve approved facts** accepts a query/excerpt and deterministically
  ranks author-approved canon by subject, claim and cited source. Each result
  includes its fact ID, evidence, chapter/world time and narrative order.
  Pending and rejected proposals are never used.
- **Check possible continuity tensions** compares a pasted excerpt with
  approved facts and flags only explicit opposite statements about named
  characters (currently **alive/dead** and **scar side**). Every warning
  includes the approved claim, draft excerpt and original evidence. It may
  be explained by time, point of view or character development; it is a
  **review suggestion**, never a proven contradiction. No text is changed.
- **Use approved Story Bible references in Editorial** is an author-controlled
  checkbox in the Finishing Desk, **off by default**. Select a saved universe
  and a maximum **number of facts** (1–200, initial value 12). Both classic
  and streaming editorial reviews use the same ranked approved references,
  in a clearly marked reference block. No other Forge uses them implicitly.

Preview endpoints:
- POST `/api/novelforge/canon/context` with
  `{"universe":"Saved_Universe","query":"Elena enters the room","limit":12}`.
  Returns selected approved facts, relevance scores, sources, a copyable
  context string, and an *advisory* estimated token count.
- POST `/api/novelforge/canon/continuity` with
  `{"universe":"Saved_Universe","text":"Elena is dead."}`.
  Returns only read-only potential-tension warnings with evidence.
- The existing POST `/api/writer/editorial/review` and
  `/api/writer/editorial/stream` accept optional
  `"use_canon":true`, `"universe":"Saved_Universe"`, and
  `"canon_limit":12`. Missing or false `use_canon` preserves existing
  behavior exactly.

**Limit 12 refers to retrieved fact records, not model context size.**
The configured model, maximum output tokens, timeout and context settings
are unchanged. Authors can retrieve up to 200 records deliberately.
A nonempty query with no approved matches yields an empty context block,
not unrelated filler. No embeddings, model loading or extra dependency
is required for this stage.

Model-generated fact extraction, cross-chapter causal/knowledge timelines,
semantic contradiction detection, automatic source verification, and
general drafting across other Forges are **not** claimed complete. In
particular, the current rule-based linter cannot prove that a novel has no
continuity issues.

## Passive model capability inspection (v1.2 incremental)

In Settings, **Inspect advertised capabilities** requests the configured
endpoint's `GET /v1/models` metadata **without running inference**.
The result lists model IDs and reports only explicitly declared context
window, tool calling, vision and streaming capabilities, when available.
Absent data appears as `null` (unknown), not as unsupported. This is
read-only; it does not save profiles, alter endpoints, reduce context/timeout,
start models, or make any inference request.

The associated `GET /api/model/capabilities` endpoint returns the same
diagnostics. Capability probes and saved routing profiles are separate
future work; no support is inferred from model names or guessed hardware.

## Novel Forge save protection (v1.2)

Existing universes now receive uniquely named JSON and Markdown backups
before a subsequent save overwrites them. Universe JSON and Markdown mirrors
are replaced atomically. Same-filename rename operations retain the live
universe instead of deleting it, and duplicate operations refuse to overwrite
an existing universe. These changes use the existing local storage folders;
they do not alter writing content, create cloud copies, or add requirements.

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
python tests/test_novel_storage_safety.py
python tests/test_canon_api.py
python tests/test_context_engine.py
python tests/test_model_capabilities.py
python tests/test_streaming.py
python tests/verify_kayock_writer.py
python tests/check_ui_js.py
```

The JavaScript syntax check uses Node only when available in the test
environment, not in the runtime. All model calls in tests use local mock
servers. Real local-model performance and browser usability still require
optional integration testing on the author's hardware before release.
