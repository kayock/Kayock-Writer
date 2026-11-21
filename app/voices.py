"""Kayock Writer voice profiles — ported from FOXAI.

Ported from core/foxai_web.py markers ERIC_POET_NARRATOR_PROFILE_V1 (lines
466–1083), FOXAI_SHORT_STORY_POLISHER_V1_PROFILE, POETRY_VOICE_PACK_V1 and
the companion selector/prompt functions. The prompt-composition code keeps
FOXAI's exact structure so downstream model behavior matches.

Private Eric poems: FOXAI embedded four complete copyrighted poems inside
ERIC_POET_NARRATOR_PROFILE. Those texts are NOT bundled in this source file.
The profile ships with its derived style settings (traits, strength rules,
originality rules, source titles). To restore the full original prompt —
where the model sees the actual poems as read-only style evidence — place a
private voice pack (see docs/PRIVATE_VOICE_PACK.md) in:

    <data_dir>/voice_packs/eric_poet_narrator_private.json
or  addons/private_eric_poet_narrator/eric_poet_narrator_private.json

and it is merged at import time. Without the pack everything still works;
the prompt simply omits the protected poem texts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# ERIC_POET_NARRATOR_PROFILE_V1_START (derived settings; poem texts moved to
# the optional private voice pack — see module docstring).

ERIC_POET_NARRATOR_PROFILE = {
    "id": "eric_poet_narrator",
    "name": "Eric — Poet/Narrator",
    "author": "Eric Z. Fox",
    "kind": "read_only_style_reference",
    "originals_modified": False,
    "source_titles": [
        "Eternity",
        "The City Of Sorrows",
        "The Vampire Lestat",
        "The Soliloquy of 2002",
    ],
    "traits": [
        "direct emotional declaration rather than detached description",
        "frequent rhyme and near-rhyme used as forward momentum",
        "mythic, cosmic, historical, religious, or supernatural framing",
        "plainspoken lines beside unusual dreamlike phrases",
        "love, mortality, injustice, faith, darkness, endurance, and hope",
        "strong concluding couplets or final declarations",
        "willingness to keep rough edges when they carry the writer's identity",
    ],
    "sources": [],
}

# FOXAI_SHORT_STORY_POLISHER_V1_PROFILE_START

ERIC_SHORT_FICTION_PROFILE = {'id': 'eric_short_fiction',
 'name': 'Eric — Short Fiction',
 'author': 'Eric Z. Fox',
 'kind': 'read_only_source_derived_craft_fingerprint',
 'default_strength': 'Recognizably Eric — Prose',
 'originals_modified': False,
 'source_files_embedded': False,
 'source_files_moved': False,
 'source_titles': ['God and Fred English',
                   'The Darkness',
                   'You',
                   'I Met Him Once',
                   'Could It Get Worse?',
                   'A Stiffy',
                   'Something Vicious',
                   'From Above',
                   'When a Man Loves a Woman',
                   'The Man Beneath His Feet',
                   'Via Dolorosa',
                   'The Last President'],
 'secondary_reference_titles': ['A Crusader Without a Crusade — long-form secondary reference',
                                'Roanoke — Slipping into Darkness excerpt; secondary reference '
                                'only'],
 'traits': ['ordinary people or familiar places interrupted by supernatural, cosmic, violent, or '
            'morally impossible events',
            'plainspoken narration that can pivot quickly into horror, grief, wonder, dark humor, '
            'or philosophical argument',
            'emotion stated directly rather than hidden behind detached literary distance',
            'strong first-person or close-narrator presence, including confessions, testimony, '
            'dialogue, and framed accounts',
            'specific physical details used to make the strange feel immediate and bodily',
            'religion, mortality, love, guilt, sacrifice, injustice, fate, and the unknowable '
            'treated as lived pressures',
            'short scenes that move efficiently toward a reversal, revelation, consequence, or '
            'final sting',
            'endings that reframe what came before through irony, horror, tenderness, '
            'newspaper-like distance, or one last declaration',
            'rough edges and unconventional phrasing preserved when they carry personality, '
            'urgency, or spoken rhythm'],
 'strength_rules': {'light prose influence': 'Use only a light Eric prose influence: direct '
                                             'feeling, one concrete strange detail, efficient '
                                             'movement, and an ending with consequence. Preserve '
                                             "the operator's own diction.",
                    'recognizably eric — prose': 'Use a recognizable Eric short-fiction voice: '
                                                 'plainspoken emotional urgency, ordinary life '
                                                 'touching the supernatural or morally impossible, '
                                                 'vivid bodily or environmental detail, dark humor '
                                                 'or tenderness where natural, and an earned final '
                                                 'turn.',
                    'full eric story voice': 'Use the full source-derived craft fingerprint: '
                                             'intimate or declarative narration, fast pressure, '
                                             'religious or cosmic questions when relevant, '
                                             'visceral detail, contradiction, dark humor, grief, '
                                             'love, moral consequence, and a memorable final '
                                             'sting. Do not copy source wording or plots.'},
 'originality_rules': ['Do not quote, paraphrase, continue, retell, or remix any source story.',
                       'Do not reuse a source title, named character, exact situation, signature '
                       'reveal, final line, or plot mechanism.',
                       'Treat A Crusader Without a Crusade and Roanoke only as broad long-form '
                       'secondary evidence; do not import their lore.',
                       "The operator's submitted story, prompt facts, canon, characters, and "
                       'intended ending remain the primary authority.',
                       "Keep Eric's original desktop files read-only and external; no source text "
                       'is embedded in this profile.']}

SHORT_FICTION_ARCHETYPE_VOICE_PROFILES = {'robin_hood_merry_outlaw': {'id': 'robin_hood_merry_outlaw',
                             'name': 'Robin Hood — The Merry Outlaw',
                             'kind': 'public_domain_folklore_archetype',
                             'author': 'Public-domain folklore tradition',
                             'default_strength': 'The Greenwood Oath',
                             'source_titles': ['Robin Hood ballad and folklore tradition'],
                             'traits': ['cheerful defiance against unjust power, especially when hunger and '
                                        'dignity are at stake',
                                        'warm fellowship, teasing wit, practical courage, and loyalty to '
                                        'ordinary people',
                                        'clear moral contrast without making every wealthy person a '
                                        'caricature',
                                        'forest paths, market roads, hidden camps, shared meals, rain, oak, '
                                        'bowstring, and disguise',
                                        "quick dialogue, confident movement, and a storyteller's sense of "
                                        'adventure',
                                        'generosity presented as action, risk, and responsibility rather '
                                        'than empty virtue',
                                        'an ending that restores dignity, exposes hypocrisy, or turns '
                                        "authority's rules against itself"],
                             'strength_rules': {'greenwood whisper': 'Use a light folklore influence: humane '
                                                                     'wit, grounded injustice, fellowship, '
                                                                     'and one woodland or road image.',
                                                'the greenwood oath': 'Balance merry confidence, social '
                                                                      'conscience, clever action, loyal '
                                                                      'companions, hunger, dignity, and an '
                                                                      'earned reversal.',
                                                'merry outlaw full force': 'Use full outlaw energy: bold '
                                                                           'banter, disguise or strategy, '
                                                                           'communal stakes, swift '
                                                                           'adventure, moral clarity, and a '
                                                                           'satisfying turn against abuse of '
                                                                           'power.'},
                             'originality_rules': ['Do not reproduce a ballad, film scene, television '
                                                   'version, catchphrase, costume design, or copyrighted '
                                                   'adaptation.',
                                                   'Do not automatically use famous companion names, royal '
                                                   'figures, tournaments, or signature rescues unless the '
                                                   'operator requests them.',
                                                   'Create a new conflict, setting details, dialogue, '
                                                   'strategy, and ending.']},
 'zorro_masked_fox': {'id': 'zorro_masked_fox',
                      'name': 'Zorro — The Masked Fox',
                      'kind': 'public_domain_literary_archetype',
                      'author': 'Public-domain masked-avenger tradition',
                      'default_strength': "The Fox's Flourish",
                      'source_titles': ['Early public-domain masked-fox literary tradition'],
                      'traits': ['elegant resistance to corrupt authority through speed, wit, theater, and '
                                 'precision',
                                 'a public mask and private identity creating tension, sacrifice, and '
                                 'dramatic irony',
                                 'courtesy toward the vulnerable paired with mockery of bullies and '
                                 'officials',
                                 'moonlit courtyards, dust, horses, rooftops, blades, capes, bells, '
                                 'balconies, and secret passages',
                                 'economical action choreography that remains readable rather than becoming '
                                 'a list of moves',
                                 'victory through intelligence and timing more often than brute force',
                                 'a final flourish, clue, mark, or disappearance that leaves injustice '
                                 'embarrassed'],
                      'strength_rules': {'masked shadow': 'Use a light masked-avenger influence: restraint, '
                                                          'one clever reversal, precise movement, and quiet '
                                                          'concern for the oppressed.',
                                         "the fox's flourish": 'Balance elegant action, playful confidence, '
                                                               'dual identity, social justice, and a '
                                                               'theatrical but earned ending.',
                                         'midnight fox full force': 'Use full swashbuckling energy: rapid '
                                                                    'strategy, sharp dialogue, moonlit '
                                                                    'movement, corrupt power exposed, and a '
                                                                    'memorable disappearance or final '
                                                                    'flourish.'},
                      'originality_rules': ['Do not reproduce protected adaptation dialogue, visual '
                                            'trademarks, scene choreography, supporting casts, or signature '
                                            'branding.',
                                            'Do not default to a famous hacienda, commandant, love interest, '
                                            'costume description, or letter-marking scene.',
                                            'Create an original masked defender, conflict, locale, action '
                                            'sequence, and resolution when not using the named folklore '
                                            'archetype directly.']},
 'dracula_ancient_count': {'id': 'dracula_ancient_count',
                           'name': 'Dracula — The Ancient Count',
                           'kind': 'public_domain_gothic_archetype',
                           'author': 'Public-domain Dracula and vampire tradition',
                           'default_strength': "The Count's Invitation",
                           'source_titles': ['Dracula (1897)', 'Public-domain vampire folklore'],
                           'traits': ['old-world courtesy that carries predation, command, loneliness, and '
                                      'concealed threat',
                                      'immortality measured through vanished empires, dead languages, '
                                      'bloodlines, ruins, and remembered wars',
                                      'formal diction sharpened by intimate sensory attention and sudden '
                                      'cruelty',
                                      'thresholds, invitations, moonlit stone, candlelight, wolves, storms, '
                                      'mirrors, blood, and sealed rooms',
                                      'seduction and terror kept psychologically legible rather than reduced '
                                      'to decorative gothic language',
                                      'a speaker who may admire humanity while treating it as prey, '
                                      'inheritance, or forbidden companionship',
                                      'an ending that closes a bargain, reveals the cost of welcome, or lets '
                                      'ancient patience triumph'],
                           'strength_rules': {'candlelit courtesy': 'Use a light ancient-vampire influence: '
                                                                    'formal hospitality, restrained menace, '
                                                                    'sensory detail, and a hint of long '
                                                                    'memory.',
                                              "the count's invitation": 'Balance aristocratic control, '
                                                                        'predatory intimacy, history, '
                                                                        'loneliness, threshold imagery, and '
                                                                        'an ominous earned turn.',
                                              'ancient hunger full force': 'Use full gothic intensity: '
                                                                           'centuries of memory, elegant '
                                                                           'threat, blood and invitation '
                                                                           'symbolism, psychological '
                                                                           'seduction, command, and a final '
                                                                           'cost.'},
                           'originality_rules': ['Do not copy or closely paraphrase Dracula, its letters, '
                                                 'diary entries, famous speeches, scenes, or adaptation '
                                                 'dialogue.',
                                                 "Do not automatically reproduce the novel's plot, castle "
                                                 'journey, supporting characters, or iconic transformation '
                                                 'scenes.',
                                                 'Create original circumstances, imagery, conflict, '
                                                 'relationships, and ending.']},
 'sherlock_holmes_consulting_mind': {'id': 'sherlock_holmes_consulting_mind',
                                     'name': 'Sherlock Holmes — The Consulting Mind',
                                     'kind': 'public_domain_detective_archetype',
                                     'author': 'Public-domain consulting-detective tradition',
                                     'default_strength': 'The Consulting Method',
                                     'source_titles': ['Public-domain Sherlock Holmes stories'],
                                     'traits': ['close observation converted into testable inference rather '
                                                'than unexplained genius',
                                                'precise, economical diction with dry wit and impatience '
                                                'toward lazy assumptions',
                                                'small material clues—mud, ash, thread, ink, posture, '
                                                'timing, weather, wear, and absence—carrying the case',
                                                'a companion or client perspective that keeps deduction '
                                                'human and understandable',
                                                'hypotheses revised when evidence contradicts them',
                                                'mystery structure built around motive, opportunity, method, '
                                                'and the detail everyone dismissed',
                                                'an ending that explains the chain of reasoning while '
                                                'preserving one final human or moral complication'],
                                     'strength_rules': {'observant glance': 'Use a light '
                                                                            'consulting-detective influence: '
                                                                            'two or three concrete '
                                                                            'observations, cautious '
                                                                            'inference, and restrained dry '
                                                                            'wit.',
                                                        'the consulting method': 'Balance readable '
                                                                                 'deduction, physical '
                                                                                 'evidence, competing '
                                                                                 'hypotheses, character '
                                                                                 'insight, and a clear but '
                                                                                 'not effortless solution.',
                                                        'the game in full force': 'Use full analytical '
                                                                                  'energy: layered '
                                                                                  'observations, disciplined '
                                                                                  'elimination, rapid '
                                                                                  'dialogue, intellectual '
                                                                                  'tension, and an '
                                                                                  'explanation that makes '
                                                                                  'every clue feel fair.'},
                                     'originality_rules': ['Do not reproduce a canonical case, client, '
                                                           'villain, address, catchphrase, disguise, '
                                                           'deduction sequence, or adaptation-specific '
                                                           'behavior.',
                                                           'Do not make deduction magical; show enough '
                                                           'evidence for the reader to follow the reasoning.',
                                                           'Create an original mystery, clues, suspects, '
                                                           'motive, method, dialogue, and solution.']}}

# FOXAI_SHORT_STORY_POLISHER_V1_PROFILE_END

# POETRY_VOICE_PACK_V1_START

ADDITIONAL_POETRY_VOICE_PROFILES = {'edgar_allan_poe_gothic_lyric': {'id': 'edgar_allan_poe_gothic_lyric', 'name': 'Edgar Allan Poe — Gothic Lyric', 'kind': 'public_domain_style_reference', 'author': 'Public-domain literary tradition', 'default_strength': 'Gothic Lyric', 'source_titles': ['The Raven', 'Annabel Lee', 'The Bells', 'Alone', 'The Haunted Palace'], 'traits': ['musical cadence shaped by internal rhyme, alliteration, and refrain', 'grief, memory, obsession, dream, dread, beauty, and mortality', 'ornate language balanced by a clear emotional center', 'gothic rooms, storms, bells, moonlight, shadows, tombs, and thresholds', 'a dramatic speaker whose certainty may be wounded or unreliable', 'sound patterns that intensify rather than merely decorate', 'an ending that closes like a door, tolling bell, or final revelation'], 'strength_rules': {'candlelit influence': 'Use a light gothic influence: musical phrasing, shadowed imagery, and restrained melancholy. Keep the language accessible.', 'gothic lyric': 'Use a clear gothic lyric voice: deliberate sound, internal rhyme when natural, haunted beauty, emotional obsession, and a memorable refrain or closing image.', 'midnight full force': 'Use full gothic intensity: incantatory cadence, layered sound, dramatic atmosphere, psychological dread, tragic beauty, and a powerful final turn. Avoid empty purple prose.'}, 'originality_rules': ['Do not reproduce or closely paraphrase a famous line, refrain, title, or plot.', 'Do not insert a raven, Lenore-like beloved, telltale heart, or other signature device unless the operator independently requests it.', 'Create a new speaker, situation, imagery sequence, rhyme design, and ending.']}, 'beneath_the_beats_west_coast_voice': {'id': 'beneath_the_beats_west_coast_voice', 'name': 'Beneath the Beats — West Coast Voice', 'kind': 'original_trait_composite', 'author': 'Original FOXAI craft profile', 'default_strength': 'Truth & Defiance', 'source_titles': [], 'traits': ['plainspoken emotional truth that sounds natural when read aloud', 'family, loyalty, abandonment, poverty, injustice, survival, responsibility, and hope', 'controlled anger beside vulnerability, humor, tenderness, and self-examination', 'strong internal rhyme, conversational cadence, and flexible line length', 'cinematic street-level scenes built from specific physical details', 'compact turns of phrase that carry consequence without decorative filler', 'a closing statement that feels earned rather than inspirational by default'], 'strength_rules': {'light west coast influence': 'Use a light spoken-word influence: direct language, natural cadence, one or two internal rhymes, and grounded emotional honesty.', 'truth & defiance': 'Balance vulnerability and resistance. Use conversational rhythm, internal rhyme, concrete social reality, loyalty, contradiction, and a forceful but human conclusion.', 'full spoken-word force': 'Use full performance energy: layered internal rhyme, sharp scene changes, controlled anger, dark humor, confession, social pressure, and lines designed to strike when spoken aloud.'}, 'originality_rules': ['Do not quote, remix, paraphrase, or continue any copyrighted poem or lyric.', 'Do not imitate or name a specific rapper, performer, song, album, persona, or signature phrase.', 'Use wholly original wording, scenes, rhyme patterns, arguments, and endings.']}, 'dust_and_duty_last_gunslinger': {'id': 'dust_and_duty_last_gunslinger', 'name': 'Dust and Duty — Last Gunslinger Voice', 'kind': 'original_fictional_archetype', 'author': 'Original FOXAI fictional archetype', 'default_strength': 'The Gunslinger’s Oath', 'source_titles': [], 'traits': ['spare deliberate language spoken by a traveler who has survived too much', 'duty, old promises, found family, sacrifice, guilt, endurance, and unfinished roads', 'old-west frontier imagery joined to fantasy ruins and failing science-fiction machinery', 'strange stars, empty stations, worn weapons, broken radios, dry towns, and impossible horizons', 'campfire stew in a blackened iron pot, tin cups, quiet fellowship, and making sure everyone eats', 'grief carried through action and silence rather than long explanation', 'small moments of tenderness from someone trained to keep walking'], 'strength_rules': {'quiet resolve': 'Use restrained frontier language, one strong image at a time, quiet loyalty, and grief shown through action.', 'the gunslinger’s oath': 'Balance old vows, frontier fantasy, ruined technology, found family, campfire fellowship, and the cost of completing the road.', 'last road, full force': 'Use the full dying-world atmosphere: severe cadence, strange stars, ancient duty, broken machines, remembered companions, hard choices, and tenderness hidden beneath iron resolve.'}, 'originality_rules': ['Do not use protected character names, place names, cosmology, catchphrases, artifacts, recipes, or franchise terminology.', 'Do not recreate a scene or plot from an existing western, fantasy, or science-fiction work.', 'Build a wholly original traveler, road, world, fellowship, meal, mission, and ending.']}, 'the_forsaken_flame_exiles_voice': {'id': 'the_forsaken_flame_exiles_voice', 'name': 'The Forsaken Flame — Exile’s Voice', 'kind': 'public_domain_character_tradition', 'author': 'Public-domain Frankenstein tradition', 'default_strength': 'Beautiful and Unwanted', 'source_titles': ['Frankenstein; or, The Modern Prometheus (1818)'], 'traits': ['eloquent intelligence formed in isolation and sharpened by rejection', 'a desperate wish to be seen, taught, loved, named, and answered', 'tender observation of ordinary human warmth from outside the window', 'abandonment, judgment, responsibility, identity, rage, remorse, and moral contradiction', 'beautiful formal language that can turn suddenly raw and accusatory', 'the question of whether cruelty is born, made, chosen, or imposed', 'fire as warmth, knowledge, creation, pain, destruction, and surviving light'], 'strength_rules': {'lonely wanderer': 'Use restrained eloquence, solitude, wonder, and a quiet wish for human recognition. Keep anger beneath the surface.', 'beautiful and unwanted': 'Balance intellectual beauty, tenderness, abandonment, accusation, self-questioning, and the pain of being judged before being known.', 'forsaken flame': 'Use full tragic intensity: formal eloquence, moral argument, longing, rage, remorse, fire imagery, creator-and-created tension, and an ending that leaves both speaker and listener implicated.'}, 'originality_rules': ['Do not copy or closely paraphrase passages from Frankenstein.', 'Do not simply retell the creature’s biography or reproduce its plot.', 'Create a new exile, circumstances, imagery sequence, conflict, and conclusion.']}}

POETRY_VOICE_PROFILES = {
    "eric_poet_narrator": ERIC_POET_NARRATOR_PROFILE,
    "eric_short_fiction": ERIC_SHORT_FICTION_PROFILE,
    **ADDITIONAL_POETRY_VOICE_PROFILES,
    **SHORT_FICTION_ARCHETYPE_VOICE_PROFILES,
}

POETRY_VOICE_NAME_TO_ID = {
    profile["name"].strip().casefold(): profile_id
    for profile_id, profile in POETRY_VOICE_PROFILES.items()
}

# POETRY_VOICE_PACK_V1_END


# --------------------------------------------------------------------------
# Private voice-pack import (optional).
#
# A pack is a JSON file shaped like:
#   {"id": "eric_poet_narrator", "sources": [{"title": ..., "author": ...,
#                                             "text": ...}, ...],
#    "private": true}
# Only the Eric Poet/Narrator profile accepts sources. Pack contents stay on
# the machine that imports them; nothing is transmitted anywhere.
# --------------------------------------------------------------------------

PRIVATE_PACK_FILENAMES = ("eric_poet_narrator_private.json",)


def _pack_candidates(data_dir: Path | None) -> List[Path]:
    here = Path(__file__).resolve().parent.parent
    dirs = []
    if data_dir:
        dirs.append(Path(data_dir) / "voice_packs")
    dirs.append(here / "addons" / "private_eric_poet_narrator")
    out = []
    for directory in dirs:
        for name in PRIVATE_PACK_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                out.append(candidate)
    return out


def apply_private_voice_pack(data_dir: Path | None = None) -> Dict[str, Any]:
    """Merge a private Eric voice pack if one is present. Returns status."""
    candidates = _pack_candidates(data_dir)
    if not candidates:
        return {"ok": True, "loaded": False,
                "message": "No private voice pack installed; the Eric "
                           "Poet/Narrator profile uses derived style settings only."}
    path = candidates[0]
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "loaded": False, "message": f"Private voice pack unreadable: {exc}"}
    if str(pack.get("id") or "") != "eric_poet_narrator":
        return {"ok": False, "loaded": False,
                "message": "Private voice pack has the wrong profile id."}
    sources = pack.get("sources")
    if not isinstance(sources, list) or not sources:
        return {"ok": False, "loaded": False,
                "message": "Private voice pack contains no source poems."}
    cleaned = []
    for item in sources:
        if isinstance(item, dict) and str(item.get("text") or "").strip():
            cleaned.append({
                "title": str(item.get("title") or "Untitled"),
                "author": str(item.get("author") or pack.get("author") or "Eric Z. Fox"),
                "text": str(item.get("text")),
            })
    ERIC_POET_NARRATOR_PROFILE["sources"] = cleaned
    if isinstance(pack.get("copyright_notice"), str):
        ERIC_POET_NARRATOR_PROFILE["copyright_notice"] = pack["copyright_notice"]
    return {"ok": True, "loaded": True, "path": str(path),
            "sources": len(cleaned),
            "message": f"Private voice pack loaded ({len(cleaned)} source poems, "
                       "read-only style references)."}


def private_pack_status() -> Dict[str, Any]:
    return {
        "loaded": bool(ERIC_POET_NARRATOR_PROFILE.get("sources")),
        "source_count": len(ERIC_POET_NARRATOR_PROFILE.get("sources") or []),
        "profile_id": "eric_poet_narrator",
    }


# --------------------------------------------------------------------------
# Voice selection and prompt composition (ported; FOXAI semantics kept).
# --------------------------------------------------------------------------

def _writer_voice_profile_id(voice: str = "") -> str:
    return POETRY_VOICE_NAME_TO_ID.get(
        str(voice or "").strip().casefold(),
        "",
    )


def _writer_voice_profile_name(profile_id: str = "") -> str:
    profile = POETRY_VOICE_PROFILES.get(str(profile_id or "").strip())
    return str(profile.get("name") or "") if profile else ""


def _writer_additional_voice_prompt(
    profile: dict,
    strength: str,
    writing_type: str = "poem",
) -> str:
    strength_rules = profile.get("strength_rules") or {}
    strength_key = str(strength or "").strip().casefold()
    strength_rule = strength_rules.get(strength_key)
    if not strength_rule:
        default_key = str(
            profile.get("default_strength") or ""
        ).strip().casefold()
        strength_rule = strength_rules.get(
            default_key,
            "Use the profile traits with restraint and keep all writing original.",
        )

    traits = "\n".join(
        f"- {item}"
        for item in profile.get("traits") or []
    )
    originality = "\n".join(
        f"- {item}"
        for item in profile.get("originality_rules") or []
    )
    titles = profile.get("source_titles") or []
    source_note = (
        "\nReference tradition or titles:\n"
        + "\n".join(f"- {title}" for title in titles)
        if titles else
        "\nNo copyrighted source text is stored in this profile."
    )
    is_story = str(writing_type or "").strip().casefold() == "short_story"
    work_kind = "short fiction" if is_story else "poetry"
    format_rule = (
        "Keep the result in readable prose paragraphs. Do not introduce verse, "
        "rhyme, meter, stanza, refrain, or line-break requirements."
        if is_story else
        "Keep the result a new poem rather than a parody, pastiche exercise, or sequel."
    )

    return f"""
{profile.get("name","WRITER VOICE PROFILE").upper()}
Profile kind: {profile.get("kind","creative_profile")}
Strength: {strength or profile.get("default_strength","balanced")}
Writing type: {work_kind}

