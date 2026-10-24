"""Initialize and configure the global FormatRegistry with all available adapters."""

from __future__ import annotations

from poliglota.formats.arb import ARBFormatAdapter
from poliglota.formats.json import JSONFormatAdapter
from poliglota.formats.registry import FormatRegistry
from poliglota.formats.xml import XMLFormatAdapter
from poliglota.formats.yaml import YAMLFormatAdapter


def create_default_registry() -> FormatRegistry:
    """Create and populate a FormatRegistry with all standard adapters.
    
    Returns:
        A FormatRegistry instance with YAML, JSON, XML, and ARB adapters registered.
    """
    registry = FormatRegistry()
    
    # Register all format adapters
    registry.register(YAMLFormatAdapter())
    registry.register(JSONFormatAdapter())
    registry.register(XMLFormatAdapter())
    registry.register(ARBFormatAdapter())
    
    return registry


# Global singleton instance (lazy-loaded on first access)
_global_registry: FormatRegistry | None = None


def get_registry() -> FormatRegistry:
    """Get or create the global FormatRegistry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = create_default_registry()
    return _global_registry
