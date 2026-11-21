"""Kayock Writer — The Weaver (port of FOXAI THE_WEAVER_V1_BACKEND).

Synthesizes 2–4 pasted sources into one new work (poem, short story, clean
prose, or Twine passages). The two-stage plan→generate flow, annotation
contamination checks, copy-metric warnings, and no-overwrite saving all match
FOXAI behavior.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from . import voices
from .provider import Provider
from .storage import Store, jwrite, now, slug


def _weaver_source_text(value, limit=22000):
    text = str(value or '').replace('\x00', '').strip()
    return text[:max(1, int(limit))]


def _weaver_clean_title(value, fallback='Woven Work'):
    candidate = _weaver_source_text(value, 120)
    candidate = re.sub(r'^\s*(?:title\s*[:\-]\s*)', '', candidate, flags=re.IGNORECASE)
    candidate = candidate.strip().strip('#*_`"\u201c\u201d\' ')
    candidate = re.sub(r'\s+', ' ', candidate)
    candidate = re.sub(r'[.,;:!?—\-]+\s*$', '', candidate).strip()
    return (candidate[:80].strip() or fallback)


def _weaver_parse_plan(value, sources, output_type):
    raw = str(value or '').strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\s*```$', '', raw)
    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {
        'suggested_title': 'Woven Work',
        'shared_threads': [],
        'structure': 'A clean unified weave that gives each source a clear contribution.',
        'source_roles': [{'title': item['title'],
                          'role': 'Contributes imagery, emotional movement, or narrative material.'}
                         for item in sources],
        'passage_plan': (['Start', 'Turning Point', 'Choice', 'Ending'] if output_type == 'twine' else []),
        'fallback_plan': True,
    }


def _weaver_clean_output(value, output_type):
    text = str(value or '').replace('\x00', '').strip()
    text = re.sub(r'^```(?:twee|twine|markdown|md|text)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    text = re.sub(r'^\s*(?:FINAL\s+(?:WOVEN\s+)?WORK|WOVEN\s+WORK|OUTPUT)\s*[:\-]\s*',
                  '', text, flags=re.IGNORECASE)
    text = text.strip()
    if output_type == 'twine':
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'(?m)^[ \t]*::[ \t]*', ':: ', text)
        if not re.search(r'(?m)^::\s+Start\s*$', text, re.IGNORECASE):
            first = re.search(r'(?m)^::\s+.+$', text)
            if first:
                text = text[:first.start()] + ':: Start' + text[first.end():]
            else:
                text = ':: Start\n\n' + text
    return text.strip()


def _weaver_annotation_flags(text):
    value = str(text or '')
    patterns = {
        'source_labels': r'(?im)^\s*(?:source|text|poem|story)\s*[1-4]\s*:',
        'editorial_notes': r'(?im)^\s*(?:editor(?:ial)?\s+note|note to (?:writer|user)|annotation|analysis)\s*:',
        'process_commentary': r'(?im)^\s*(?:here is|i have|i combined|the following)\b.{0,80}(?:weave|woven|sources|texts)',
        'bracketed_notes': r'(?i)\[(?:note|source|annotation|editor|comment)\s*:',
    }
    return [name for name, pattern in patterns.items() if re.search(pattern, value)]


def _weaver_copy_metrics(output, sources):
    import difflib
    output_words = re.findall(r"[A-Za-z0-9'’_-]+", str(output or '').casefold())
    metrics = []
    for item in sources:
        source_words = re.findall(r"[A-Za-z0-9'’_-]+", item['content'].casefold())
        matcher = difflib.SequenceMatcher(None, source_words, output_words, autojunk=False)
        match = matcher.find_longest_match(0, len(source_words), 0, len(output_words))
        denominator = max(1, min(len(source_words), len(output_words)))
        metrics.append({
            'title': item['title'],
            'source_words': len(source_words),
            'longest_verbatim_words': int(match.size),
            'longest_verbatim_ratio': round(match.size / denominator, 6),
            'overall_similarity': round(matcher.ratio(), 6),
        })
    return metrics


def _weaver_plan_prompt(sources, mode, output_type, direction):
    source_block = '\n\n'.join(
        f"SOURCE {index + 1} — {item['title']}\n{item['content']}"
        for index, item in enumerate(sources)
    )
    system = (
        'You are Kayock Writer — The Weaver planning stage. Create a concise editorial source map, '
        'not hidden reasoning. Return valid JSON only with keys suggested_title, shared_threads, '
        'structure, source_roles, and passage_plan. source_roles must be an array of objects with '
        'title and role. shared_threads must be short phrases. passage_plan is required only for '
        'Twine output and should list passage names and purposes. Do not quote long passages, do '
        'not write the final creative work, and do not include analysis or chain-of-thought.'
    )
    user = (
        f'Weave mode: {mode}\nOutput type: {output_type}\nUser direction: {direction or "none"}\n\n'
        f'{source_block}'
    )
    return system, user


def _weaver_generation_prompt(sources, plan, mode, output_type, voice, length, direction):
    labels = {
        'shared_soul': 'Create one new unified work from the sources\' shared emotional or thematic soul.',
        'braided_voices': 'Braid the source threads or perspectives so each remains distinguishable but the result reads as one intentional work.',
        'best_threads': 'Use the strongest compatible lines, images, scenes, or passages, transforming and joining them into a coherent new whole.',
        'new_tapestry': 'Write a substantially new original work inspired by the sources rather than summarizing or mechanically combining them.',
    }
    formats = {
        'poem': 'Return only a finished poem. Preserve intentional line and stanza breaks.',
        'short_story': 'Return only one complete short story in prose paragraphs with an earned ending.',
        'clean_prose': 'Return only clean literary prose with deliberate paragraph and scene breaks.',
        'twine': (
            'Return only valid Twee/Twine passage source. Begin with :: Start. Use :: Passage Name headings on their own lines, '
            'blank lines between passages, and optional [[Choice->Passage]] links where choices genuinely help. Keep passage names concise. '
            'Do not add YAML, code fences, explanations, source labels, or notes.'
        ),
    }
    length_rules = {
        'short': 'Keep the result compact: roughly 300–650 words, or 3–5 Twine passages.',
        'long': 'Develop the result fully: roughly 1,400–2,400 words, or 8–14 Twine passages.',
    }
    source_block = '\n\n'.join(
        f"SOURCE {index + 1} — {item['title']}\n{item['content']}"
        for index, item in enumerate(sources)
    )
    system = (
        'You are Kayock Writer — The Weaver, a creative synthesis tool. Return only the finished creative work. '
        'Never include editorial annotations, source labels, bracketed notes, planning commentary, explanations, or model process. '
        'Preserve the originals by creating a separate derivative work; never claim to have modified a source. '
        'Honor supplied facts and intentional meanings, but do not copy long passages verbatim unless Best Threads explicitly calls for selected lines. '
        'Do not imitate a living author. ' + formats.get(output_type, formats['clean_prose'])
    )
    if voice and voice != 'My natural voice':
        profile_id = voices._writer_voice_profile_id(voice)
        if profile_id:
            system += '\n\n' + voices.build_writer_voice_prompt(
                profile_id, 'Recognizable influence',
                'short_story' if output_type in {'short_story', 'clean_prose', 'twine'} else 'poem')
        else:
            system += f'\n\nUse this broad creative voice preference without imitation: {voice}.'
    plan_json = json.dumps(plan, ensure_ascii=False)
    user = '\n'.join([
        f'Weave mode: {mode}',
        f'Mode instruction: {labels.get(mode, labels["shared_soul"])}',
        f'Output type: {output_type}',
        f'Target length: {length}',
        length_rules.get(str(length).strip().casefold(),
                         'Use a medium length: roughly 700–1,300 words, or 5–8 Twine passages.'),
        f'User direction: {direction or "none supplied"}',
        f'Concise source map: {plan_json}',
        '',
        source_block,
    ])
    return system, user


class Weaver:
    def __init__(self, store: Store, provider: Provider, default_author: str = "Eric Z. Fox"):
        self.store = store
        self.provider = provider
        self.default_author = default_author

    def chat(self, messages, max_tokens=900, temperature=0.82):
        result = self.provider.chat(messages, max_tokens=max_tokens, temperature=temperature)
        if result.get('ok'):
            return {'ok': True, 'poem': result['text'],
                    'model_name': result.get('model_name') or self.provider.display_model()}
        return result

    def generate(self, d=None):
        d = d or {}
        raw_sources = d.get('sources') if isinstance(d.get('sources'), list) else []
        sources = []
        total_chars = 0
        for index, item in enumerate(raw_sources[:4]):
            if not isinstance(item, dict):
                continue
            content = _weaver_source_text(item.get('content'), 22000)
            if not content:
                continue
            title = _weaver_clean_title(item.get('title'), f'Source {index + 1}')
            total_chars += len(content)
            sources.append({
                'title': title,
                'content': content,
                'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
                'words': len(re.findall(r"[A-Za-z0-9'’_-]+", content)),
            })
        if len(sources) < 2:
            return {'ok': False,
                    'message': 'The Weaver needs at least two non-empty sources. No files were changed.'}
        if total_chars > 60000:
            return {'ok': False,
                    'message': 'The combined sources are too large for Weaver 1.0. Use shorter selections '
                               'totaling no more than 60,000 characters. No files were changed.'}
        mode = _weaver_source_text(d.get('mode'), 40).casefold() or 'shared_soul'
        if mode not in {'shared_soul', 'braided_voices', 'best_threads', 'new_tapestry'}:
            mode = 'shared_soul'
        output_type = _weaver_source_text(d.get('output_type'), 30).casefold() or 'clean_prose'
        if output_type not in {'poem', 'short_story', 'clean_prose', 'twine'}:
            output_type = 'clean_prose'
        voice = _weaver_source_text(d.get('voice'), 100) or 'My natural voice'
        length = _weaver_source_text(d.get('length'), 20) or 'Medium'
        direction = _weaver_source_text(d.get('direction'), 3000)

        plan_system, plan_user = _weaver_plan_prompt(sources, mode, output_type, direction)
        plan_result = self.chat(
            [{'role': 'system', 'content': plan_system}, {'role': 'user', 'content': plan_user}],
            max_tokens=700,
            temperature=0.35,
        )
        plan = _weaver_parse_plan(
            plan_result.get('poem') if plan_result.get('ok') else '', sources, output_type)

        system, user = _weaver_generation_prompt(sources, plan, mode, output_type, voice, length, direction)
        max_tokens = {'short': 1300, 'medium': 2600, 'long': 4200}.get(length.strip().casefold(), 2600)
        result = self.chat(
            [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            max_tokens=max_tokens,
            temperature=0.76 if mode == 'new_tapestry' else 0.68,
        )
        attempts = 1
        if not result.get('ok'):
            result['source_files_modified'] = False
            return result
        output = _weaver_clean_output(result.get('poem'), output_type)
        flags = _weaver_annotation_flags(output)
        twine_invalid = bool(output_type == 'twine' and
                             len(re.findall(r'(?m)^::\s+.+$', output)) < 2)
        if flags or twine_invalid:
            retry_system = system + (
                '\n\nThe prior draft was rejected because it contained editorial contamination or invalid output formatting. '
                'Return only the finished creative work. Remove every source label, note, explanation, annotation, and process statement. '
                'For Twine, provide at least two clean :: Passage Name blocks beginning with :: Start.'
            )
            result = self.chat(
                [{'role': 'system', 'content': retry_system}, {'role': 'user', 'content': user}],
                max_tokens=max_tokens,
                temperature=0.62,
            )
            attempts = 2
            if not result.get('ok'):
                result['source_files_modified'] = False
                return result
            output = _weaver_clean_output(result.get('poem'), output_type)
            flags = _weaver_annotation_flags(output)
            twine_invalid = bool(output_type == 'twine' and
                                 len(re.findall(r'(?m)^::\s+.+$', output)) < 2)
            if flags or twine_invalid:
                return {
                    'ok': False,
                    'message': 'The model did not return a clean Weaver result after two attempts. '
                               'No woven output was accepted or saved.',
                    'annotation_flags': flags,
                    'twine_format_invalid': twine_invalid,
                    'source_map': plan,
                    'source_files_modified': False,
                    'attempts': attempts,
                }

        copy_metrics = _weaver_copy_metrics(output, sources)
        warnings = []
        threshold = 0.72 if mode == 'best_threads' else 0.48
        for metric in copy_metrics:
            if metric['longest_verbatim_words'] >= 35 and metric['longest_verbatim_ratio'] >= threshold:
                warnings.append(
                    f"A long passage closely matches {metric['title']} "
                    f"({metric['longest_verbatim_words']} consecutive words). Review before saving."
                )
        title = _weaver_clean_title(plan.get('suggested_title'), 'Woven Work')
        output_hash = hashlib.sha256(output.encode('utf-8')).hexdigest()
        return {
            'ok': True,
            'message': 'Woven work created.',
            'title': title,
            'output': output,
            'output_type': output_type,
            'output_type_label': {
                'poem': 'Poem', 'short_story': 'Short story',
                'clean_prose': 'Clean prose', 'twine': 'Twine-ready passages',
            }[output_type],
            'mode': mode,
            'voice': voice,
            'length': length,
            'direction': direction,
            'source_map': plan,
            'provenance': {'sources': [{k: item[k] for k in ('title', 'sha256', 'words')}
                                       for item in sources]},
            'copy_metrics': copy_metrics,
            'warnings': warnings,
            'word_count': len(re.findall(r"[A-Za-z0-9'’_-]+", output)),
            'content_sha256': output_hash,
            'attempts': attempts,
            'source_files_modified': False,
            'source_files_read_only': True,
            'finished_output_contains_annotations': False,
            'hidden_chain_of_thought_requested': False,
            'planning_summary_is_editorial_artifact': True,
            'story_forge_used': False,
        }

    def save(self, d=None):
        d = d or {}
        output = _weaver_source_text(d.get('output'), 80000)
        if not output:
            return {'ok': False, 'message': 'There is no woven output to save.'}
        output_type = _weaver_source_text(d.get('output_type'), 30).casefold() or 'clean_prose'
        if output_type not in {'poem', 'short_story', 'clean_prose', 'twine'}:
            output_type = 'clean_prose'
        title = _weaver_clean_title(d.get('title'), 'Woven Work')
        folder = self.store.folder('weaver_outputs')
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        base = slug(title)[:70] or 'Woven_Work'
        content_hash = hashlib.sha256(output.encode('utf-8')).hexdigest()
        provenance = (d.get('provenance') or {}).get('sources') \
            if isinstance(d.get('provenance'), dict) else []
        if not isinstance(provenance, list):
            provenance = []
        metadata = {
            'title': title,
            'author': _weaver_source_text(d.get('author'), 120) or self.default_author,
            'created': now(),
            'source': 'Kayock Writer — The Weaver',
            'content_type': 'weaver_output',
            'weaver_output_type': output_type,
            'weaver_mode': _weaver_source_text(d.get('mode'), 40),
            'voice': _weaver_source_text(d.get('voice'), 100),
            'length': _weaver_source_text(d.get('length'), 30),
            'direction': _weaver_source_text(d.get('direction'), 3000),
            'model': self.provider.display_model() if self.provider else 'active model',
            'content_sha256': content_hash,
            'source_provenance': provenance,
            'source_files_modified': False,
            'source_files_read_only': True,
            'no_overwrite': True,
        }
        created = []
        if output_type == 'twine':
            work_path = folder / f'{base}_{stamp}.twee'
            meta_path = folder / f'{base}_{stamp}.weaver.json'
            work_path.write_text(output.rstrip() + '\n', encoding='utf-8')
            jwrite(meta_path, metadata)
            created = [str(work_path), str(meta_path)]
        else:
            work_path = folder / f'{base}_{stamp}.md'
            frontmatter = '---\n' + \
                '\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False)}'
                          for key, value in metadata.items()) + \
                '\n---\n\n'
            work_path.write_text(frontmatter + f'# {title}\n\n' + output.rstrip() + '\n',
                                 encoding='utf-8')
            created = [str(work_path)]
        return {
            'ok': True,
            'message': f"Saved a separate no-overwrite Weaver revision: {Path(created[0]).name}",
            'created_files': created,
            'folder': str(folder),
            'content_sha256': content_hash,
            'source_files_modified': False,
            'no_overwrite': True,
        }