Purpose:
Create or revise wholly new {work_kind} guided by broad craft traits. The
operator's theme, emotion, imagery, opening line, submitted text, and canon
remain the primary authority.

Voice fingerprint:
{traits}

Strength instruction:
{strength_rule}

Originality and boundary rules:
{originality}
- Never reproduce a recognizable passage from another work.
- Never allow the profile to override the operator's meaning, lived experience,
  characters, canon, point of view, or intended ending.
- {format_rule}
{source_note}
""".strip()


_STRENGTH_RULES = {
    "light influence": (
        "Use only a light influence: emotional directness, purposeful cadence, "
        "and a decisive ending. Do not borrow the source poems' vocabulary, "
        "images, situations, rhyme pairs, titles, or line structures."
    ),
    "recognizably eric": (
        "Make the new poem recognizably Eric-like through direct emotion, "
        "rhyme or near-rhyme when natural, mythic or spiritual scale, unusual "
        "plainspoken images, and a strong concluding declaration. Keep all "
        "subject matter and wording original."
    ),
    "strong eric voice": (
        "Use a strong Eric voice: emotionally declarative lines, energetic "
        "rhyme, cosmic or historical reach, moral or spiritual tension, "
        "unusual phrases that remain understandable, and a memorable final "
        "couplet or declaration. Do not copy any distinctive source wording."
    ),
}


def get_writer_voice_profile(
    profile_id: str = "eric_poet_narrator",
) -> Optional[dict]:
    profile = POETRY_VOICE_PROFILES.get(
        str(profile_id or "").strip(),
    )
    if profile is None:
        return None
    return json.loads(json.dumps(profile))


def build_writer_voice_prompt(
    profile_id: str,
    strength: str = "",
    writing_type: str = "poem",
) -> str:
    profile = get_writer_voice_profile(profile_id)
    if profile is None:
        return ""

    is_story = str(writing_type or "").strip().casefold() == "short_story"

    if profile_id == "eric_short_fiction":
        resolved_strength = strength or profile.get("default_strength") or "Recognizably Eric — Prose"
        strength_key = str(resolved_strength).strip().casefold()
        strength_rules = profile.get("strength_rules") or {}
        strength_rule = strength_rules.get(
            strength_key,
            strength_rules.get(
                "recognizably eric — prose",
                "Use the source-derived prose traits with restraint and preserve the operator's story.",
            ),
        )
        traits = "\n".join(f"- {item}" for item in profile.get("traits") or [])
        core_sources = "\n".join(f"- {item}" for item in profile.get("source_titles") or [])
        secondary_sources = "\n".join(
            f"- {item}" for item in profile.get("secondary_reference_titles") or []
        )
        originality = "\n".join(
            f"- {item}" for item in profile.get("originality_rules") or []
        )
        return f"""
