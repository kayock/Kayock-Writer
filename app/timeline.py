"""Explicit fictional-world chronology helpers; never infer chronology from prose.

Supported comparable labels: "Day N" and ISO calendar dates (YYYY-MM-DD).
The two systems are deliberately incomparable. Narrative order is metadata,
not assumed to equal fictional-world time.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

_DAY = re.compile(r"day\s*(\d+)", re.IGNORECASE)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_world_time(value: str) -> Optional[Tuple[str, int]]:
    text = str(value or "").strip()
    match = _DAY.fullmatch(text)
    if match:
        return ("day", int(match.group(1)))
    if _DATE.fullmatch(text):
        try:
            return ("date", date.fromisoformat(text).toordinal())
        except ValueError:
            return None
    return None


def chronology(approved_facts: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Group approved facts only; never merge incomparable time systems."""
    timed: Dict[str, List[Dict[str, Any]]] = {"day": [], "date": []}
    unplaced: List[Dict[str, Any]] = []
    for record in approved_facts:
        if not isinstance(record, dict) or record.get("state") != "approved":
            continue
        item = dict(record)
        parsed = parse_world_time(item.get("world_time") or "")
        if parsed is None:
            unplaced.append(item)
        else:
            timed[parsed[0]].append(item)
    groups = []
    for family, label in (("day", "Day numbers"), ("date", "Calendar dates")):
        items = sorted(timed[family], key=lambda item:
                       parse_world_time(item.get("world_time"))[1])
        if items:
            groups.append({"time_system": family, "label": label, "facts": items})
    return {
        "ok": True, "groups": groups, "unplaced": unplaced,
        "total": sum(len(g["facts"]) for g in groups) + len(unplaced),
        "read_only": True,
        "note": "World chronology is author-declared. Different time systems and unspecified dates are not ordered against one another.",
    }


def character_knowledge(approved_facts: Iterable[Dict[str, Any]],
                        character: str, at_time: str = "") -> Dict[str, Any]:
    """Return only facts explicitly marked as known to this character.

    The author assigns known_by and optional learned_time. No inference from
    scene presence or fact/world time is made.
    """
    if not isinstance(character, str) or not character.strip():
        raise ValueError("Choose a character to inspect.")
    if len(character) > 200:
        raise ValueError("Character name is too long.")
    selected_time = parse_world_time(at_time) if at_time else None
    if at_time and selected_time is None:
        raise ValueError("For time-specific knowledge use 'Day N' or 'YYYY-MM-DD'.")
    confirmed, indeterminate = [], []
    later = 0
    for record in approved_facts:
        if not isinstance(record, dict) or record.get("state") != "approved":
            continue
        knowers = record.get("known_by")
        if not isinstance(knowers, list) or not any(
                isinstance(who, str) and who.strip().casefold() == character.strip().casefold()
                for who in knowers):
            continue
        item = dict(record)
        if selected_time is None:
            confirmed.append(item)
            continue
        learned = parse_world_time(str(record.get("learned_time") or ""))
        if learned is None or learned[0] != selected_time[0]:
            indeterminate.append(item)
            continue
        if learned[1] <= selected_time[1]:
            confirmed.append(item)
        else:
            later += 1
    return {
        "ok": True, "character": character.strip(), "at_world_time": at_time,
        "facts": confirmed, "count": len(confirmed),
        "time_uncertain_facts": indeterminate,
        "later_known_facts_excluded": later,
        "read_only": True,
        "disclaimer": (
            "Knowledge is explicitly assigned by the author; unspecified or "
            "incomparable learning times are not assumed to be known at the "
            "requested time. No passage, character memory, or canon is altered."
        ),
    }
