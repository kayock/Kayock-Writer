"""Approved-only, explicit relationship graph for Novel Forge.

The graph does not infer relationships from prose. Legacy relationship claims
without source/target/type annotations remain in the canonical record store
but are not invented into graph edges.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List


def _node_id(name: str) -> str:
    return hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:24]


def build_graph(facts: Iterable[Dict[str, Any]], focus: str = "",
                max_edges: int = 150) -> Dict[str, Any]:
    if not isinstance(focus, str) or len(focus) > 200:
        raise ValueError("Relationship focus must be text up to 200 characters.")
    if type(max_edges) is not int or not 1 <= max_edges <= 250:
        raise ValueError("Relationship edge limit must be between 1 and 250.")
    focus = focus.strip().casefold()
    nodes = {}
    edges: List[Dict[str, Any]] = []
    total = 0
    unstructured = 0
    for record in facts:
        if not isinstance(record, dict) or record.get("state") != "approved":
            continue
        if record.get("kind") != "relationship":
            continue
        subject = str(record.get("subject") or "").strip()
        target = str(record.get("related_to") or "").strip()
        kind = str(record.get("relation_type") or "").strip()
        if not subject or not target or not kind or subject.casefold() == target.casefold():
            unstructured += 1
            continue
        if focus and focus not in (subject.casefold(), target.casefold()):
            continue
        total += 1
        if len(edges) >= max_edges:
            continue
        for name in (subject, target):
            key = _node_id(name)
            if key not in nodes:
                nodes[key] = {
                    "id": key,
                    "name": name,
                    "degree": 0,
                }
            nodes[key]["degree"] += 1
        edges.append({
            "fact_id": str(record.get("id") or ""),
            "source": _node_id(subject),
            "target": _node_id(target),
            "source_name": subject,
            "target_name": target,
            "relation_type": kind,
            "claim": str(record.get("claim") or ""),
            "world_time": str(record.get("world_time") or ""),
            "narrative_order": str(record.get("narrative_order") or ""),
            "evidence": [
                {"source": str(e.get("source") or ""),
                 "quote": str(e.get("quote") or "")}
                for e in (record.get("evidence") or [])
                if isinstance(e, dict)
            ],
        })
    return {
        "ok": True,
        "nodes": sorted(nodes.values(), key=lambda item: item["name"].casefold()),
        "edges": edges,
        "edge_count": len(edges),
        "matching_edge_total": total,
        "truncated": total > len(edges),
        "unstructured_approved_relationships": unstructured,
        "focus": focus,
        "read_only": True,
        "note": (
            "Only explicitly linked, author-approved relationship facts are shown. "
            "Each edge retains its underlying claim and source. No inferred or "
            "proposed/rejected connections are drawn."
        ),
    }