ERIC — SHORT FICTION VOICE PROFILE
Author: Eric Z. Fox
Strength: {resolved_strength}
Profile kind: read-only source-derived craft fingerprint

Purpose:
Use broad craft tendencies derived from Eric's original prose to create or
polish new short fiction. No original story text is embedded here. The current
prompt or submitted story remains primary authority.

Voice fingerprint:
{traits}

Strength instruction:
{strength_rule}

Core source titles used only to derive traits:
{core_sources}

Secondary long-form references:
{secondary_sources}

Non-copying and preservation rules:
{originality}
- Keep the result as prose short fiction, not poetry.
- Never import a source story's wording, plot, character, lore, reveal, or ending.
- Preserve rough or unconventional phrasing when it carries Eric's identity.
""".strip()

    if profile_id != "eric_poet_narrator":
        return _writer_additional_voice_prompt(
            profile,
            strength or profile.get("default_strength") or "balanced",
            writing_type=writing_type,
        )

    resolved_strength = strength or "Recognizably Eric"
    strength_key = str(resolved_strength).strip().casefold()
    strength_rule = _STRENGTH_RULES.get(
        strength_key,
        _STRENGTH_RULES["recognizably eric"],
    )
    traits = "\n".join(f"- {item}" for item in profile["traits"])
    sources = "\n\n".join(
        (
            f"--- SOURCE: {source['title']} ---\n"
            f"{source['text'].strip()}"
        )
        for source in profile.get("sources") or []
    )
    work_kind = "short fiction prose" if is_story else "poetry"
    format_rule = (
        "Translate only broad emotional and narrative tendencies into prose. "
        "Do not force rhyme, stanzas, meter, or poetic line breaks."
        if is_story else
        "Keep the result a poem."
    )

    if not sources:
        # Private pack not installed: keep the identical non-copying rules but
        # omit the protected poems entirely. The prompt stays usable.
        return f"""
