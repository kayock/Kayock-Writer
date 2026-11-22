"""Opt-in structured canon proposals for Kayock Writer universes.

The existing Novel Forge universe JSON is never modified here. Proposals are
isolated in a sibling .canon directory, and become approved facts only through
an explicit approve operation. No LLM calls or background updates occur.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from .storage import Store, contained, jread, jwrite, now, slug

KINDS = frozenset({"character", "location", "artifact", "event", "relationship", "thread", "rule"})
STATES = frozenset({"proposed", "approved", "rejected"})


class CanonStore:
    def __init__(self, store: Store):
        self.store = store

    def _root(self, universe: str) -> Path:
        name = slug(universe)
        root = self.store.folder("novel_forge")
        path = (root / ".canon" / name).resolve()
        if not contained(path, root):
            raise ValueError("Invalid universe")
        return path

    def _path(self, universe: str) -> Path:
        return self._root(universe) / "facts.json"

    def _load(self, universe: str) -> Dict[str, Any]:
        path = self._path(universe)
        data = jread(path, None)
        if data is None:
            if path.exists():
                raise ValueError("Damaged canon JSON; refusing to overwrite")
            return {"schema": "kayock.writer.canon.v1", "universe": universe, "facts": []}
        if not isinstance(data, dict) or data.get("schema") != "kayock.writer.canon.v1" or not isinstance(data.get("facts"), list):
            raise ValueError("Unsupported or damaged canon data; refusing to overwrite")
        return data

    def prepare_relocation(self, old_universe: str, new_universe: str) -> None:
        """Preflight a rename so existing canon records cannot be overwritten."""
        source, target = self._root(old_universe), self._root(new_universe)
        if source != target and source.exists() and target.exists():
            raise ValueError("The target universe already has canon records.")

    def relocate(self, old_universe: str, new_universe: str) -> None:
        self.prepare_relocation(old_universe, new_universe)
        source, target = self._root(old_universe), self._root(new_universe)
        if source == target or not source.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        data = self._load(new_universe)
        data["universe"] = new_universe
        jwrite(self._path(new_universe), data)

    def list_facts(self, universe: str, state: str | None = None) -> Dict[str, Any]:
        if state is not None and state not in STATES:
            raise ValueError("Invalid state")
        facts = self._load(universe)["facts"]
        return {"ok": True, "facts": [dict(f) for f in facts if state is None or f["state"] == state]}

    def propose(self, universe: str, kind: str, subject: str, claim: str,
                evidence: List[Dict[str, str]], *, chapter: str = "",
                world_time: str = "", narrative_order: str = "") -> Dict[str, Any]:
        """Queue a fact for human review; no canon status is granted yet."""
        if kind not in KINDS:
            raise ValueError("Unrecognized canon kind")
        if not isinstance(subject, str) or not subject.strip() or not isinstance(claim, str) or not claim.strip():
            raise ValueError("Fact subject and claim required")
        if not isinstance(evidence, list) or not evidence or any(
            not isinstance(e, dict)
            or not isinstance(e.get("source"), str) or not e["source"].strip()
            or not isinstance(e.get("quote"), str) or not e["quote"].strip()
            for e in evidence
        ):
            raise ValueError("A source and text excerpt are required for each evidence item")
        record = {
            "id": uuid.uuid4().hex,
            "kind": kind, "subject": subject.strip(), "claim": claim.strip(),
            "evidence": [{"source": e["source"].strip(), "quote": e["quote"].strip()} for e in evidence],
            "chapter": str(chapter), "world_time": str(world_time),
            "narrative_order": str(narrative_order),
            "state": "proposed", "created": now(), "reviewed": None,
        }
        data = self._load(universe)
        data["facts"].append(record)
        jwrite(self._path(universe), data)
        return {"ok": True, "fact": dict(record)}

    def review(self, universe: str, fact_id: str, decision: str) -> Dict[str, Any]:
        """Record deliberate accept/reject. A second decision cannot overwrite history."""
        if decision not in ("approved", "rejected"):
            raise ValueError("Decision must be approved or rejected")
        data = self._load(universe)
        for record in data["facts"]:
            if record["id"] == fact_id:
                if record["state"] != "proposed":
                    raise ValueError("Fact was already reviewed")
                record["state"] = decision
                record["reviewed"] = now()
                jwrite(self._path(universe), data)
                return {"ok": True, "fact": dict(record)}
        raise KeyError("Fact not found")

    def approved_context(self, universe: str) -> List[Dict[str, Any]]:
        """Return only reviewed canon for optional future context assembly."""
        return self.list_facts(universe, "approved")["facts"]
