# Private voice pack — Eric — Poet/Narrator

## Why this exists

FOXAI's `ERIC_POET_NARRATOR_PROFILE` embedded four complete copyrighted
poems as read-only style references for the model. Those texts are **not**
part of Kayock Writer's default source code. The profile ships with its
derived style settings (traits, strength rules, originality rules, source
titles), which works, but the original full-experience prompt — where the
model also sees the actual poems as evidence of the writer's voice — needs
the private texts.

This add-on restores that experience locally.

## How to install

The app automatically loads the pack from either location at startup:

1. `<data_dir>/voice_packs/eric_poet_narrator_private.json` (recommended —
   survives app updates), or
2. `addons/private_eric_poet_narrator/eric_poet_narrator_private.json`
   (only in the **separately supplied private add-on**, not public GitHub).

Verify after restarting the app: **Writer Home → Eric private voice pack**
shows `loaded (4 source poems)`, or `GET /api/voice/pack/status`.

To remove it (reverting to derived-settings-only), delete the file and
restart.

## Where the poems came from

`ERIC_POET_NARRATOR_PROFILE` in `core/foxai_web.py` (FOXAI, commit
`b510e5c38c0a1fa41f61b6c65e74ce1812f1ecdb`):

- *Eternity*
- *The City Of Sorrows* (© 2002, Writing.Com: kayock)
- *The Vampire Lestat*
- *The Soliloquy of 2002* (© 2003 by Eric Z. Fox)

## Redistribution rules

- The poems are copyrighted works of Eric Z. Fox. **Do not publish, share,
  upload, or commit this JSON file.** It exists only for the author's own
  local installation.
- If you distribute Kayock Writer to someone else, delete
  `addons/private_eric_poet_narrator/eric_poet_narrator_private.json` from
  the copy first. Without it, the app still runs fully — the Eric profile
  simply uses derived style settings.
- When enabled, the private source poems are included in prompts sent to **the configured model endpoint**. Only select a model endpoint that you trust with these private texts; a cloud-hosted endpoint receives the poems over the network.