ERIC — POET/NARRATOR VOICE PROFILE
Author: Eric Z. Fox
Strength: {resolved_strength}
Writing type: {work_kind}

Purpose:
Create or revise new {work_kind} in Eric's voice from the craft fingerprint
below. The private read-only source poems are not installed in this profile
(see docs/PRIVATE_VOICE_PACK.md); use the derived traits only.

Voice fingerprint:
{traits}

Strength instruction:
{strength_rule}

Non-copying rules:
- Never reuse a complete source line.
- Never reuse six or more consecutive source words.
- Never reuse a source title, named character, signature image sequence,
  historical sequence, rhyme pair, or closing line unless the operator
  supplied it in the current work or opening line.
- Preserve rough or unconventional phrasing when it carries identity.
- New work must remain clearly new work, not a remix of a source poem.
- Do not correct or alter any source poem; they are read-only references.
- {format_rule}
""".strip()

    return f"""
ERIC — POET/NARRATOR VOICE PROFILE
Author: Eric Z. Fox
Strength: {resolved_strength}
Writing type: {work_kind}

Purpose:
Use the protected poems below only as evidence of the writer's tendencies.
Create or revise new {work_kind} in a compatible voice without reproducing a source.

Voice fingerprint:
{traits}

Strength instruction:
{strength_rule}

