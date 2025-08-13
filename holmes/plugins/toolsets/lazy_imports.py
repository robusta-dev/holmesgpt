"""Lazy import utilities for expensive toolset modules."""

import importlib.util
import sys
from typing import Any


def lazy_import(name: str) -> Any:
    """
    Lazily import a module using importlib.util.LazyLoader.

    Args:
        name: The module name to import (e.g., 'azure.identity')

    Returns:
        The lazily loaded module
    """
    # Check if already imported
    if name in sys.modules:
        return sys.modules[name]

    spec = importlib.util.find_spec(name)
    if spec is None:
        raise ImportError(f"Module {name} not found")

    if spec.loader is None:
        raise ImportError(f"Module {name} has no loader")

    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)

    return module


# Pre-configured lazy imports for common expensive modules
def get_azure_identity():
    """Get azure.identity module lazily."""
    return lazy_import("azure.identity")


def get_beautifulsoup():
    """Get bs4 module lazily."""
    return lazy_import("bs4")


def get_markdownify():
    """Get markdownify module lazily."""
    return lazy_import("markdownify")


def get_mcp_client():
    """Get MCP client modules lazily."""
    return {
        "session": lazy_import("mcp.client.session"),
        "sse": lazy_import("mcp.client.sse"),
        "types": lazy_import("mcp.types"),
    }


def get_opensearch():
    """Get opensearchpy module lazily."""
    return lazy_import("opensearchpy")


def get_kubernetes():
    """Get kubernetes modules lazily."""
    return {
        "client": lazy_import("kubernetes.client"),
        "config": lazy_import("kubernetes.config"),
    }


def get_requests():
    """Get requests module lazily."""
    return lazy_import("requests")
