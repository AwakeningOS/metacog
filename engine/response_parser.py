"""
Response Parser

Splits LLM output into three parts:
1. Response text — returned to the user
2. Insights — extracted from "## 気づき" section, saved to memory
3. Voluntary saves — lines starting with [SAVE], saved to ChromaDB

The LLM is instructed (via system prompt) to write:
  <response text>
  ---
  ## 気づき
  - insight 1
  - insight 2
  - [SAVE] memory to save
"""

import logging

logger = logging.getLogger(__name__)


class ResponseParser:
    """Parse LLM output into response + insights + voluntary memories"""

    # Markers
    INSIGHT_HEADER = "## 気づき"
    SAVE_MARKER = "[SAVE]"
    SEPARATOR = "---"

    def parse(self, raw_output: str) -> dict:
        """
        Parse raw LLM output.

        Returns:
            {
                "response": str,        # Main response text for user
                "insights": list[str],  # Extracted insight texts
                "saves": list[str],     # Voluntary memory items
                "raw": str,             # Original unmodified output
            }
        """
        if not raw_output:
            return {
                "response": "",
                "insights": [],
                "saves": [],
                "raw": "",
            }

        response = raw_output
        insights = []
        saves = []

        # Split on "## 気づき" header
        if self.INSIGHT_HEADER in raw_output:
            parts = raw_output.split(self.INSIGHT_HEADER, 1)

            # Clean up response: remove trailing "---" separator
            response = parts[0].rstrip()
            if response.endswith(self.SEPARATOR):
                response = response[:-len(self.SEPARATOR)].rstrip()

            # Parse insight section
            insight_section = parts[1]
            for line in insight_section.strip().split("\n"):
                line = line.strip()

                # Remove list markers
                if line.startswith("- "):
                    line = line[2:].strip()
                elif line.startswith("* "):
                    line = line[2:].strip()

                if not line:
                    continue

                # Check for [SAVE] markers
                if line.upper().startswith(self.SAVE_MARKER):
                    save_content = line[len(self.SAVE_MARKER):].strip()
                    if save_content:
                        saves.append(save_content)
                        logger.debug(f"Extracted [SAVE]: {save_content[:60]}...")
                elif len(line) > 5:
                    # Only include substantial insights (not noise)
                    insights.append(line)

        if insights:
            logger.info(f"Parsed: {len(insights)} insights, {len(saves)} saves")

        return {
            "response": response,
            "insights": insights,
            "saves": saves,
            "raw": raw_output,
        }