Non-copying rules:
- Never reuse a complete source line.
- Never reuse six or more consecutive source words.
- Never reuse a source title, named character, signature image sequence,
  historical sequence, rhyme pair, or closing line unless the operator
  supplied it in the current work or opening line.
- Preserve rough or unconventional phrasing when it carries identity.
- New work must remain clearly new work, not a remix of a source poem.
- Do not correct or alter any source poem; they are read-only references.
- {format_rule}

Protected read-only source poems:
{sources}
""".strip()


def poetry_compact_voice_prompt(
    profile_id: str,
    strength: str,
) -> str:
    """FOXAI _poetry_compact_voice_prompt — used by the Selection Workshop."""
    profile = get_writer_voice_profile(profile_id)
    if not profile:
        return ""

    if profile_id == "eric_poet_narrator":
        strength_key = str(
            strength or "Recognizably Eric"
        ).strip().casefold()
        strength_rule = {
            "light influence": (
                "Use only light Eric influence: direct feeling, purposeful "
                "cadence, and a decisive ending."
            ),
            "strong eric voice": (
                "Use strong Eric influence: emotionally direct language, "
                "energetic rhyme or near-rhyme, mythic scale when natural, "
                "memorable unusual phrasing, and a forceful final line."
            ),
        }.get(
            strength_key,
            "Use recognizable Eric influence: direct emotion, natural rhyme "
            "or near-rhyme, unusual but understandable imagery, and a strong "
            "ending.",
        )
        return (
            "ERIC — POET/NARRATOR COMPACT VOICE GUIDE\n"
            f"{strength_rule}\n"
            "Preserve rough edges that carry identity. Keep all wording new. "
            "Do not copy or recall any protected source poem line."
        )

    strength_rules = profile.get("strength_rules") or {}
    strength_key = str(
        strength
        or profile.get("default_strength")
        or ""
    ).strip().casefold()
    strength_rule = strength_rules.get(
        strength_key,
        next(
            iter(strength_rules.values()),
            "Use the profile traits with restraint.",
        ),
    )
    traits = "; ".join(
        str(item)
        for item in (profile.get("traits") or [])[:5]
    )
    boundaries = " ".join(
        str(item)
        for item in (
            profile.get("originality_rules")
            or []
        )[:3]
    )
    return (
        f"{profile.get('name','POETRY VOICE').upper()} "
        "COMPACT VOICE GUIDE\n"
        f"{strength_rule}\n"
        f"Core traits: {traits}.\n"
        f"Boundaries: {boundaries} "
        "Keep every replacement line new and limited to the submitted passage."
    )


def voice_catalog() -> List[Dict[str, Any]]:
    """Catalog for the UI: id, name, kind, strengths, source titles."""
    out = []
    for profile_id, profile in POETRY_VOICE_PROFILES.items():
        out.append({
            "id": profile_id,
            "name": profile.get("name", profile_id),
            "kind": profile.get("kind", ""),
            "default_strength": profile.get("default_strength", ""),
            "strengths": sorted((profile.get("strength_rules") or {}).keys()),
            "source_titles": profile.get("source_titles") or [],
            "has_private_sources": bool(profile.get("sources")),
        })
    return out
