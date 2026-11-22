"""Conservative, read-only continuity review against approved canon.

A limited set of explicit character attributes can be compared. An optional
fictional-world time lets the checker compare the *latest dated approved
state at or before that time*, without confusing an earlier character state
with a later one. Unsupported dates never acquire invented ordering.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from .timeline import parse_world_time

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?", re.UNICODE)
_LIVING = re.compile(r"\b(?:is|was|remains|stayed|still)\s+(?:(?:very|quite)\s+)?(alive|dead)\b", re.I)
_SCAR = re.compile(r"\b(left|right)\s+(arm|hand|leg|eye)\b", re.I)
_NEGATION = re.compile(r"\b(?:not|never|isn't|wasn't|cannot|can't)\b", re.I)


def _attribute(sentence: str) -> Dict[str, str]:
    result = {}
    life = _LIVING.search(sentence)
    if life and not _NEGATION.search(sentence):
        result["life"] = life.group(1).lower()
    if re.search(r"\bscar\b", sentence, re.I):
        scar = _SCAR.search(sentence)
        if scar and not _NEGATION.search(sentence):
            result["scar:" + scar.group(2).lower()] = scar.group(1).lower()
    return result


def _baselines(fact: Dict[str, Any]) -> Dict[str, str]:
    subject = str(fact.get("subject") or "").strip()
    if not subject:
        return {}
    pattern = re.compile(r"(?<!\w)" + re.escape(subject) + r"(?!\w)", re.I)
    baseline: Dict[str, str] = {}
    for phrase in _SENTENCE.findall(str(fact.get("claim") or "")):
        if pattern.search(phrase):
            baseline.update(_attribute(phrase))
    return baseline


def check(draft: str, facts: Iterable[Dict[str, Any]],
          world_time: str = "") -> Dict[str, Any]:
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("A passage is required for continuity review.")
    if len(draft) > 80000:
        raise ValueError("Continuity passage exceeds 80,000 characters; select an excerpt.")
    if not isinstance(world_time, str) or len(world_time) > 100:
        raise ValueError("World time must be short text.")
    selected = parse_world_time(world_time) if world_time.strip() else None
    if world_time.strip() and selected is None:
        raise ValueError("To check a specific time use 'Day N' or 'YYYY-MM-DD'.")
    sentences = [s.strip() for s in _SENTENCE.findall(draft) if s.strip()]
    approved = [f for f in facts if isinstance(f, dict) and f.get("state") == "approved"]
    checks = []
    skipped_future = 0
    skipped_unknown = 0
    if selected is None:
        for record in approved:
            for attribute, baseline in _baselines(record).items():
                checks.append((record, attribute, baseline))
    else:
        # The same character may have an approved different state later.
        # Compare only the most recent comparable declaration available
        # in the selected fictional-world timeline at that moment.
        latest = {}
        for record in approved:
            parsed = parse_world_time(str(record.get("world_time") or ""))
            if parsed is None or parsed[0] != selected[0]:
                skipped_unknown += 1
                continue
            if parsed[1] > selected[1]:
                skipped_future += 1
                continue
            for attribute, baseline in _baselines(record).items():
                key = (str(record.get("subject") or "").casefold(), attribute)
                if key not in latest or parsed[1] > latest[key][0]:
                    latest[key] = (parsed[1], record, attribute, baseline)
                elif parsed[1] == latest[key][0] and baseline != latest[key][3]:
                    # Two opposing author-approved facts at the same time.
                    # Keep both as uncertainty; don't silently pick one.
                    checks.append((record, attribute, baseline))
        checks.extend((record, attribute, baseline)
                      for _, record, attribute, baseline in latest.values())
    alerts: List[Dict[str, Any]] = []
    for record, attribute, canonical in checks:
        subject = str(record.get("subject") or "").strip()
        if not subject:
            continue
        subject_pattern = re.compile(r"(?<!\w)" + re.escape(subject) + r"(?!\w)", re.I)
        for sentence in sentences:
            if not subject_pattern.search(sentence):
                continue
            candidate = _attribute(sentence)
            if attribute not in candidate or candidate[attribute] == canonical:
                continue
            alerts.append({
                "kind": "potential_continuity_tension",
                "severity": "review",
                "subject": subject,
                "attribute": attribute,
                "approved_value": canonical,
                "draft_value": candidate[attribute],
                "approved_claim": str(record.get("claim") or ""),
                "draft_excerpt": sentence,
                "fact_id": record.get("id"),
                "world_time": str(record.get("world_time") or ""),
                "narrative_order": str(record.get("narrative_order") or ""),
                "evidence": [dict(e) for e in (record.get("evidence") or [])
                             if isinstance(e, dict)],
                "explanation": (
                    "The draft appears to describe a different state from "
                    "the relevant approved fact. Unrecorded events, narrative "
                    "order or viewpoint may still explain it. This is a "
                    "review suggestion, not a proven error."
                ),
            })
    return {
        "ok": True, "reviewed_approved_facts": len(approved),
        "compared_fact_attributes": len(checks),
        "sentences_checked": len(sentences),
        "alerts": alerts, "alert_count": len(alerts),
        "selected_world_time": world_time.strip(),
        "time_scope_applied": selected is not None,
        "future_facts_excluded": skipped_future,
        "undated_or_incomparable_facts_excluded": skipped_unknown,
        "saved": False, "source_unchanged": True,
        "disclaimer": (
            "Heuristic review only. Time-scoped checks compare the latest "
            "compatible dated states and exclude future, undated and "
            "incomparable records; they do not infer unseen state changes "
            "or prove complete continuity."
        ),
    }
