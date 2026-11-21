# Parity report — FOXAI → Kayock Writer

Source: `core/foxai_web.py` and `core/VERIFY_KAYOCK_WRITER_V2.py` at
`kayock/FOXAI_` commit `b510e5c38c0a1fa41f61b6c65e74ce1812f1ecdb` (fetched
read-only; FOXAI itself was not modified, run, or deployed).

This report is precise about what is retained verbatim, what was adapted,
and what is not reproduced.

## 1. Route and function mapping

| FOXAI (core/foxai_web.py) | Kayock Writer | Notes |
|---|---|---|
| `ERIC_POET_NARRATOR_PROFILE` (L466–590) | `app/voices.py` | Traits/strengths/titles verbatim. The four embedded copyrighted poems moved to the optional private add-on (`addons/private_eric_poet_narrator/`) instead of the default source; loading the pack restores the identical full prompt. |
| `ERIC_SHORT_FICTION_PROFILE` (L594–659) | `app/voices.py` | Verbatim (traits, strength rules, originality rules, source titles). |
| `SHORT_FICTION_ARCHETYPE_VOICE_PROFILES` (L661–828) | `app/voices.py` | Verbatim: Robin Hood, Zorro, Dracula, Sherlock Holmes. |
| `ADDITIONAL_POETRY_VOICE_PROFILES` / `POETRY_VOICE_PACK_V1` (L832–928) | `app/voices.py` | Verbatim: Poe, Beneath the Beats, Dust and Duty, The Forsaken Flame. |
| `_writer_voice_profile_id/_name`, `_writer_additional_voice_prompt`, `_STRENGTH_RULES`, `get_writer_voice_profile`, `build_writer_voice_prompt` (L849–1082) | `app/voices.py` | Ported with identical prompt structure; system prompts rebranded FOXAI→Kayock Writer. |
| `_poetry_chat` + `check/post` | `app/provider.py` | Hard-wired `127.0.0.1:8080` llama-server replaced by configurable OpenAI-compatible client (base URL, chat/health path, model name, API key, timeout). Same message/response semantics and `{'ok': False}` failure contract. |
| `kayock_writer_poetry_create` (L24937) | `app/poetry.py :: create` | Verbatim logic: poem/short_story types, all guidance fields, rhyme/rhythm maps, length guides, variation, voice-profile wiring, short-story mode override, separate title generation, provenance payload. |
| `_poetry_generate_title`, `_short_story_generate_title`, `_poetry_clean_title`, `_poetry_fallback_title` (L24847–24933) | `app/poetry.py` | Verbatim. |
| `kayock_writer_poetry_polish` (L25250) | `app/poetry.py :: polish` | Verbatim: per-focus change rules and temperatures for poem and story, protected-guidance block, token budget, `story_change_metrics` retry (unchanged-output rejection after 2 attempts). |
| `kayock_writer_poetry_revise_selection` + `_poetry_selection_alternatives` + `_poetry_compact_voice_prompt` (L25861–26210) | `app/poetry.py :: revise_selection` | Verbatim: exact-position verification with whitespace recovery, context lines, three-alternative parsing, scope/length rejection rules, compact voice guide. |
| `kayock_writer_poetry_save` (L26270) | `app/poetry.py :: save` | Verbatim front-matter schema (title/author/copyright/version/version_group/content_sha256/prompt_fields…), dedup for polished stories, folder layout. |
| `kayock_writer_poetry_archive`, `_poetry_parse_markdown`, recordings, `_poetry_legacy_update` (L26492–26827) | `app/poetry.py` | Verbatim archive grouping, `voices that carry home` first-Eric-voice handling, legacy/for_akaysha/for_nevaeh manifest, recordings README/slots. `os.startfile` → cross-platform, config-gated `allow_folder_open` (falls back to returning the path). |
| `kayock_writer_weaver_generate/save` (L25521–25858) | `app/weaver.py` | Verbatim: 2–4 sources, 60k-char cap, 4 modes, 4 output types incl. Twine, planner JSON stage, annotation-contamination retry, copy metrics and warnings, no-overwrite saving (`.twee` + sidecar JSON for Twine). |
| `novel_root/novel_path/novel_md_path`, `list/read/save/duplicate/rename/delete_universe`, `export_story_bible` (L14472–14663) | `app/novelforge.py` | Verbatim schema (`version 0.1`, Markdown mirror, exports JSON+MD+TXT). Additive: unknown keys in existing universe files now survive a re-save (FOXAI dropped them). |
| Story Forge gates/actions (L26912–36660): `story_forge_report`, `manifest_preview`, `create_project_gate/action`, project dashboards, chapter planner/save, chapter editor + edit gate/action + audits, draft workspace/save/continue/history/compare/refresh, real-prose draft/save/editor/compare, chapter-prose continue | `app/storyforge.py` | **Generalized reimplementation** (see §3): same workflow stages, file formats (`kayock.writer.project.v1` manifest, `kayock.writer.chapter_preview_set.v1`, chapter-card markdown incl. handoff tags JSON, continuity handoffs), same gate→phrase→action pattern, backups before overwrite, reports as JSON receipts. |
| FOXAI HTML sections `poetrystudio`, `poemarchive`, `storyforge`, `novelforge`, `kayockwriter`, `weaver`, `mywriting` + `KAYOCK_WRITER_CALM_HOME_V1_JS` | `app/ui.py` | **Rewritten as one upgraded SPA** with a navigation tree; all fields/options preserved (see §2). |
| `/api/writer/*`, `/api/novelforge/*` routes (L13588+, L13661+) | `app/server.py` | Same route names for poetry/weaver/novelforge. Story Forge routes consolidated (see §3). |

