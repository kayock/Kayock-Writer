"""Conservative, read-only continuity review against author-approved facts.

This is a *potential-tension* detector, not a semantic proof or timeline
reasoner. It only reports explicit opposite statements when the named subject
and attribute are present in both canon and a sentence of the draft. Timing
and context may resolve apparent conflicts; authors decide.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?", re.UNICODE)

# Narrow, auditable patterns intentionally favor precision over recall.
_LIVING = re.compile(r"\b(?:is|was|remains|stayed|still)\s+(?:(?:very|quite)\s+)?(alive|dead)\b", re.I)
_SCAR = re.compile(r"\b(left|right)\s+(arm|hand|leg|eye)\b", re.I)
_NEGATION = re.compile(r"\b(?:not|never|isn't|wasn't|cannot|can't)\b", re.I)


def _attribute(sentence: str) -> Dict[str, str]:
    result = {}
    life = _LIVING.search(sentence)
    if life and not _NEGATION.search(sentence):
        result["life"] = life.group(1).lower()
    # A wound may move; this is still just an advisory signal.
    if re.search(r"\bscar\b", sentence, re.I):
        scar = _SCAR.search(sentence)
        if scar and not _NEGATION.search(sentence):
            result["scar:" + scar.group(2).lower()] = scar.group(1).lower()
    return result


def check(draft: str, facts: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("A passage is required for continuity review.")
    if len(draft) > 80000:
        raise ValueError("Continuity passage exceeds 80,000 characters; select an excerpt.")
    sentences = [s.strip() for s in _SENTENCE.findall(draft) if s.strip()]
    alerts: List[Dict[str, Any]] = []
    reviewed = 0
    for fact in facts:
        if not isinstance(fact, dict) or fact.get("state") != "approved":
            continue
        reviewed += 1
        subject = str(fact.get("subject") or "").strip()
        claim = str(fact.get("claim") or "").strip()
        if not subject or not claim:
            continue
        # Only compare an attribute in sentences that explicitly name the subject.
        # This avoids attributing an unrelated character's condition to them.
        subject_pattern = re.compile(r"(?<!\w)" + re.escape(subject) + r"(?!\w)", re.I)
        baseline = {}
        for piece in _SENTENCE.findall(claim):
            if subject_pattern.search(piece):
                baseline.update(_attribute(piece))
        if not baseline:
            continue
        for sentence in sentences:
            if not subject_pattern.search(sentence):
                continue
            candidate = _attribute(sentence)
            for key, canonical in baseline.items():
                if key not in candidate or canonical == candidate[key]:
                    continue
                alerts.append({
                    "kind": "potential_continuity_tension",
                    "severity": "review",
                    "subject": subject,
                    "attribute": key,
                    "approved_value": canonical,
                    "draft_value": candidate[key],
                    "approved_claim": claim,
                    "draft_excerpt": sentence,
                    "fact_id": fact.get("id"),
                    "world_time": str(fact.get("world_time") or ""),
                    "narrative_order": str(fact.get("narrative_order") or ""),
                    "evidence": [dict(e) for e in (fact.get("evidence") or [])
                                 if isinstance(e, dict)],
                    "explanation": (
                        "The draft appears to describe a different state than an "
                        "approved fact. Time, point of view, or a later event may "
                        "explain it. This is a review suggestion, not a proven error."
                    ),
                })
    return {
        "ok": True,
        "reviewed_approved_facts": reviewed,
        "sentences_checked": len(sentences),
        "alerts": alerts,
        "alert_count": len(alerts),
        "saved": False,
        "source_unchanged": True,
        "disclaimer": "Heuristic review of explicit opposite statements only; not a complete continuity analysis.",
    }
