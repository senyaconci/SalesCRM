"""Helpers for organizational relationship graphs."""

from __future__ import annotations

from org_intel.schemas.organization import OrganizationRelationshipGraph


def summarize_responsibilities(graph: OrganizationRelationshipGraph) -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {}
    for node in graph.nodes:
        for resp in node.capital_responsibilities:
            summary.setdefault(resp, []).append(node.name)
    graph.capital_responsibility_summary = summary
    return summary


def find_nodes_by_function(graph: OrganizationRelationshipGraph, function: str) -> list[str]:
    needle = function.lower()
    return [
        n.name
        for n in graph.nodes
        if (n.function and needle in n.function.lower())
        or any(needle in r.lower() for r in n.capital_responsibilities)
    ]
