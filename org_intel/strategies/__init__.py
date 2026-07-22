"""Organization-type discovery strategies."""

from org_intel.strategies.base import OrganizationStrategy, get_strategy
from org_intel.strategies.registry import STRATEGY_REGISTRY

__all__ = ["OrganizationStrategy", "STRATEGY_REGISTRY", "get_strategy"]
