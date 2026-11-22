"""Optional, non-destructive editorial assistant.

It never edits files or changes text in another Forge. Users must explicitly
copy/apply a suggestion. Uses the configured model on demand.
"""
from __future__ import annotations

from typing import Any, Dict

from .provider import Provider

REVIEW_SYSTEM = """You are a professional literary editor, not a ghostwriter.
Read the author's actual draft and give a useful, specific editorial review.
Preserve the author's chosen voice, meaning, plot, poetry form, unusual
phrasing that carries personality, character relationships, and canon.
Focus on the highest-impact improvements. Do not rewrite the work. Use these
headings: STRENGTHS, CLARITY AND FLOW, VOICE AND ORIGINALITY, CONCRETE EDITS,
NEXT PASS. Quote only short excerpts from the submitted draft as needed.
Never invent background, sources, references, or manuscript details.
"""

SUGGEST_SYSTEM = """You are a careful literary line editor. Return ONLY the
revised passage, with no preface, notes, headings, fences, or follow-up.
Keep the original author's voice, point of view, narrative facts, characters,
canon, rough expressive edges, and intended ending. Preserve poem line breaks
and stanza boundaries; preserve prose paragraphs and scene separators. Make
restrained edits for clarity, rhythm, grammar, and pacing. Do not add events,
characters, or factual assertions. Do not imitate copyrighted passages.
"""



DEVELOPMENTAL_SYSTEM = """You are a developmental literary editor reviewing
the AUTHOR'S actual passage, not drafting new prose. Analyze structure,
scene purpose, narrative promises and payoffs, pacing, motivation, scene
transitions and tension. Separate observed evidence from hypotheses and
questions for the author. Use headings: STRUCTURAL STRENGTHS, SCENE PURPOSE,
PACING AND CAUSALITY, CHARACTER CHOICES, PRIORITIZED QUESTIONS.
Quote only short submitted excerpts. Flag missing context instead of
inventing story-world facts. Preserve the author's voice and decisions;
do not rewrite, save, or publish the passage.
"""

VOICE_AUDIT_SYSTEM = """You are an author-respecting literary voice critic.
Analyze the submitted passage's sentence rhythm, perspective, diction,
imagery, emotional directness, and distinctive expressive choices.
If the author explicitly supplied a Voice DNA style reference, compare
high-level patterns without copying sample wording or plot.
Use headings: DISTINCTIVE VOICE SIGNALS, NATURAL RHYTHM, PASSAGES TO KEEP,
PLACES THAT FEEL FLATTENED, OPTIONAL MICRO-SUGGESTIONS.
Cite short excerpts from the submitted draft. Never claim you know
an author's personal style beyond the provided evidence. Do not
rewrite the full draft, change files, or invent writing history.
"""

def prepare_editorial(payload: Dict[str, Any], max_tokens: int = 4000,
                      canon_context: str = "",
                      voice_context: str = "") -> Dict[str, Any]:
    """Share exact validation/prompt rules between classic and streaming reviews."""
    draft = str(payload.get('text') or '')
    mode = str(payload.get('mode') or 'review').strip().casefold()
    kind = str(payload.get('writing_type') or 'prose').strip().casefold()
    title = str(payload.get('title') or '').strip()[:200]
    direction = str(payload.get('direction') or '').strip()[:1000]
    if mode not in ('review', 'suggestion', 'developmental', 'voice_audit'):
        return {'ok': False, 'message': 'Choose review, suggestion, developmental, or voice audit mode.'}
    if kind not in ('poem', 'short_story', 'novel', 'prose'):
        return {'ok': False, 'message': 'Unrecognized writing type.'}
    if not draft.strip():
        return {'ok': False, 'message': 'Add a passage to review.'}
    if len(draft) > 80000:
        return {'ok': False, 'message': 'Passage exceeds 80,000 characters. Select a chapter or excerpt; nothing was truncated.'}
    max_tokens = max(200, int(max_tokens))
    instruction = {
        'review': REVIEW_SYSTEM,
        'suggestion': SUGGEST_SYSTEM,
        'developmental': DEVELOPMENTAL_SYSTEM,
        'voice_audit': VOICE_AUDIT_SYSTEM,
    }[mode]
    if canon_context:
        instruction += '\n\n' + canon_context
    if voice_context:
        instruction += '\n\n' + voice_context
    messages = [
        {'role': 'system', 'content': instruction},
        {'role': 'user', 'content':
            f'Type: {kind}\nTitle: {title or "Untitled"}\n'
            f'Author direction: {direction or "Respect the submitted work."}\n'
            'DRAFT START\n' + draft + '\nDRAFT END'},
    ]
    return {'ok': True, 'mode': mode, 'draft': draft, 'messages': messages,
            'max_tokens': max_tokens, 'temperature': 0.45 if mode == 'suggestion' else 0.35}


def editorial_review(provider: Provider, payload: Dict[str, Any],
                     max_tokens: int = 4000,
                     canon_context: str = '',
                     voice_context: str = '') -> Dict[str, Any]:
    prepared = prepare_editorial(
        payload, max_tokens, canon_context=canon_context,
        voice_context=voice_context
    )
    if not prepared['ok']:
        return prepared
    response = provider.chat(prepared['messages'],
                             max_tokens=prepared['max_tokens'],
                             temperature=prepared['temperature'])
    if not response.get('ok'):
        return {'ok': False, 'message': response.get('message', 'Model did not respond.')}
    result = str(response.get('text') or '')
    if prepared['mode'] == 'suggestion' and result.strip() == prepared['draft'].strip():
        return {'ok': False, 'message': 'No changes suggested; original is unchanged.'}
    return {'ok': True, 'mode': prepared['mode'], 'text': result,
            'saved': False, 'source_unchanged': True,
            'message': 'Review complete. No work was saved or overwritten.'}
