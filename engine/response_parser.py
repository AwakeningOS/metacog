"""
Response Parser

Splits LLM output into:
1. Response text — returned to the user
2. Voluntary saves — lines starting with [SAVE], saved to ChromaDB

Observation/Seed generation is handled by separate API calls in core.py.
"""

import logging

logger = logging.getLogger(__name__)


class ResponseParser:
    """Parse LLM output into response + voluntary memories"""

    SAVE_MARKER = "[SAVE]"

    def parse(self, raw_output: str) -> dict:
        """
        Parse raw LLM output.

        Returns:
            {
                "response": str,
                "saves": list[str],
                "raw": str,
            }
        """
        if not raw_output:
            return {
                "response": "",
                "saves": [],
                "raw": "",
            }

        response = raw_output
        saves = []

        # Extract [SAVE] markers from response
        lines = raw_output.split("\n")
        clean_lines = []

        for line in lines:
            stripped = line.strip()
            # Remove list markers for checking
            check_line = stripped
            if check_line.startswith("- "):
                check_line = check_line[2:].strip()
            elif check_line.startswith("* "):
                check_line = check_line[2:].strip()

            # Check for [SAVE] markers
            if check_line.upper().startswith(self.SAVE_MARKER):
                save_content = check_line[len(self.SAVE_MARKER):].strip()
                if save_content:
                    saves.append(save_content)
                    logger.debug(f"Extracted [SAVE]: {save_content[:60]}...")
            else:
                clean_lines.append(line)

        response = "\n".join(clean_lines).strip()

        if saves:
            logger.info(f"Parsed: {len(saves)} saves")

        return {
            "response": response,
            "saves": saves,
            "raw": raw_output,
        }
