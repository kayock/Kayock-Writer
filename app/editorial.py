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


def editorial_review(provider: Provider, payload: Dict[str, Any],
                     max_tokens: int = 4000) -> Dict[str, Any]:
    draft = str(payload.get('text') or '')
    mode = str(payload.get('mode') or 'review').strip().casefold()
    kind = str(payload.get('writing_type') or 'prose').strip().casefold()
    title = str(payload.get('title') or '').strip()[:200]
    direction = str(payload.get('direction') or '').strip()[:1000]
    if mode not in ('review', 'suggestion'):
        return {'ok': False, 'message': 'Choose review or suggestion mode.'}
    if kind not in ('poem', 'short_story', 'novel', 'prose'):
        return {'ok': False, 'message': 'Unrecognized writing type.'}
    if not draft.strip():
        return {'ok': False, 'message': 'Add a passage to review.'}
    if len(draft) > 80000:
        return {'ok': False, 'message': 'Passage exceeds 80,000 characters. Select a chapter or excerpt; nothing was truncated.'}
    max_tokens = max(200, int(max_tokens))
    instruction = REVIEW_SYSTEM if mode == 'review' else SUGGEST_SYSTEM
    response = provider.chat([
        {'role': 'system', 'content': instruction},
        {'role': 'user', 'content':
            f'Type: {kind}\nTitle: {title or "Untitled"}\n'
            f'Author direction: {direction or "Respect the submitted work."}\n'
            'DRAFT START\n' + draft + '\nDRAFT END'},
    ], max_tokens=max_tokens, temperature=0.35 if mode == 'review' else 0.45)
    if not response.get('ok'):
        return {'ok': False, 'message': response.get('message', 'Model did not respond.')}
    result = str(response.get('text') or '')
    if mode == 'suggestion' and result.strip() == draft.strip():
        return {'ok': False, 'message': 'No changes suggested; original is unchanged.'}
    return {'ok': True, 'mode': mode, 'text': result,
            'saved': False, 'source_unchanged': True,
            'message': 'Review complete. No work was saved or overwritten.'}
