"""Discover procurement portals from the source registry."""

from __future__ import annotations

from org_intel.schemas.enums import SourceRole
from org_intel.schemas.source import SourceRecord, SourceRegistry

PROCUREMENT_ROLES = {
    SourceRole.PROCUREMENT_PAGE,
    SourceRole.BID_PORTAL,
    SourceRole.DEMANDSTAR,
    SourceRole.BONFIRE,
    SourceRole.PLANETBIDS,
    SourceRole.IONWAVE,
    SourceRole.OPENGOV_PROCUREMENT,
    SourceRole.BIDNET,
    SourceRole.STATE_PROCUREMENT,
}


def discover_procurement_portals(registry: SourceRegistry) -> list[SourceRecord]:
    return [s for s in registry.sources if s.source_role in PROCUREMENT_ROLES]
