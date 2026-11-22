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

## Verified universe backup recovery (v1.2)

Novel Forge now includes a manual **Backup Recovery** panel for an existing,
saved universe. The author can list prior JSON snapshots, preview their
premise, date, title and section counts alongside the current version, then
deliberately confirm restoration. A preview supplies a fingerprint of the
backup and the current JSON/Markdown; any later change invalidates that
confirmation. Corrupted backups, path traversal and mismatched universes are
rejected before any restoration.

A confirmed restore makes a *new* local backup of the current saved JSON and
Markdown before overwriting. The selected original snapshot is restored
without dropping unknown extension keys, and the Markdown mirror is rebuilt.
If the mirror write fails, rollback of the prior content is attempted. No
background restore, cloud copy, automatic recovery or model calls occur.

This version deliberately restores only **existing Novel Forge universes**;
a deleted universe or an unrelated Story Forge project is not automatically
recreated. The web API serializes universe writes with restore operations,
and tests reject stale restore previews even when another save races with
recovery. Existing damaged JSON is refused by save/rename/duplicate, never
silently treated as an empty universe. Older backups larger than the explicit 32 MiB safety preview
limit need manual recovery. It does not restore the separate approved-canon
review record (which remains stored independently).

## Time-scoped continuity and explicitly assigned knowledge (v1.3)

Author-approved canon proposals now accept optional `known_by` (a list of
named characters) and independent `learned_time`. An empty list means
**unspecified**, not "everyone knows". The world event date and the time
a character learns about it are **different fields**.

The Novel Forge workshop provides:

- **World chronology**, grouped into separately comparable Day N and
  YYYY-MM-DD sequences. Unknown or differently formatted times remain
  unplaced rather than being silently sorted.
- **Character knowledge**, listing only facts that the author explicitly
  assigned to that character. When "as of" a world time is supplied, facts
  learned later are excluded and unknown/incomparable learning times
  are displayed separately as uncertain.
- **Continuity at a chosen time**, selecting the latest author-approved
  state at or before that moment for each comparable character attribute,
  skipping future or incomparable declarations. Without a time entered,
  the earlier advisory review remains available.

Read-only endpoints:

- POST `/api/novelforge/canon/chronology` with
  `{"universe":"Saved_Universe"}`.
- POST `/api/novelforge/canon/knowledge` with
  `{"universe":"Saved_Universe","character":"Elena","at_world_time":"Day 7"}`.
- POST `/api/novelforge/canon/continuity` can include
  `"world_time":"Day 7"` to select temporal comparison.

Only the literal **Day N** and **YYYY-MM-DD** patterns are comparable in
this first implementation. They are never compared to each other. This is
an evidence-linked heuristic, not a complete causality engine or a claim
that an unrecorded character transition never occurred. Narrative display
order is retained separately; no timeline is automatically edited.

## Saved local model presets (v1.2)

Settings now contains **Saved Model Profiles**, an optional local preset
library. A preset includes the six existing endpoint fields: base URL, chat
path, health path, health kind, model name and timeout. Names are author
chosen; new names must be unique.

- **Save form as new preset** writes the six fields to
  `Projects/KayockWriter/ModelProfiles/profiles.json`.
- **Load preset into form** fills the Settings editor but does **not** change
  the active model, connect to the endpoint, run inference or save config.
- The author must **review and explicitly use the existing Save endpoint
  settings button** to change the active endpoint.
- **Delete preset** needs confirmation, retains a backup of the prior preset
  library and does not touch active settings.
- Credentials and API keys are never stored or returned by the profile
  library. Saved presets cannot hold arbitrary secret/config fields.
- Existing model context limits, endpoint timeouts, output token budgets,
  activation behavior and environment overrides are not automatically
  changed. This feature does not implement hidden model routing or preload
  models.

The APIs are GET `/api/model/profiles`, POST
`/api/model/profiles/save` with `{"name":"...","settings":{...}}`, and
POST `/api/model/profiles/delete` with `{"profile_id":"..."}`.
Damaged profile libraries are refused rather than overwritten.

## Relationship Explorer — initial visual studio slice (v1.4)

Novel Forge now contains an optional SVG **Relationship Explorer**, showing
approved story connections as an interactive node-and-edge map. Click a node
to focus that entity; use **Show all** to reset. Under the graph, each link
displays its original author-approved claim, evidence source, fictional-world
time, and narrative order.

A relationship proposal can now explicitly name `related_to` (the target
entity) and `relation_type` (e.g. sibling, rival, ally), along with its
existing author-supplied evidence and approval workflow. These two new
optional fields are used only for the `relationship` kind and must be
supplied together. Legacy claims without explicit endpoints remain intact
but are **not** guessed into graph edges. Only approved structured facts
are graphed. The visualization is deterministic, local and needs no model
calls, browser build tooling or additional Python libraries.

POST `/api/novelforge/canon/relationships` accepts the saved `universe`,
optional `focus` and `max_edges` (1–250, default 150). Large graphs are
explicitly truncated; proposed/rejected facts never appear. This is the
first relationship visualization, not the complete v1.4 corkboard, scene
graph, or branching-manuscript system.

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
python tests/test_recovery.py
python tests/test_canon_api.py
python tests/test_context_engine.py
python tests/test_timeline.py
python tests/test_relationships.py
python tests/test_model_capabilities.py
python tests/test_model_profiles.py
python tests/test_streaming.py
python tests/verify_kayock_writer.py
python tests/check_ui_js.py
```

The JavaScript syntax check uses Node only when available in the test
environment, not in the runtime. All model calls in tests use local mock
servers. Real local-model performance and browser usability still require
optional integration testing on the author's hardware before release.
