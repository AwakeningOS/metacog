"""
Utility functions for the awareness engine.
"""

import re

# Pattern to match tag prefixes like [残響], [余韻], [旋律]
TAG_PATTERN = re.compile(r'^\[(?:残響|余韻|旋律)\]\s*')


def strip_tags(content: str) -> str:
    """
    Remove all tag prefixes from content.

    Handles multiple stacked tags like "[旋律] [残響] text" → "text"
    """
    result = content
    while TAG_PATTERN.match(result):
        result = TAG_PATTERN.sub('', result)
    return result.strip()
