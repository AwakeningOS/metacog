"""
System Prompt Builder

Returns the base system prompt (dynamically loaded from config).
Memory injection is handled by core.py via _build_input_with_context().
"""

import logging

from config.default_config import load_config, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class SystemPromptBuilder:
    """Build system prompt (base prompt only)"""

    def __init__(self, config: dict):
        self.config = config

    def build(self) -> str:
        """Return the base system prompt (loaded fresh from config each time)."""
        config = load_config()
        return config.get("system_prompt", SYSTEM_PROMPT)
