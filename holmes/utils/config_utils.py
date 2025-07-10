"""
Configuration utility functions for HolmesGPT.
"""

from typing import Any, Dict, List, Optional


def merge_transformer_configs(
    base_configs: Optional[List[Dict[str, Any]]],
    override_configs: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    """
    Merge transformer configurations with intelligent field-level merging.

    Logic:
    - Override configs take precedence for existing fields
    - Base configs provide missing fields
    - Merge at transformer-type level (e.g., "llm_summarize")

    Args:
        base_configs: Base configurations (e.g., global configs)
        override_configs: Override configurations (e.g., toolset configs)

    Returns:
        Merged configuration list or None if both inputs are None/empty
    """
    if not base_configs and not override_configs:
        return None
    if not base_configs:
        return override_configs
    if not override_configs:
        return base_configs

    # Convert lists to dicts keyed by transformer type for easier merging
    base_dict = {}
    for config in base_configs:
        for transformer_type, transformer_config in config.items():
            base_dict[transformer_type] = transformer_config

    override_dict = {}
    for config in override_configs:
        for transformer_type, transformer_config in config.items():
            override_dict[transformer_type] = transformer_config

    # Merge configurations at field level
    merged_dict = {}

    # Start with all base transformer types
    for transformer_type, base_config in base_dict.items():
        if transformer_type in override_dict:
            # Merge fields: override takes precedence, base provides missing fields
            merged_config = dict(base_config)  # Start with base
            merged_config.update(
                override_dict[transformer_type]
            )  # Override with specific fields
            merged_dict[transformer_type] = merged_config
        else:
            # No override, use base config as-is
            merged_dict[transformer_type] = base_config

    # Add any override-only transformer types
    for transformer_type, override_config in override_dict.items():
        if transformer_type not in merged_dict:
            merged_dict[transformer_type] = override_config

    # Convert back to list format
    return [
        {transformer_type: config} for transformer_type, config in merged_dict.items()
    ]
