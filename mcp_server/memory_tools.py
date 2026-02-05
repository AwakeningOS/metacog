"""
Memory Tools MCP Server

Simple MCP server providing memory search and save tools.
LLM decides when to use these tools during conversation.

Launched by LM Studio as a child process via mcp.json.
Receives: sys.argv[1] = data directory
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Fix encoding for Windows stderr
if sys.platform == "win32":
    import io
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [memory-tools] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ========== MCP Server ==========

mcp = FastMCP("memory-tools")

# ========== Global State ==========

_initialized = False
_data_dir: Optional[Path] = None
_chromadb_collection = None


# ========== Initialization ==========

def _ensure_initialized():
    """Lazy initialization — called on first tool invocation"""
    global _initialized, _data_dir, _chromadb_collection

    if _initialized:
        return

    # Parse args: data_dir
    if len(sys.argv) > 1:
        _data_dir = Path(sys.argv[1])
    else:
        _data_dir = Path("./data")

    _data_dir.mkdir(parents=True, exist_ok=True)

    # Connect to shared ChromaDB
    chromadb_dir = _data_dir / "chromadb"
    if chromadb_dir.exists():
        try:
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=str(chromadb_dir),
                settings=Settings(anonymized_telemetry=False)
            )
            _chromadb_collection = client.get_or_create_collection(
                name="awareness_memory"
            )
            count = _chromadb_collection.count()
            logger.info(f"ChromaDB connected: {count} memories")
        except Exception as e:
            logger.warning(f"ChromaDB unavailable: {e}")
            _chromadb_collection = None
    else:
        chromadb_dir.mkdir(parents=True, exist_ok=True)
        try:
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=str(chromadb_dir),
                settings=Settings(anonymized_telemetry=False)
            )
            _chromadb_collection = client.get_or_create_collection(
                name="awareness_memory"
            )
            logger.info("ChromaDB initialized (new)")
        except Exception as e:
            logger.warning(f"ChromaDB init failed: {e}")
            _chromadb_collection = None

    _initialized = True
    logger.info(f"Memory Tools Server initialized. data_dir={_data_dir}")


# ========== Tools ==========

@mcp.tool()
def search_memory(query: str, limit: int = 5) -> dict:
    """Search past memories by semantic similarity.

    Use this when:
    - User references past conversations ("前に話した...", "以前の...")
    - You need context from previous interactions
    - Topic requires historical knowledge

    Do NOT use for:
    - Simple greetings or casual chat
    - Questions that don't need past context

    Args:
        query: Search query (topic, keyword, or question)
        limit: Maximum results (default 5)

    Returns:
        List of relevant memories with content and category
    """
    _ensure_initialized()

    if _chromadb_collection is None:
        return {"status": "error", "message": "Memory system unavailable", "memories": []}

    if not query.strip():
        return {"status": "error", "message": "Empty query", "memories": []}

    try:
        results = _chromadb_collection.query(
            query_texts=[query],
            n_results=min(limit, 10)  # Cap at 10
        )

        memories = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i] if results["distances"] else None
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}

                # Filter out very distant results
                if distance is not None and distance > 1.5:
                    continue

                memories.append({
                    "content": doc,
                    "category": metadata.get("category", "unknown"),
                    "relevance": round(1.0 - (distance / 2.0), 3) if distance else None,
                })

        logger.info(f"search_memory('{query[:50]}...'): {len(memories)} results")
        return {
            "status": "ok",
            "query": query,
            "count": len(memories),
            "memories": memories,
        }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"status": "error", "message": str(e), "memories": []}


@mcp.tool()
def save_memory(content: str, category: str = "voluntary") -> dict:
    """Save important information to long-term memory.

    Use this when:
    - User shares important personal information
    - A significant insight emerges from conversation
    - Information should be remembered for future sessions

    Do NOT use for:
    - Trivial or temporary information
    - General knowledge (you already know it)

    Args:
        content: The information to remember
        category: Type of memory (voluntary, insight)

    Returns:
        Status of save operation
    """
    _ensure_initialized()

    if _chromadb_collection is None:
        return {"status": "error", "message": "Memory system unavailable"}

    if not content.strip():
        return {"status": "error", "message": "Empty content"}

    # Validate category
    valid_categories = ["voluntary", "insight"]
    if category not in valid_categories:
        category = "voluntary"

    try:
        memory_id = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        _chromadb_collection.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[{
                "category": category,
                "user_id": "global",
                "created_at": datetime.now().isoformat(),
                "source": "mcp_tool",
            }]
        )

        logger.info(f"save_memory[{category}]: {content[:80]}...")
        return {
            "status": "ok",
            "memory_id": memory_id,
            "content": content[:100] + "..." if len(content) > 100 else content,
        }

    except Exception as e:
        logger.error(f"Save failed: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def memory_stats() -> dict:
    """Get current memory statistics.

    Use this to check memory system status.
    """
    _ensure_initialized()

    if _chromadb_collection is None:
        return {"status": "error", "message": "Memory system unavailable"}

    try:
        total = _chromadb_collection.count()

        # Count by category
        categories = {}
        for cat in ["voluntary", "insight", "dream_insight"]:
            try:
                results = _chromadb_collection.get(where={"category": cat})
                categories[cat] = len(results["ids"])
            except:
                categories[cat] = 0

        return {
            "status": "ok",
            "total_memories": total,
            "by_category": categories,
        }

    except Exception as e:
        logger.error(f"Stats failed: {e}")
        return {"status": "error", "message": str(e)}


# ========== Entry Point ==========

if __name__ == "__main__":
    logger.info("Starting Memory Tools MCP Server...")
    _ensure_initialized()
    logger.info("Starting MCP transport...")
    mcp.run(transport="stdio")
