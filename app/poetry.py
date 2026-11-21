"""Kayock Writer Poetry & Short Story Forge backend.

Ported from FOXAI core/foxai_web.py KAYOCK_WRITER_CALM_HOME_V1_BACKEND
(lines ~24818–26831): creator (poem + short story), polisher (poem + story
with substantive-change retry), selected-lines workshop, save with front-matter
drafts, archive grouping, recordings folders, legacy manifest flags.

Differences from FOXAI (behavioral parity kept):
- `_poetry_chat` → provider.chat() against a configurable OpenAI-compatible
  endpoint; identical message/response semantics and {'ok': False} on failure.
- FOLDERS globals → app-owned Store paths.
- `os.startfile` folder opening → cross-platform, config-gated, best-effort.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from . import voices
from .provider import Provider
from .storage import Store, jread, jwrite, now, slug

WRITING_TYPES = {"poem", "short_story"}


# --------------------------------------------------------------------------
# text helpers (ported)
# --------------------------------------------------------------------------

def _writer_text(value, limit=12000):
    return str(value or '').replace('\x00', '').strip()[:max(1, int(limit))]


def _writer_exact_text(value, limit=12000):
    """Preserve whitespace when browser character positions must remain exact."""
    return str(value or '').replace('\x00', '')[:max(1, int(limit))]


def _clean_title(value):
    candidate = _writer_text(value, 160)
    candidate = re.sub(r'^\s*(?:title\s*[:\-]\s*)', '', candidate, flags=re.IGNORECASE)
    candidate = candidate.strip().strip('#*_`"\u201c\u201d\' ')
    candidate = re.sub(r'\s+', ' ', candidate)
    candidate = re.sub(r'[.,;:!?—\-]+\s*$', '', candidate).strip()
    words = candidate.split()
    if len(words) > 10:
        candidate = ' '.join(words[:10])
    return candidate[:80].strip()


def _fallback_title(theme, emotion, imagery):
    theme_words = re.findall(r"[A-Za-z0-9']+", theme or '')[:4]
    emotion_words = re.findall(r"[A-Za-z0-9']+", emotion or '')[:2]
    image_words = re.findall(r"[A-Za-z0-9']+", imagery or '')[:5]
    if theme_words and emotion_words:
        return _clean_title(' '.join(theme_words + ['in'] + emotion_words)) or 'Untitled Poem'
    if theme_words:
        return _clean_title(' '.join(theme_words)) or 'Untitled Poem'
    if image_words:
        return _clean_title(' '.join(image_words)) or 'Untitled Poem'
    return 'Untitled Poem'


class PoetryForge:
    def __init__(self, store: Store, provider: Provider, default_author: str = "Eric Z. Fox",
                 archive_limit: int = 500, allow_folder_open: bool = True):
        self.store = store
        self.provider = provider
        self.default_author = default_author
        self.archive_limit = max(10, int(archive_limit))
        self.allow_folder_open = bool(allow_folder_open)

    # -- model plumbing ------------------------------------------------------
    def chat(self, messages, max_tokens=900, temperature=0.82):
        result = self.provider.chat(messages, max_tokens=max_tokens, temperature=temperature)
        if result.get("ok"):
            return {"ok": True, "poem": result["text"],
                    "model_name": result.get("model_name") or self.provider.display_model()}
        return result

    # -- titles (ported) -------------------------------------------------------
    def _generate_title(self, poem, theme='', emotion='', imagery='', kind='poem'):
        is_story = kind == 'short_story'
        first_nonempty = next((line.strip() for line in poem.splitlines() if line.strip()), '')
        if is_story:
            system = (
                'You title short stories for Kayock Writer. Return only one concise original '
                'title of two to seven words. Do not use quotation marks, markdown, labels, '
                'commentary, or terminal punctuation. Do not simply repeat the opening '
                'sentence. Prefer a memorable image, conflict, mystery, or turn from the story.'
            )
            work_label = 'SHORT STORY'
            body_limit = 16000
        else:
            system = (
                'You title poems for Kayock Writer Poetry Studio. Return only one concise '
                'original title of two to seven words. Do not use quotation marks, markdown, '
                'labels, commentary, or terminal punctuation. Do not simply repeat the first '
                'line. Prefer a memorable image or tension from the poem.'
            )
            work_label = 'POEM'
            body_limit = 12000
        user = '\n'.join([
            f'Theme: {theme or "open"}',
            f'Emotion: {emotion or "open"}',
            f'Imagery: {imagery or "open"}',
            '',
            f'{work_label}:',
            poem[:body_limit],
        ])
        result = self.chat(
            [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            max_tokens=48,
            temperature=0.55,
        )
        if result.get('ok'):
            candidate = _clean_title(result.get('poem'))
            probe = first_nonempty
            if is_story:
                probe = re.split(r'(?<=[.!?])\s+', first_nonempty, 1)[0].strip()
            if candidate and candidate.casefold() != probe.casefold():
                return candidate
        fallback = _fallback_title(theme, emotion, imagery)
        if is_story and fallback == 'Untitled Poem':
            return 'Untitled Short Story'
        return fallback

    # =====================================================================
    # Creator (poem + short story) — FOXAI kayock_writer_poetry_create
    # =====================================================================
    def create(self, d=None):
        d = d or {}
        writing_type = _writer_text(d.get('writing_type') or 'poem', 40).strip().casefold()
        if writing_type not in WRITING_TYPES:
            writing_type = 'poem'
        is_story = writing_type == 'short_story'
        theme = _writer_text(d.get('theme'), 300)
        emotion = _writer_text(d.get('emotion'), 300)
        imagery = _writer_text(d.get('imagery'), 2000)
        speaker = _writer_text(d.get('speaker'), 500)
        personal_memory = _writer_text(d.get('personal_memory'), 3000)
        audience = _writer_text(d.get('audience'), 500)
        voice = _writer_text(d.get('voice') or 'My natural voice', 160)
        voice_strength = _writer_text(d.get('voice_strength') or 'Recognizably Eric', 80)
        form = _writer_text(d.get('form') or 'Free verse', 80)
        rhyme_preference = _writer_text(
            d.get('rhyme_preference') or 'Natural — let the poem decide', 120)
        rhythm_preference = _writer_text(
            d.get('rhythm_preference') or 'Natural spoken cadence', 120)
        length = _writer_text(d.get('length') or 'Medium', 40)
        canon = _writer_text(d.get('canon'), 5000)
        opening = _writer_text(d.get('opening_line'), 1000)
        variation = bool(d.get('variation'))

        creative_seed_fields = {
            'theme': theme, 'emotion': emotion, 'imagery': imagery,
            'speaker': speaker, 'personal_memory': personal_memory,
            'canon': canon, 'opening_line': opening,
        }
        if not any(creative_seed_fields.values()):
            return {
                'ok': False,
                'message': (
                    'Add at least a theme, emotion, scene, speaker, personal memory, '
                    'canon detail, or opening line.'
                ),
            }

        if is_story:
            length_guide = {
                'short': 'roughly 300 to 600 words',
                'medium': 'roughly 700 to 1,200 words',
                'long': 'roughly 1,300 to 2,000 words',
            }.get(length.lower(), 'roughly 700 to 1,200 words')
            rhyme_guide = 'Not used in short-story mode.'
            rhythm_guide = ('Use natural readable prose rhythm, varied sentence '
                            'length, and clear paragraphing.')
        else:
            length_guide = {
                'short': 'roughly 8 to 16 lines',
                'medium': 'roughly 18 to 32 lines',
                'long': 'roughly 35 to 60 lines',
            }.get(length.lower(), 'roughly 18 to 32 lines')

            rhyme_guide = {
                'natural — let the poem decide': (
                    'Use rhyme only where it strengthens the poem. Slant rhyme, internal '
                    'rhyme, repeated sounds, or no end rhyme are all acceptable. Do not '
                    'force a scheme.'
                ),
                'no required rhyme': (
                    'Do not force end rhyme. Let image, meaning, line breaks, and cadence '
                    'carry the poem.'
                ),
                'couplets — aabb': (
                    'Prefer an AABB couplet pattern where it sounds natural. Meaning and '
                    'the writer voice outrank perfect rhyme.'
                ),
                'alternating — abab': (
                    'Prefer an ABAB alternating pattern where it sounds natural. Allow '
                    'slant rhyme rather than distorting meaning.'
                ),
                'monorhyme — aaaa': (
                    'Explore an AAAA monorhyme pattern carefully. Avoid repetitive filler '
                    'and abandon exact rhyme when it harms the poem.'
                ),
                'internal and slant rhyme': (
                    'Favor internal rhyme, near rhyme, assonance, consonance, and spoken '
                    'sound over a rigid end-rhyme scheme.'
                ),
            }.get(
                rhyme_preference.strip().casefold(),
                'Treat the stated rhyme choice as a preference, not a rigid requirement.',
            )

            rhythm_guide = {
                'natural spoken cadence': (
                    'Use a natural read-aloud cadence with line breaks that support breath '
                    'and emphasis.'
                ),
                'steady lyrical pulse': (
                    'Use a steady lyrical pulse while allowing meaningful variation.'
                ),
                'loose conversational rhythm': (
                    'Use flexible conversational phrasing that still feels intentional '
                    'when spoken aloud.'
                ),
                'performance / spoken-word cadence': (
                    'Write for performance: strong breath points, momentum, emphasis, and '
                    'memorable sound without turning every line into a slogan.'
                ),
                'formal meter where possible': (
                    'Use a recognizable formal meter where practical, but do not damage '
                    'meaning or natural speech merely to satisfy the count.'
                ),
            }.get(
                rhythm_preference.strip().casefold(),
                'Treat the stated rhythm choice as a flexible craft preference.',
            )

        voice_profile_id = voices._writer_voice_profile_id(voice)
        if voice_profile_id == 'eric_short_fiction' and not is_story:
            voice_profile_id = ''
        voice_profile_prompt = voices.build_writer_voice_prompt(
            voice_profile_id, voice_strength, writing_type,
        ) if voice_profile_id else ''

        if is_story:
            system = (
                'You are Kayock Writer Short Story Creator, a respectful creative partner. '
                'Write one complete original short story only. Return prose paragraphs without '
                'a title, analysis, outline, labels, or commentary. Establish a specific scene, '
                'a clear character perspective or narrator, meaningful pressure or desire, and '
                'an earned turn, consequence, revelation, or ending. Preserve the writer\'s '
                'requested voice and meaning. Prefer vivid concrete detail over generic '
                'inspiration. If an opening line is supplied, use it exactly as the first '
                'sentence. Treat personal memories and canon as authoritative: do not invent '
                'extra biographical facts, relationships, events, names, or project lore. The '
                'intended audience should shape clarity and intensity without forcing direct '
                'address. Do not imitate a living author.'
            )
        else:
            system = (
                'You are Kayock Writer Poetry Studio, a respectful creative partner. Write one '
                'finished poem only. Do not explain the poem, announce the title, discuss '
                'your process, or add commentary outside the poem. Preserve the writer\'s '
                'requested voice and meaning. Prefer vivid, specific language over generic '
                'inspiration. Avoid clichés unless deliberately transformed. Follow the '
                'requested form honestly. If an opening line is supplied, use it exactly '
                'as the first line. Treat personal memories and canon as authoritative: '
                'do not invent extra biographical facts, relationships, events, names, or '
                'project lore. The intended audience should shape intimacy and clarity, '
                'not force a dedication or direct address unless appropriate. Rhyme and '
                'rhythm preferences must never override meaning, emotional truth, or the '
                'writer\'s identity. Do not imitate a living poet.'
            )
        if voice_profile_prompt:
            system += '\n\n' + voice_profile_prompt
        if is_story and voice_profile_prompt:
            system += (
                '\n\nSHORT STORY MODE OVERRIDE: Translate the profile\'s broad worldview, diction, '
                'imagery, emotional tendencies, and cadence into wholly original prose. Any '
                'profile wording that asks for poetry, rhyme, meter, stanzas, refrains, couplets, '
                'or line breaks is craft background only and must not turn this response into verse.'
            )

        if is_story:
            user = '\n'.join([
                f'Theme: {theme or "open"}',
                f'Emotion: {emotion or "open"}',
                f'Scene or imagery: {imagery or "open"}',
                f'Narrator or character voice: {speaker or "open"}',
                f'Personal memory or truth: {personal_memory or "none supplied"}',
                f'Intended audience: {audience or "open"}',
                f'Creative voice profile: {voice}',
                f'Story length: {length_guide}',
                f'Prose rhythm: {rhythm_guide}',
                f'Canon or established project details: {canon or "none supplied"}',
                f'Opening line: {opening or "none"}',
                (
                    'Create a distinctly different short-story variation with a different '
                    'approach, scene movement, or ending while preserving supplied facts.'
                    if variation else
                    'Create the first strong complete short story.'
                ),
            ])
            max_tokens = {'short': 1000, 'medium': 1900, 'long': 3100}.get(length.lower(), 1900)
            temperature = 0.88 if variation else 0.80
        else:
            user = '\n'.join([
                f'Theme: {theme or "open"}',
                f'Emotion: {emotion or "open"}',
                f'Scene or imagery: {imagery or "open"}',
                f'Speaker or character voice: {speaker or "open"}',
                f'Personal memory or truth: {personal_memory or "none supplied"}',
                f'Intended audience: {audience or "open"}',
                f'Creative voice profile: {voice}',
                f'Poetic form: {form}',
                f'Rhyme preference: {rhyme_preference}',
                f'Rhyme guidance: {rhyme_guide}',
                f'Rhythm preference: {rhythm_preference}',
                f'Rhythm guidance: {rhythm_guide}',
                f'Length: {length_guide}',
                f'Canon or established project details: {canon or "none supplied"}',
                f'Opening line: {opening or "none"}',
                (
                    'Create a distinctly different variation from the previous attempt.'
                    if variation else
                    'Create the first strong version.'
                ),
            ])
            max_tokens = {'short': 500, 'medium': 900, 'long': 1500}.get(length.lower(), 900)
            temperature = 0.9 if variation else 0.82

        result = self.chat(
            [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if not result.get('ok'):
            if is_story:
                result['message'] = str(result.get('message') or 'Short Story Creator failed.') \
                    .replace('empty poem', 'empty short story') \
                    .replace('Poetry Studio', 'Short Story Creator')
            return result

        suggested = self._generate_title(
            result['poem'], theme=theme, emotion=emotion, imagery=imagery,
            kind=writing_type,
        )
        provided_fields = [
            key
            for key, value in {
                'theme': theme,
                'emotion': emotion,
                'scene_or_imagery': imagery,
                'speaker': speaker,
                'personal_memory': personal_memory,
                'intended_audience': audience,
                'canon': canon,
                'opening_line': opening,
            }.items()
            if value
        ]
        result.update({
            'message': 'Short story created.' if is_story else 'Poem created.',
            'writing_type': writing_type,
            'suggested_title': suggested,
            'title_generated_separately': True,
            'settings': {
                'writing_type': writing_type,
                'theme': theme,
                'emotion': emotion,
                'imagery': imagery,
                'speaker': speaker,
                'personal_memory': personal_memory,
                'audience': audience,
                'voice': voice,
                'voice_strength': voice_strength,
                'form': '' if is_story else form,
                'rhyme_preference': '' if is_story else rhyme_preference,
                'rhythm_preference': 'Natural readable prose' if is_story else rhythm_preference,
                'length': length,
                'canon': canon,
                'opening_line': opening,
            },
            'provenance': {
                'writing_type': writing_type,
                'user_guidance_fields': provided_fields,
                'user_opening_line_preserved': bool(opening),
                'personal_memory_treated_as_authoritative': bool(personal_memory),
                'canon_treated_as_authoritative': bool(canon),
                'draft_source': 'kayock_generated_short_story' if is_story else 'kayock_generated_poem',
                'suggestions_applied_automatically': False,
                'saved_file_created': False,
            },
            'voice_profile': (
                voices._writer_voice_profile_name(voice_profile_id)
                if voice_profile_id else ''
            ),
            'voice_strength': voice_strength if voice_profile_id else '',
            'profile_sources': (
                voices.get_writer_voice_profile(voice_profile_id).get('source_titles', [])
                if voice_profile_id else []
            ),
            'source_poems_modified': False,
            'source_stories_modified': False,
            'new_work_not_copied': bool(voice_profile_id),
        })
        return result

    # =====================================================================
    # Polisher (poem + short story) — FOXAI kayock_writer_poetry_polish
    # =====================================================================
    def polish(self, d=None):
        d = d or {}
        writing_type = _writer_text(d.get('writing_type') or 'poem', 40).strip().casefold()
        if writing_type not in WRITING_TYPES:
            writing_type = 'poem'
        is_story = writing_type == 'short_story'
        work = _writer_text(d.get('poem'), 48000 if is_story else 24000)
        focus = _writer_text(
            d.get('focus') or ('Balanced story polish' if is_story else 'Balanced polish'),
            160,
        )
        voice = _writer_text(d.get('voice') or 'My natural voice', 160)
        voice_strength = _writer_text(
            d.get('voice_strength') or (
                'Recognizably Eric — Prose'
                if voice.strip().casefold() == 'eric — short fiction'.casefold() else
                'Recognizably Eric'
            ),
            80,
        )
        speaker = _writer_text(d.get('speaker'), 500)
        personal_memory = _writer_text(d.get('personal_memory'), 4000)
        audience = _writer_text(d.get('audience'), 500)
        canon = _writer_text(d.get('canon'), 6000)
        opening = _writer_text(d.get('opening_line'), 1000)
        if not work:
            return {
                'ok': False,
                'message': ('There is no short story to polish.' if is_story
                            else 'There is no poem to polish.'),
            }

        focus_key = focus.strip().casefold()
        if is_story:
            if focus_key == 'light cleanup':
                change_rule = (
                    'Make only small corrections to clarity, grammar, paragraphing, and awkward repetition. '
                    'Do not recast scenes or alter the ending.'
                )
                temperature = 0.24
            elif focus_key == 'pacing and scene flow':
                change_rule = (
                    'Improve pacing, transitions, paragraph movement, scene emphasis, and sentence variety. '
                    'Do not add, remove, reorder, or replace story events.'
                )
                temperature = 0.38
            elif focus_key == 'dialogue and character voice':
                change_rule = (
                    'Improve dialogue clarity, rhythm, attribution, and character distinction without changing '
                    'what characters decide, know, reveal, or mean.'
                )
                temperature = 0.38
            elif focus_key == 'imagery and atmosphere':
                change_rule = (
                    'Strengthen concrete imagery, sensory detail, and atmosphere only where the existing story '
                    'supports it. Do not invent new setting facts or lore.'
                )
                temperature = 0.42
            elif focus_key == 'emotional impact':
                change_rule = (
                    'Strengthen emotional clarity, pressure, and consequence while preserving restraint, events, '
                    'relationships, and the writer\'s intended meaning.'
                )
                temperature = 0.40
            elif focus_key == 'clarity and word choice':
                change_rule = (
                    'Improve clarity, precision, paragraphing, and word choice while preserving distinctive '
                    'phrasing, spoken rhythm, and intentional rough edges.'
                )
                temperature = 0.32
            elif focus_key == 'preserve voice with minimal changes':
                change_rule = (
                    'Change as little as possible. Correct only clear obstacles to reading and preserve unusual '
                    'diction, syntax, humor, intensity, and rough edges that carry the writer\'s identity.'
                )
                temperature = 0.22
            elif focus_key == 'deep polish — preserve story':
                change_rule = (
                    'Perform a thorough prose polish across pacing, flow, dialogue, imagery, atmosphere, emotional '
                    'impact, clarity, and word choice, but do not alter any protected story fact, event, character, '
                    'point of view, tense, timeline, canon element, central meaning, or intended ending.'
                )
                temperature = 0.48
            else:
                change_rule = (
                    'Make only changes that clearly improve the selected story-polish focus. Preserve strong '
                    'sentences, distinctive voice, and the complete identity of the submitted story.'
                )
                temperature = 0.35
        else:
            if focus_key == 'light touch':
                change_rule = 'Make only one to three small edits unless a line is clearly broken.'
                temperature = 0.30
            elif focus_key == 'bold rewrite':
                change_rule = ('You may substantially recast weak lines, imagery, rhythm, and structure while '
                               'preserving the poem\'s core meaning and recognizable voice.')
                temperature = 0.62
            elif focus_key == 'preserve voice with minimal changes':
                change_rule = ('Change as little as possible. Preserve unusual diction and rough edges that '
                               'feel intentional.')
                temperature = 0.28
            else:
                change_rule = ('Make only changes that clearly improve the selected focus; preserve strong '
                               'lines and the poem\'s overall identity.')
                temperature = 0.45

        voice_profile_id = voices._writer_voice_profile_id(voice)
        if voice_profile_id == 'eric_short_fiction' and not is_story:
            voice_profile_id = ''
        voice_profile_prompt = voices.build_writer_voice_prompt(
            voice_profile_id, voice_strength, writing_type,
        ) if voice_profile_id else ''

        if is_story:
            system = (
                'You are Kayock Writer Short Story Polisher. Return only the complete revised short story in prose paragraphs, '
                'with no title, critique, outline, labels, explanation, or commentary. The submitted story is the primary '
                'authority. Preserve its plot, characters, names, relationships, point of view, tense, setting, timeline, '
                'canon, central meaning, intended ending, and distinctive writer voice. Do not silently add a new character, '
                'scene, event, subplot, relationship, lore fact, biography, twist, moral, epilogue, or sequel hook. Do not '
                'remove an existing event merely to make the story smoother. Do not convert the work into poetry, a synopsis, '
                'an outline, a chapter plan, or a Story Forge expansion. Improve only prose craft: pacing, scene flow, dialogue, '
                'character voice, imagery, atmosphere, emotional impact, clarity, paragraphing, and word choice. Preserve '
                'unconventional phrasing when it carries identity or intentional spoken rhythm. '
                f'{change_rule} Do not imitate a living author.'
            )
            protected_guidance = '\n'.join([
                f'Narrator or character voice guidance: {speaker or "none supplied"}',
                f'Personal memory or truth that remains authoritative: {personal_memory or "none supplied"}',
                f'Intended audience: {audience or "open"}',
                f'Canon or established project details that must remain true: {canon or "none supplied"}',
                f'Opening line guidance: {opening or "none supplied"}',
            ])
            user = (
                f'Polish focus: {focus}\n\n'
                f'PROTECTED GUIDANCE:\n{protected_guidance}\n\n'
                f'SUBMITTED SHORT STORY — PRIMARY AUTHORITY:\n{work}'
            )
            source_words = max(1, len(work.split()))
            max_tokens = min(4000, max(1200, int(source_words * 1.7) + 450))
        else:
            system = (
                'You are Kayock Writer Poem Polisher. Return only the revised poem, with no critique or commentary. '
                'Preserve the writer\'s identity, meaning, strongest images, emotional intention, and unusual phrasing. '
                'Do not turn the poem into generic polished verse. '
                f'{change_rule} '
                'Do not imitate a living poet.'
            )
            user = f'Polish focus: {focus}\n\nPOEM:\n{work}'
            max_tokens = 1700

        if voice_profile_prompt:
            system += '\n\n' + voice_profile_prompt
            system += (
                '\n\nFor polishing, the submitted work remains the primary authority. '
                'The profile may strengthen compatible craft qualities but must not replace '
                'the work with source material, imported lore, a different plot, or a different ending.'
            )

        # FOXAI_SHORT_STORY_POLISHER_V1_1: substantive-change verification.
        def story_change_metrics(original, candidate):
            import difflib
            original_words = re.findall(r"[A-Za-z0-9'’_-]+", str(original or '').casefold())
            candidate_words = re.findall(r"[A-Za-z0-9'’_-]+", str(candidate or '').casefold())
            matcher = difflib.SequenceMatcher(None, original_words, candidate_words, autojunk=False)
            changed_words = 0
            changed_blocks = 0
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == 'equal':
                    continue
                changed_blocks += 1
                changed_words += max(i2 - i1, j2 - j1)
            exact = (
                re.sub(r'\s+', ' ', str(original or '')).strip().casefold()
                == re.sub(r'\s+', ' ', str(candidate or '')).strip().casefold()
            )
            return {
                'exact_match': exact,
                'similarity': round(float(matcher.ratio()), 6),
                'changed_words': int(changed_words),
                'changed_blocks': int(changed_blocks),
                'original_words': len(original_words),
                'candidate_words': len(candidate_words),
            }

        def story_change_is_substantive(metrics):
            if metrics.get('exact_match'):
                return False
            if focus_key in {'light cleanup', 'preserve voice with minimal changes'}:
                minimum = 1
            elif focus_key == 'deep polish — preserve story':
                minimum = 6
            else:
                minimum = 3
            return bool(
                int(metrics.get('changed_words') or 0) >= minimum
                or float(metrics.get('similarity') or 1.0) <= 0.992
            )

        result = self.chat(
            [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        polish_attempts = 1
        change_metrics = None
        if is_story and result.get('ok'):
            change_metrics = story_change_metrics(work, result.get('poem'))
            if not story_change_is_substantive(change_metrics):
                retry_system = (
                    system
                    + '\n\nThe prior attempt was rejected because it returned the source unchanged or nearly unchanged. '
                    'Produce a genuinely revised version now. Improve sentence rhythm, transitions, paragraph openings, '
                    'word precision, pacing, and concrete imagery where supported by the submitted story. Revise multiple '
                    'sentences, but preserve every protected story fact and the intended ending. Never return the source '
                    'verbatim and never explain the edits.'
                )
                retry_user = (
                    user
                    + '\n\nRETRY REQUIREMENT: Return a visibly polished complete story with several concrete prose improvements. '
                    'Do not add events or facts and do not return unchanged text.'
                )
                result = self.chat(
                    [{'role': 'system', 'content': retry_system}, {'role': 'user', 'content': retry_user}],
                    max_tokens=max_tokens,
                    temperature=min(0.68, max(0.46, temperature + 0.12)),
                )
                polish_attempts = 2
                if result.get('ok'):
                    change_metrics = story_change_metrics(work, result.get('poem'))
                    if not story_change_is_substantive(change_metrics):
                        return {
                            'ok': False,
                            'message': (
                                'The model returned the original story without enough substantive change after two attempts. '
                                'No polished version was accepted or made saveable. Try a different focus or model.'
                            ),
                            'writing_type': writing_type,
                            'focus': focus,
                            'unchanged_output': True,
                            'polish_attempts': polish_attempts,
                            'change_metrics': change_metrics,
                            'source_stories_modified': False,
                            'story_facts_protected': True,
                            'story_forge_used': False,
                        }
        if result.get('ok'):
            result['message'] = 'Polished short story created.' if is_story else 'Polished version created.'
            result['writing_type'] = writing_type
            result['focus'] = focus
            result['voice_profile'] = voices._writer_voice_profile_name(voice_profile_id) if voice_profile_id else ''
            result['voice_strength'] = voice_strength if voice_profile_id else ''
            result['profile_sources'] = (
                voices.get_writer_voice_profile(voice_profile_id).get('source_titles', [])
                if voice_profile_id else []
            )
            result['source_poems_modified'] = False
            result['source_stories_modified'] = False
            result['new_work_not_copied'] = bool(voice_profile_id)
            result['story_facts_protected'] = bool(is_story)
            result['story_forge_used'] = False
            result['suggestions_applied_automatically'] = False
            if is_story:
                result['polish_attempts'] = polish_attempts
                result['change_metrics'] = change_metrics or story_change_metrics(work, result.get('poem'))
                result['substantive_change'] = True
                result['identical_output_rejected'] = bool(polish_attempts > 1)
        return result

    # =====================================================================
    # Selected Lines & Stanza Workshop — FOXAI revise_selection
    # =====================================================================
    @staticmethod
    def _nonempty_lines(value):
        return [
            line.strip()
            for line in str(value or '').splitlines()
            if line.strip()
        ]

    @classmethod
    def _nearby_context(cls, value, *, take_last=False, max_lines=2):
        lines = cls._nonempty_lines(value)
        if take_last:
            lines = lines[-max_lines:]
        else:
            lines = lines[:max_lines]
        return '\n'.join(lines)

    @classmethod
    def _selection_alternatives(cls, raw, selected, before='', after=''):
        value = _writer_text(raw, 12000)
        value = re.sub(r'^```(?:text|markdown)?\s*', '', value, flags=re.IGNORECASE)
        value = re.sub(r'\s*```$', '', value)

        pattern = (
            r'\n\s*(?:<<<ALT>>>|'
            r'---+\s*ALTERNATIVE(?:\s+\d+)?\s*---+|'
            r'ALTERNATIVE\s+\d+\s*:?|'
            r'OPTION\s+\d+\s*:?)\s*\n'
        )
        parts = [
            part.strip()
            for part in re.split(pattern, '\n' + value, flags=re.IGNORECASE)
            if part.strip()
        ]
        if len(parts) < 2:
            numbered = re.split(r'(?m)^\s*(?:\d+[.)]|[A-C][.)])\s+', value)
            parts = [part.strip() for part in numbered if part.strip()]

        selected_lines = cls._nonempty_lines(selected)
        selected_line_count = max(1, len(selected_lines))
        max_line_count = selected_line_count + max(
            1, min(2, (selected_line_count + 1) // 2),
        )
        selected_length = max(1, len(selected.strip()))
        max_character_count = max(
            260,
            int(selected_length * 1.85) + 80,
        )

        protected_context = [
            line.casefold()
            for line in (
                cls._nonempty_lines(before)
                + cls._nonempty_lines(after)
            )
            if len(line) >= 12
        ]

        cleaned = []
        normalized_seen = set()
        selected_key = re.sub(r'\s+', ' ', selected).strip().casefold()

        for part in parts:
            part = re.sub(
                r'^\s*(?:alternative|option)\s*\d*\s*[:\-]\s*',
                '',
                part,
                flags=re.IGNORECASE,
            ).strip()
            part = part.strip('` ')
            if not part:
                continue

            lines = cls._nonempty_lines(part)
            if not lines:
                continue
            # Reject full-poem or multi-stanza answers. A replacement may vary by
            # one or two lines, but it may not grow into the surrounding poem.
            if len(lines) > max_line_count:
                continue
            if len(part) > max_character_count:
                continue

            part_key = part.casefold()
            if any(context_line in part_key for context_line in protected_context):
                continue

            key = re.sub(r'\s+', ' ', part).strip().casefold()
            if key == selected_key or key in normalized_seen:
                continue

            normalized_seen.add(key)
            cleaned.append(part)
            if len(cleaned) >= 3:
                break

        return cleaned

    def revise_selection(self, d=None):
        d = d or {}
        # Character positions come from the browser textarea. Do not strip either
        # value before validating the selected slice.
        poem = _writer_exact_text(d.get('poem'), 32000)
        selected = _writer_exact_text(d.get('selection'), 8000)
        title = _writer_text(d.get('title'), 160)
        focus = _writer_text(d.get('focus') or 'Keep meaning, improve the lines', 160)
        note = _writer_text(d.get('note'), 800)
        voice = _writer_text(d.get('voice') or 'My natural voice', 160)
        voice_strength = _writer_text(d.get('voice_strength') or 'Recognizably Eric', 80)
        try:
            start = int(d.get('selection_start'))
            end = int(d.get('selection_end'))
        except Exception:
            return {'ok': False, 'message': 'Selection positions were invalid. Capture the passage again.'}
        if not poem.strip() or not selected.strip():
            return {'ok': False, 'message': 'Capture selected lines or a stanza first.'}
        if start < 0 or end <= start or end > len(poem):
            return {'ok': False, 'message': 'The captured positions were outside the poem. Select the passage again.'}

        captured_slice = poem[start:end]
        if captured_slice != selected:
            # Older browser selections may include harmless leading/trailing
            # whitespace differently. Recover only when the same passage remains
            # at the same location after trimming those edges.
            left_trim = len(captured_slice) - len(captured_slice.lstrip())
            right_trim = len(captured_slice) - len(captured_slice.rstrip())
            adjusted_start = start + left_trim
            adjusted_end = end - right_trim
            adjusted_slice = poem[adjusted_start:adjusted_end]
            if adjusted_slice.strip() == selected.strip() and adjusted_slice.strip():
                start = adjusted_start
                end = adjusted_end
                selected = adjusted_slice
            else:
                return {
                    'ok': False,
                    'message': (
                        'The poem changed after the passage was captured. '
                        'Select the lines again before creating alternatives.'
                    ),
                }
        before_raw = poem[max(0, start - 1200):start]
        after_raw = poem[end:min(len(poem), end + 1200)]
        before = self._nearby_context(before_raw, take_last=True, max_lines=2)
        after = self._nearby_context(after_raw, take_last=False, max_lines=2)
        focus_rules = {
            'stronger imagery': 'Make each option more vivid and specific without changing the central meaning.',
            'smoother rhyme and rhythm': 'Improve cadence, line balance, rhyme, or near-rhyme while avoiding forced filler.',
            'more emotional impact': 'Increase emotional force through concrete language rather than melodrama.',
            'clearer wording': 'Clarify confusing wording while keeping the writer\'s distinctive phrasing.',
            'make it stranger and more memorable': 'Offer unusual but understandable images and phrasing; avoid generic poetic language.',
            'preserve voice with minimal changes': 'Make restrained edits and preserve rough edges that carry identity.',
        }
        focus_rule = focus_rules.get(
            focus.strip().casefold(),
            'Preserve the meaning and role of the passage while making the lines stronger.')
        voice_profile_id = voices._writer_voice_profile_id(voice)
        # The full profile may contain complete source poems. That is useful for
        # whole poem creation, but it can distract a small model during a
        # four-line edit — use the compact guide instead (FOXAI behavior).
        voice_profile_prompt = (
            voices.poetry_compact_voice_prompt(voice_profile_id, voice_strength)
            if voice_profile_id else ''
        )
        selected_line_count = max(1, len(self._nonempty_lines(selected)))
        minimum_lines = max(1, selected_line_count - 1)
        maximum_lines = selected_line_count + 1
        system = (
            'You are the Kayock Writer Selected Lines and Stanza Workshop. '
            'Create exactly three distinct replacement passages. '
            'OUTPUT ONLY THE REPLACEMENT LINES. NEVER RETURN THE WHOLE POEM. '
            'Never repeat a BEFORE or AFTER context line. '
            'Each choice must fit naturally between the supplied context. '
            f'Each choice must contain {minimum_lines} to {maximum_lines} nonblank lines. '
            'Do not include the title, context, explanations, labels, numbering, '
            'quotation marks, or markdown fences. '
            'Separate the three passages with a line containing exactly <<<ALT>>>. '
            'Do not return the unchanged selection as an option. '
            'Do not imitate a living poet. '
            f'{focus_rule}'
        )
        if voice_profile_prompt:
            system += '\n\n' + voice_profile_prompt
            system += (
                '\n\nFor this workshop, the submitted poem and selected passage are the primary authority. '
                'Use the profile only to preserve compatible voice qualities. Never import a source-poem line.'
            )
        user = '\n'.join([
            f'Title: {title or "Untitled Poem"}',
            f'Focus: {focus}',
            f'Additional direction: {note or "none"}',
            '',
            'BEFORE CONTEXT:',
            before or '[beginning of poem]',
            '',
            'SELECTED PASSAGE TO REPLACE:',
            selected,
            '',
            'AFTER CONTEXT:',
            after or '[end of poem]',
            '',
            'Return exactly three replacement passages separated by <<<ALT>>>.',
        ])
        selected_word_count = max(1, len(selected.split()))
        token_budget = min(700, max(260, selected_word_count * 7))
        result = self.chat(
            [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            max_tokens=token_budget,
            temperature=0.68,
        )
        if not result.get('ok'):
            return result
        alternatives = self._selection_alternatives(
            result.get('poem'), selected, before, after,
        )
        if not alternatives:
            return {
                'ok': False,
                'message': (
                    'The model returned text outside the selected passage, so '
                    'Kayock Writer rejected it. Press Create 3 Alternatives again.'
                ),
                'scope_rejected': True,
                'whole_poem_unchanged': True,
            }
        return {
            'ok': True,
            'message': f'{len(alternatives)} replacement choices created.',
            'alternatives': alternatives,
            'verified_selection_start': start,
            'verified_selection_end': end,
            'verified_selection': selected,
            'selection_unchanged': True,
            'whole_poem_unchanged': True,
            'voice_profile': voices._writer_voice_profile_name(voice_profile_id) if voice_profile_id else '',
            'voice_strength': voice_strength if voice_profile_id else '',
            'source_poems_modified': False,
        }

    # =====================================================================
    # Save (front-matter markdown drafts) — FOXAI kayock_writer_poetry_save
    # =====================================================================
    def _find_identical_saved(self, folder, content, version_kind):
        wanted = hashlib.sha256(str(content or '').strip().encode('utf-8')).hexdigest()
        if not folder.is_dir():
            return None
        for candidate in sorted(folder.glob('*.md'), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                text = candidate.read_text(encoding='utf-8')
            except Exception:
                continue
            if self._saved_meta(text, 'content_type') != 'short_story':
                continue
            if self._saved_meta(text, 'version') != version_kind:
                continue
            saved_body = self._saved_body(text)
            saved_hash = hashlib.sha256(saved_body.encode('utf-8')).hexdigest()
            if saved_hash == wanted:
                return {
                    'path': candidate,
                    'version_group': self._saved_meta(text, 'version_group'),
                    'content_sha256': saved_hash,
                }
        return None

    @staticmethod
    def _saved_body(markdown_text):
        text = str(markdown_text or '').replace('\r\n', '\n')
        if text.startswith('---\n'):
            end = text.find('\n---\n', 4)
            if end >= 0:
                text = text[end + 5:]
        text = text.lstrip('\n')
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith('#'):
            lines = lines[1:]
        return '\n'.join(lines).strip()

    @staticmethod
    def _saved_meta(markdown_text, key):
        text = str(markdown_text or '').replace('\r\n', '\n')
        if not text.startswith('---\n'):
            return ''
        end = text.find('\n---\n', 4)
        if end < 0:
            return ''
        prefix = f'{key}:'
        for line in text[4:end].splitlines():
            if line.startswith(prefix):
                raw = line[len(prefix):].strip()
                try:
                    value = json.loads(raw)
                except Exception:
                    value = raw.strip('"')
                return _writer_text(value, 240)
        return ''

    def save(self, d=None):
        d = d or {}
        content = _writer_text(d.get('poem'), 48000)
        title = _writer_text(d.get('title'), 160)
        settings = d.get('settings') if isinstance(d.get('settings'), dict) else {}
        writing_type = _writer_text(
            d.get('writing_type') or settings.get('writing_type') or 'poem',
            40,
        ).strip().casefold()
        if writing_type not in WRITING_TYPES:
            writing_type = 'poem'
        is_story = writing_type == 'short_story'
        version_kind = _writer_text(d.get('version_kind') or 'draft', 40).strip().casefold()
        version_group = _writer_text(d.get('version_group'), 120)
        source_mode = _writer_text(
            d.get('source_mode') or settings.get('source_mode') or 'creator',
            40,
        ).strip().casefold()
        if source_mode not in {'creator', 'polisher'}:
            source_mode = 'creator'
        polish_focus = _writer_text(d.get('polish_focus') or settings.get('polish_focus'), 160)
        if version_kind not in {'draft', 'original', 'polished'}:
            version_kind = 'draft'
        if not content:
            return {'ok': False,
                    'message': 'There is no short story to save.' if is_story else 'There is no poem to save.'}

        if is_story:
            folder = self.store.folder('short_story_drafts')
        else:
            folder = self.store.folder('poetry_drafts')
        content_sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()
        if is_story and source_mode == 'polisher' and version_kind in {'original', 'polished'}:
            existing = self._find_identical_saved(folder, content, version_kind)
            if existing:
                existing_group = _writer_text(existing.get('version_group'), 120)
                return {
                    'ok': True,
                    'message': (
                        'Canonical original already exists; no duplicate was created.'
                        if version_kind == 'original' else
                        'An identical polished revision already exists; no duplicate was created.'
                    ),
                    'path': str(existing['path']),
                    'writing_type': writing_type,
                    'version_kind': version_kind,
                    'version_group': existing_group or version_group,
                    'source_mode': source_mode,
                    'polish_focus': polish_focus,
                    'content_sha256': existing.get('content_sha256') or content_sha256,
                    'overwritten': False,
                    'new_file': False,
                    'reused_existing': True,
                    'deduplicated': True,
                    'creator_guidance_preserved': True,
                }
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        display_title = title or ('Untitled Short Story' if is_story else 'Untitled Poem')
        safe = (
            re.sub(r'[^A-Za-z0-9 _.-]', '', display_title)
            .strip()
            .replace(' ', '_')[:70]
            or ('Untitled_Short_Story' if is_story else 'Untitled_Poem')
        )
        kind_suffix = '' if version_kind == 'draft' else f'_{version_kind}'
        path = folder / f'{safe}{kind_suffix}_{stamp}.md'

        prompt_fields = {
            'writing_type': writing_type,
            'theme': _writer_text(settings.get('theme'), 300),
            'emotion': _writer_text(settings.get('emotion'), 300),
            'imagery': _writer_text(settings.get('imagery'), 4000),
            'speaker': _writer_text(settings.get('speaker'), 500),
            'personal_memory': _writer_text(settings.get('personal_memory'), 4000),
            'audience': _writer_text(settings.get('audience'), 500),
            'voice': _writer_text(settings.get('voice'), 160),
            'voice_strength': _writer_text(settings.get('voice_strength'), 80),
            'form': '' if is_story else _writer_text(settings.get('form'), 80),
            'rhyme_preference': '' if is_story else _writer_text(settings.get('rhyme_preference'), 120),
            'rhythm_preference': (
                'Natural readable prose'
                if is_story else
                _writer_text(settings.get('rhythm_preference'), 120)
            ),
            'length': _writer_text(settings.get('length'), 80),
            'canon': _writer_text(settings.get('canon'), 6000),
            'opening_line': _writer_text(settings.get('opening_line'), 1000),
            'author': _writer_text(settings.get('author') or self.default_author, 160),
            'copyright': _writer_text(settings.get('copyright'), 240),
        }

        source_label = (
            (
                'Kayock Writer Poetry Studio — Short Story Polisher'
                if source_mode == 'polisher' else
                'Kayock Writer Poetry Studio — Short Story Creator'
            )
            if is_story else
            'Kayock Writer Poetry Studio'
        )
        front = [
            '---',
            f'title: {json.dumps(display_title, ensure_ascii=False)}',
            f'author: {json.dumps(prompt_fields["author"], ensure_ascii=False)}',
            f'copyright: {json.dumps(prompt_fields["copyright"], ensure_ascii=False)}',
            f'created: {json.dumps(now())}',
            f'source: {json.dumps(source_label, ensure_ascii=False)}',
            f'source_mode: {json.dumps(source_mode)}',
            f'polish_focus: {json.dumps(polish_focus, ensure_ascii=False)}',
            f'content_type: {json.dumps(writing_type)}',
            f'model: {json.dumps(self.provider.display_model() if self.provider else "", ensure_ascii=False)}',
            f'version: {json.dumps(version_kind)}',
            f'version_group: {json.dumps(version_group, ensure_ascii=False)}',
            f'content_sha256: {json.dumps(content_sha256)}',
            f'form: {json.dumps(prompt_fields["form"], ensure_ascii=False)}',
            f'length: {json.dumps(prompt_fields["length"], ensure_ascii=False)}',
            f'voice: {json.dumps(prompt_fields["voice"], ensure_ascii=False)}',
            'voice_strength: '
            f'{json.dumps(prompt_fields["voice_strength"], ensure_ascii=False)}',
            'voice_profile_sources_read_only: '
            f'{json.dumps(bool(voices._writer_voice_profile_id(prompt_fields["voice"])))}',
            f'theme: {json.dumps(prompt_fields["theme"], ensure_ascii=False)}',
            f'emotion: {json.dumps(prompt_fields["emotion"], ensure_ascii=False)}',
            f'imagery: {json.dumps(prompt_fields["imagery"], ensure_ascii=False)}',
            f'speaker: {json.dumps(prompt_fields["speaker"], ensure_ascii=False)}',
            'personal_memory: '
            f'{json.dumps(prompt_fields["personal_memory"], ensure_ascii=False)}',
            f'audience: {json.dumps(prompt_fields["audience"], ensure_ascii=False)}',
            'rhyme_preference: '
            f'{json.dumps(prompt_fields["rhyme_preference"], ensure_ascii=False)}',
            'rhythm_preference: '
            f'{json.dumps(prompt_fields["rhythm_preference"], ensure_ascii=False)}',
            f'canon: {json.dumps(prompt_fields["canon"], ensure_ascii=False)}',
            'opening_line: '
            f'{json.dumps(prompt_fields["opening_line"], ensure_ascii=False)}',
            'opened_from: '
            f'{json.dumps(_writer_text(settings.get("opened_from"), 220), ensure_ascii=False)}',
            'opened_mode: '
            f'{json.dumps(_writer_text(settings.get("opened_mode"), 80), ensure_ascii=False)}',
            'prompt_fields: '
            f'{json.dumps(prompt_fields, ensure_ascii=False)}',
            '---',
            '',
            f'# {display_title}',
            '',
            content,
            '',
        ]
        path.write_text('\n'.join(front), encoding='utf-8')
        noun = 'Short story' if is_story else 'Poetry'
        return {
            'ok': True,
            'message': f'{noun} {version_kind} saved as {path.name}.',
            'path': str(path),
            'writing_type': writing_type,
            'version_kind': version_kind,
            'version_group': version_group,
            'source_mode': source_mode,
            'source_label': source_label,
            'polish_focus': polish_focus,
            'content_sha256': content_sha256,
            'overwritten': False,
            'new_file': True,
            'reused_existing': False,
            'deduplicated': False,
            'creator_guidance_preserved': True,
        }

    # =====================================================================
    # Archive, recordings, legacy manifest — FOXAI poem archive block
    # =====================================================================
    @property
    def _archive_folder(self):
        return self.store.folder('poetry_drafts')

    @property
    def _recordings_root(self):
        return self.store.folder('poetry_recordings')

    @property
    def _legacy_root(self):
        return self.store.folder('poetry_legacy')

    @staticmethod
    def _archive_title_key(title):
        return slug(_writer_text(title, 160)).casefold()

    @property
    def _archive_manifest_path(self):
        return self._legacy_root / 'legacy_manifest.json'

    def _archive_manifest(self):
        data = jread(self._archive_manifest_path, {})
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _parse_scalar(value):
        raw = str(value or '').strip()
        if not raw:
            return ''
        try:
            return json.loads(raw)
        except Exception:
            return raw.strip('"').strip("'")

    def _parse_markdown(self, path, include_poem=False):
        try:
            raw = path.read_text(encoding='utf-8', errors='replace')
        except Exception as exc:
            return {'ok': False, 'message': f'{type(exc).__name__}: {exc}', 'filename': path.name}
        lines = raw.splitlines()
        meta = {}
        body_start = 0
        if lines and lines[0].strip() == '---':
            for index in range(1, len(lines)):
                line = lines[index]
                if line.strip() == '---':
                    body_start = index + 1
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    meta[key.strip()] = self._parse_scalar(value)
        body = '\n'.join(lines[body_start:]).strip()
        body_lines = body.splitlines()
        if body_lines and body_lines[0].lstrip().startswith('# '):
            body = '\n'.join(body_lines[1:]).strip()
        stat = path.stat()
        created = str(meta.get('created') or datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'))
        try:
            created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            created_display = created_dt.astimezone().strftime('%b %d, %Y · %I:%M %p')
            created_sort = created_dt.timestamp()
        except Exception:
            created_display = created
            created_sort = stat.st_mtime
        title = _writer_text(meta.get('title'), 160) or \
            re.sub(r'_(?:draft|original|polished)?_?\d{8}_\d{6}(?:_\d+)?$',
                   '', path.stem, flags=re.IGNORECASE).replace('_', ' ')
        version = _writer_text(meta.get('version') or 'draft', 40).strip().casefold()
        if version not in {'draft', 'original', 'polished'}:
            version = 'draft'
        entry = {
            'ok': True,
            'filename': path.name,
            'title': title or 'Untitled Poem',
            'author': _writer_text(meta.get('author') or self.default_author, 160),
            'copyright': _writer_text(meta.get('copyright'), 240),
            'created': created,
            'created_display': created_display,
            'created_sort': created_sort,
            'version': version,
            'version_group': _writer_text(meta.get('version_group'), 120),
            'voice': _writer_text(meta.get('voice'), 160),
            'voice_strength': _writer_text(meta.get('voice_strength'), 80),
            'model': _writer_text(meta.get('model'), 180),
            'theme': _writer_text(meta.get('theme'), 300),
            'emotion': _writer_text(meta.get('emotion'), 300),
            'imagery': _writer_text(meta.get('imagery'), 4000),
            'speaker': _writer_text(meta.get('speaker'), 500),
            'personal_memory': _writer_text(meta.get('personal_memory'), 4000),
            'audience': _writer_text(meta.get('audience'), 500),
            'form': _writer_text(meta.get('form'), 80),
            'rhyme_preference': _writer_text(meta.get('rhyme_preference'), 120),
            'rhythm_preference': _writer_text(meta.get('rhythm_preference'), 120),
            'length': _writer_text(meta.get('length'), 80),
            'canon': _writer_text(meta.get('canon'), 6000),
            'opening_line': _writer_text(meta.get('opening_line'), 1000),
            'opened_from': _writer_text(meta.get('opened_from'), 220),
            'opened_mode': _writer_text(meta.get('opened_mode'), 80),
            'prompt_fields': meta.get('prompt_fields') if isinstance(meta.get('prompt_fields'), dict) else {},
            'profile_sources_read_only': bool(meta.get('voice_profile_sources_read_only')),
            'excerpt': re.sub(r'\s+', ' ', body)[:220],
            'size_bytes': stat.st_size,
        }
        if include_poem:
            entry['poem'] = body
        return entry

    def _safe_markdown(self, name):
        for folder in (self._archive_folder, self.store.folder('short_story_drafts')):
            candidate = (folder / Path(str(name or '')).name).resolve()
            try:
                candidate.relative_to(folder.resolve())
            except Exception:
                continue
            if candidate.suffix.casefold() != '.md' or not candidate.is_file():
                continue
            return candidate
        return None

    def _recording_folder(self, title):
        return self._recordings_root / slug(_writer_text(title, 160))

    _AUDIO_SUFFIXES = {'.wav', '.flac', '.mp3', '.m4a', '.ogg', '.aac'}

    def _recording_snapshot(self, title):
        folder = self._recording_folder(title)
        files = []
        if folder.is_dir():
            files = sorted(
                [
                    path for path in folder.iterdir()
                    if path.is_file() and path.suffix.casefold() in self._AUDIO_SUFFIXES
                ],
                key=lambda item: item.name.casefold(),
            )

        def find_slot(*terms):
            for path in files:
                stem = path.stem.casefold().replace('-', '_').replace(' ', '_')
                if any(term in stem for term in terms):
                    return {'found': True, 'filename': path.name, 'path': str(path)}
            return {'found': False, 'filename': '', 'path': ''}

        slots = {
            'original': find_slot('original'),
            'polished': find_slot('polished'),
            'personal_message': find_slot('personal_message', 'personalmessage', 'message'),
        }
        return {
            'folder': str(folder),
            'folder_exists': folder.is_dir(),
            'found_count': sum(1 for slot in slots.values() if slot['found']),
            'audio_file_count': len(files),
            'slots': slots,
            'master_policy': 'Original recordings remain read-only; cleaned or model-ready copies stay separate.',
        }

    def archive(self):
        folder = self._archive_folder
        folder.mkdir(parents=True, exist_ok=True)
        # FOXAI saved short stories to a separate drafts folder that its poem
        # archive never scanned. Kayock Writer merges both so "Browse My
        # Writing" shows every saved work; each entry keeps its content_type.
        story_folder = self.store.folder('short_story_drafts')
        manifest = self._archive_manifest()
        entries = []
        limit = self.archive_limit
        paths = sorted(
            list(folder.glob('*.md')) + list(story_folder.glob('*.md')),
            key=lambda item: item.stat().st_mtime, reverse=True,
        )[:limit]
        for path in paths:
            parsed = self._parse_markdown(path, include_poem=False)
            if parsed.get('ok'):
                parsed['content_type'] = 'short_story' if path.parent == story_folder else 'poem'
                entries.append(parsed)
        grouped = {}
        for entry in entries:
            title = entry['title']
            key = self._archive_title_key(title)
            grouped.setdefault(key, {'title': title, 'versions': []})['versions'].append(entry)
        groups = []
        for key, group in grouped.items():
            versions = sorted(group['versions'],
                              key=lambda item: item.get('created_sort', 0), reverse=True)
            latest = versions[0]
            content_type = next(
                (v.get('content_type') for v in versions if v.get('content_type')), 'poem')
            counts = {'draft': 0, 'original': 0, 'polished': 0}
            for version in versions:
                counts[version['version']] = counts.get(version['version'], 0) + 1

            def latest_file(kind):
                return next((item['filename'] for item in versions if item['version'] == kind), '')

            is_eric_voice = any(
                item.get('voice', '').strip().casefold() == 'eric — poet/narrator'.casefold()
                or item.get('profile_sources_read_only')
                for item in versions
            )
            special = group['title'].strip().casefold() == 'voices that carry home'.casefold() and is_eric_voice
            stored = manifest.get(key, {}) if isinstance(manifest.get(key, {}), dict) else {}
            legacy = bool(stored.get('legacy', special))
            for_akaysha = bool(stored.get('for_akaysha', special))
            for_nevaeh = bool(stored.get('for_nevaeh', special))
            recordings = self._recording_snapshot(group['title'])
            groups.append({
                'id': hashlib.sha256(key.encode('utf-8')).hexdigest()[:16],
                'key': key,
                'title': group['title'],
                'content_type': content_type,
                'author': latest.get('author') or self.default_author,
                'copyright': next((item.get('copyright') for item in versions if item.get('copyright')),
                                  'Copyright © 2026 by Eric Z. Fox' if special else ''),
                'latest_created': latest.get('created', ''),
                'latest_created_display': latest.get('created_display', ''),
                'voice': next((item.get('voice') for item in versions if item.get('voice')), ''),
                'voice_strength': next((item.get('voice_strength') for item in versions if item.get('voice_strength')), ''),
                'model': next((item.get('model') for item in versions if item.get('model')), ''),
                'theme': next((item.get('theme') for item in versions if item.get('theme')), ''),
                'emotion': next((item.get('emotion') for item in versions if item.get('emotion')), ''),
                'imagery': next((item.get('imagery') for item in versions if item.get('imagery')), ''),
                'speaker': next((item.get('speaker') for item in versions if item.get('speaker')), ''),
                'personal_memory': next((item.get('personal_memory') for item in versions if item.get('personal_memory')), ''),
                'audience': next((item.get('audience') for item in versions if item.get('audience')), ''),
                'form': next((item.get('form') for item in versions if item.get('form')), ''),
                'rhyme_preference': next((item.get('rhyme_preference') for item in versions if item.get('rhyme_preference')), ''),
                'rhythm_preference': next((item.get('rhythm_preference') for item in versions if item.get('rhythm_preference')), ''),
                'length': next((item.get('length') for item in versions if item.get('length')), ''),
                'canon': next((item.get('canon') for item in versions if item.get('canon')), ''),
                'opening_line': next((item.get('opening_line') for item in versions if item.get('opening_line')), ''),
                'is_eric_voice': is_eric_voice,
                'is_first_eric_voice': special,
                'legacy': legacy,
                'for_akaysha': for_akaysha,
                'for_nevaeh': for_nevaeh,
                'legacy_notes': _writer_text(stored.get('notes'), 500),
                'version_total': len(versions),
                'version_counts': counts,
                'latest_original': latest_file('original'),
                'latest_polished': latest_file('polished'),
                'latest_draft': latest_file('draft'),
                'latest_any': latest['filename'],
                'versions': versions,
                'recordings': recordings,
            })
        groups.sort(key=lambda item: max(
            (v.get('created_sort', 0) for v in item['versions']), default=0), reverse=True)
        return {
            'ok': True,
            'message': 'Poetry archive scanned without changing source files.',
            'folder': str(folder),
            'poem_count': len(groups),
            'file_count': len(entries),
            'groups': groups,
            'source_files_modified': False,
        }

    def archive_read(self, name):
        path = self._safe_markdown(name)
        if path is None:
            return {'ok': False, 'message': 'Saved poem file was not found.'}
        result = self._parse_markdown(path, include_poem=True)
        result['source_file_modified'] = False
        return result

    def recordings_prepare(self, d=None):
        d = d or {}
        title = _writer_text(d.get('title'), 160)
        if not title:
            return {'ok': False, 'message': 'Choose a poem first.'}
        folder = self._recording_folder(title)
        existed = folder.is_dir()
        folder.mkdir(parents=True, exist_ok=True)
        readme = folder / 'README_RECORDINGS.txt'
        created_readme = False
        if not readme.exists():
            base = slug(title)
            readme.write_text(
                '\n'.join([
                    f'KAYOCK WRITER VOICE LEGACY RECORDINGS — {title}',
                    '',
                    'Suggested master filenames:',
                    f'{base}_original.wav',
                    f'{base}_polished.wav',
                    f'{base}_personal_message.wav',
                    '',
                    'Keep these master recordings read-only.',
                    'Create separate copies for noise cleanup, trimming, segmentation, or voice-model preparation.',
                    'Spoken names personalize playback; they are not secure authentication.',
                    '',
                ]),
                encoding='utf-8',
            )
            created_readme = True
        return {
            'ok': True,
            'message': 'Recording folder prepared.' if not existed else 'Recording folder already exists.',
            'folder': str(folder),
            'folder_created': not existed,
            'readme_created': created_readme,
            'poem_files_modified': False,
            'recordings': self._recording_snapshot(title),
        }

    def recordings_open(self, title):
        title = _writer_text(title, 160)
        if not title:
            return {'ok': False, 'message': 'Choose a poem first.'}
        folder = self._recording_folder(title)
        if not folder.is_dir():
            return {'ok': False, 'message': 'Prepare the recording folder first.'}
        opened = self._open_folder_on_server(folder)
        if opened:
            return {
                'ok': True,
                'message': f'Open request sent for {folder.name}; window state is not verified.',
                'folder': str(folder),
                'claim_state': 'requested',
                'poem_files_modified': False,
            }
        return {
            'ok': True,
            'message': f'Recording folder is at: {folder}',
            'folder': str(folder),
            'claim_state': 'path_only',
            'poem_files_modified': False,
        }

    def _open_folder_on_server(self, folder: Path) -> bool:
        """Best-effort, config-gated server-side folder open (was os.startfile)."""
        import sys
        if not hasattr(self, 'allow_folder_open') or not self.allow_folder_open:
            return False
        try:
            if sys.platform.startswith('win'):
                os_startfile = getattr(__import__('os'), 'startfile', None)
                if os_startfile:
                    os_startfile(str(folder))
                    return True
                return False
            if sys.platform == 'darwin':
                subprocess.Popen(['open', str(folder)])
                return True
            subprocess.Popen(['xdg-open', str(folder)])
            return True
        except Exception:
            return False

    def legacy_update(self, d=None):
        d = d or {}
        title = _writer_text(d.get('title'), 160)
        field = _writer_text(d.get('field'), 40).strip().casefold()
        if not title:
            return {'ok': False, 'message': 'Choose a poem first.'}
        if field not in {'legacy', 'for_akaysha', 'for_nevaeh'}:
            return {'ok': False, 'message': 'That legacy setting is not supported.'}
        value = bool(d.get('value'))
        path = self._archive_manifest_path
        manifest = self._archive_manifest()
        key = self._archive_title_key(title)
        record = manifest.get(key, {}) if isinstance(manifest.get(key, {}), dict) else {}
        record.update({
            'title': title,
            field: value,
            'updated': now(),
        })
        manifest[key] = record
        jwrite(path, manifest)
        labels = {
            'legacy': 'Legacy work',
            'for_akaysha': 'For Akaysha',
            'for_nevaeh': 'For Nevaeh',
        }
        return {
            'ok': True,
            'message': f'{labels[field]} {"enabled" if value else "disabled"} for {title}.',
            'title': title,
            'field': field,
            'value': value,
            'manifest_path': str(path),
            'poem_files_modified': False,
        }