## 2. UI feature coverage (upgraded interface)

Preserved from FOXAI's writer UI: guided creator fields (theme, emotion,
imagery, speaker, personal memory, audience, canon, opening line, variation),
17-option voice select (10 profiles + 6 generic craft voices), voice-strength
select populated per profile with read-only source-title chips, poem-only
craft controls (form, rhyme preference with 6 FOXAI options, rhythm with 5
options), story-length guidance, polisher with all poem/story focus presets
and keep-original/use-polished/save-both, Selected Lines & Stanza Workshop
with `Create 3 Alternatives`, archive with search/filter/version groups/
read-back/recordings/legacy flags, Novel Forge with card builders and story
bible export, Weaver with 4 sources and format help.

**Upgrades:** left navigation tree grouping all forges; Writer Home task
dashboard; My Writing merges poems and stories; Story Forge generalized to
any project; live model-endpoint settings page; responsive layout
(sidebar collapses to a hamburger under 900 px); no-login LAN access.

## 3. Story Forge: what changed and why

FOXAI's Story Forge (≈9,700 lines) is a report/receipt-oriented workflow
hard-wired to the flagship "Slipping into Darkness" project, with each
operation split into gate → preview → action endpoints that emit large
milestone-branded payloads. The standalone app reimplements the same
workflow, generalized:

**Preserved:** approval phrases (`CREATE STORY PROJECT`, `SAVE CHAPTER
CARDS`, `APPROVE CHAPTER EDIT`, `APPROVE PROSE EDIT`), no-write gates and
preflight with overwrite-risk detection, manifest schema
`kayock.writer.project.v1` (books with outline seeds, handoff points, safety
contract), chapter preview-set JSON + per-chapter markdown cards with the
identical section layout (Goal/Conflict/Reveal/Hook/Continuity
Notes/Handoff Tags/Draft Space/Safety), continuity handoff markdown with the
same per-chapter field list, chapter editing with exact diff metrics and
backup-before-overwrite, versioned drafts with SHA-256 manifest and
word-growth checks on continuation, prose versions with identical-save
rejection and diff verification, JSON action receipts under
`Reports/KayockWriter/`.

**Changed:** works for any project (not only the flagship); books are
user-defined instead of seeded with Anthony/Kayock/Jokaya placeholder
content; the 28 report endpoints are consolidated into 17 working routes
plus read endpoints; report payloads keep the operative fields (ok, status,
blockers, preflight, overwrite risks, created/written files, backups,
diff metrics, safety) but drop FOXAI's milestone marketing text and
legacy-copy import machinery (no `Z:\FOXAI` source to import from).

## 4. Not reproduced / intentionally omitted

1. **Embedded Eric poems in default code** — moved to the private add-on per
   the handoff rules. Loading the pack restores the identical prompt; without
   it the Eric — Poet/Narrator prompt uses derived traits only.
2. **FOXAI non-writer subsystems** (excluded per handoff rule 5): Artificial
   Minds model launcher/engine management, ComfyUI integration, Fleet,
   Kayock's Study/Bibliotheca library, mission-image/vision pipeline,
   professors, web-engineer/repair bay, extension manager, sentry, scan
   bridge, restore/rollback machinery, PDF library indexing.
3. **Story Forge legacy import** — the "copy legacy NovelForge files into
   `Source/`" step needs the FOXAI tree; skipped. Import universes manually
   (see INSTALL.md §5).
4. **Report-only/audit endpoints** — FOXAI's self-test reports
   (`chapter_edit_gate_diff_selftest`, `chapter_edit_direct_diff_proof`,
   audit-reader) were verification scaffolding for FOXAI development; their
   substance (diff verification, audit receipts) lives inside the working
   edit flow. Not exposed as separate pages.
5. **`os.startfile` behaviors** — replaced with a config-gated, cross-platform
   opener that degrades gracefully on headless servers.
6. **The Weaver is FOXAI's (retained) but the flagship-demo framing**
   ("Kayock Command OS" branding, USB-drive assumptions) is replaced by the
   app-owned data dir.
7. **Multi-user/auth** — FOXAI had none; Kayock Writer adds none. LAN access
   is trust-based (documented).

## 5. Improvements over FOXAI

- Configurable model endpoint (any OpenAI-compatible server) with live
  settings and health probe; no hard-coded `127.0.0.1:8080`.
- App-owned, relocatable data dir; no `Z:\FOXAI` or drive-root assumptions.
- Short stories now appear in the archive ("Browse My Writing") — FOXAI
  saved them to a folder its archive never scanned.
- Novel Forge structured card keys survive re-save.
- Draft/prose saves never overwrite; edits always back up first.
- 53-test suite + offline self-verification, with a bundled mock model
  endpoint (FOXAI's VERIFY script checked hashes; these tests exercise the
  actual workflows).

## 6. Verification summary

- `python tests/verify_kayock_writer.py` — 18/18 checks (compile, profiles,
  no bundled poems, prompt builders, UI markers, config defaults, traversal
  guard).
- `python tests/run_tests.py` — 53/53 passing: voice profiles, private-pack
  import, poetry create/polish/selection/save/archive/legacy, weaver
  (incl. contamination retry), Novel Forge CRUD/export/traversal, Story Forge
  gates/actions/edits/drafts/prose/dashboards, config precedence, provider
  offline/online, HTTP route smoke tests, 0.0.0.0 LAN binding, endpoint
  reconfiguration.
- Live E2E run: app served on LAN, poem created and saved through the UI
  with the Eric — Poet/Narrator profile, archive round-trip, story project
  created, chapter cards saved, story bible exported, weaver output saved.
