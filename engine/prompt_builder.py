"""
System Prompt Builder

Returns the base system prompt (fixed).
Memory injection is handled by core.py via _build_input_with_context().
"""

import logging

logger = logging.getLogger(__name__)


class SystemPromptBuilder:
    """Build system prompt (base prompt only)"""

    def __init__(self, config: dict):
        self.config = config
        self.base_prompt = config.get("system_prompt", "")

    def build(self) -> str:
        """Return the base system prompt."""
        return self.base_prompt
