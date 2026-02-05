"""
Unified Memory System
- ChromaDB for persistent vector memory (semantic search)
- JSONL files for insights, thought logs, feedback
- RAM cache for frequently accessed data

Consolidates the previous project's 3 memory systems
(ChromaDB + SimpleMemory + MCP Memory) into one.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class UnifiedMemory:
    """Single memory system for the Awareness Engine"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ChromaDB persistent client
        chromadb_dir = self.data_dir / "chromadb"
        chromadb_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(chromadb_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="awareness_memory",
            metadata={"description": "Unified awareness engine memory"}
        )

        # File paths
        self.insights_file = self.data_dir / "insights.jsonl"
        self.thought_logs_file = self.data_dir / "thought_logs.jsonl"
        self.feedback_file = self.data_dir / "feedback.jsonl"

        # RAM cache for insights (avoid repeated file reads)
        self._insight_cache: list[dict] = []
        self._cache_dirty: bool = True

        logger.info(f"UnifiedMemory initialized: {self.data_dir}")

    # ========== Core Operations ==========

    def save(
        self,
        content: str,
        category: str,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save content to ChromaDB with semantic indexing.

        Categories: insight, voluntary, dream_insight
        """
        memory_id = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        doc_metadata = {
            "category": category,
            "user_id": "global",
            "created_at": datetime.now().isoformat(),
        }
        if metadata:
            doc_metadata.update(metadata)

        self.collection.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[doc_metadata]
        )

        logger.debug(f"Saved memory [{category}]: {content[:80]}...")
        return memory_id

    def search(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None
    ) -> list[dict]:
        """
        Semantic similarity search via ChromaDB.
        Returns list of {id, content, category, distance}
        """
        where_filter = None
        if category:
            where_filter = {"category": category}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_filter
            )
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")
            return []

        memories = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results["distances"] else None
                memories.append({
                    "id": results["ids"][0][i],
                    "content": doc,
                    "category": meta.get("category", ""),
                    "distance": dist,
                })

        return memories

    def count(self, category: Optional[str] = None) -> int:
        """Count memories, optionally filtered by category"""
        if category:
            try:
                results = self.collection.get(where={"category": category})
                return len(results["ids"])
            except Exception:
                return 0
        return self.collection.count()

    # ========== Insights ==========

    def save_insight(self, insight_text: str, source: str = "response") -> str:
        """Save an insight to both ChromaDB and insights.jsonl"""
        # ChromaDB (for semantic search)
        memory_id = self.save(
            content=f"[Insight] {insight_text}",
            category="insight",
            metadata={"source": source}
        )

        # JSONL file (for dreaming engine)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "insight": insight_text,
            "source": source,
        }
        self._append_jsonl(self.insights_file, entry)
        self._cache_dirty = True

        return memory_id

    def get_insights(self, limit: int = 10) -> list[dict]:
        """Get recent insights from insights.jsonl (cached in RAM)"""
        if self._cache_dirty:
            self._insight_cache = self._read_jsonl(self.insights_file)
            self._cache_dirty = False
        return self._insight_cache[-limit:]

    def get_all_insights(self) -> list[dict]:
        """Get all insights (for dreaming)"""
        return self._read_jsonl(self.insights_file)

    # ========== Feedback ==========

    def save_feedback(self, feedback: str, context: Optional[dict] = None) -> bool:
        """Save user feedback (highest priority in dreaming)"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback,
            "context": context or {},
        }
        try:
            self._append_jsonl(self.feedback_file, entry)
            logger.info(f"Feedback saved: {feedback[:80]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
            return False

    def get_feedback(self, limit: int = 10) -> list[dict]:
        """Get recent feedback entries"""
        return self._read_jsonl(self.feedback_file)[-limit:]

    # ========== Thought Logs ==========

    def save_thought_log(
        self,
        step: str,
        thought: str,
        memories_found: int = 0,
        extra: Optional[dict] = None
    ):
        """Save a thinking step log (from MCP server)"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "thought": thought,
            "memories_found": memories_found,
        }
        if extra:
            entry.update(extra)
        self._append_jsonl(self.thought_logs_file, entry)

    def get_thought_logs(self, limit: int = 20) -> list[dict]:
        """Get recent thought logs"""
        return self._read_jsonl(self.thought_logs_file)[-limit:]

    # ========== Dreaming Support ==========

    def export_for_dreaming(self) -> dict:
        """Export all data for the dreaming engine"""
        # ChromaDB memories (all categories)
        all_results = self.collection.get()
        all_memories = []
        if all_results["ids"]:
            for i, doc in enumerate(all_results["documents"]):
                meta = all_results["metadatas"][i] if all_results["metadatas"] else {}
                all_memories.append({
                    "id": all_results["ids"][i],
                    "content": doc,
                    "category": meta.get("category", "unknown"),
                    "created_at": meta.get("created_at", ""),
                })

        return {
            "memories": all_memories,
            "feedback": self.get_feedback(),
            "insights": self.get_all_insights(),
            "thought_logs": self.get_thought_logs(limit=20),
            "total_memory_count": len(all_memories),
        }

    def archive_insights(self, new_insights: list[dict]):
        """Archive current insights and replace with new ones (dream cycle)"""
        # Archive old insights
        old_insights = self.get_all_insights()
        if old_insights:
            archive_file = self.insights_file.with_suffix(".archived.jsonl")
            timestamp = datetime.now().isoformat()
            for entry in old_insights:
                entry["archived_at"] = timestamp
                self._append_jsonl(archive_file, entry)

        # Overwrite with new insights
        with open(self.insights_file, "w", encoding="utf-8") as f:
            for insight in new_insights:
                f.write(json.dumps(insight, ensure_ascii=False) + "\n")

        self._cache_dirty = True
        logger.info(f"Archived {len(old_insights)} old insights, saved {len(new_insights)} new")

    def archive_feedback(self):
        """Archive processed feedback (after dreaming)"""
        feedbacks = self.get_feedback()
        if not feedbacks or not self.feedback_file.exists():
            return 0

        archive_file = self.feedback_file.with_suffix(".archived.jsonl")
        timestamp = datetime.now().isoformat()
        for fb in feedbacks:
            fb["archived_at"] = timestamp
            self._append_jsonl(archive_file, fb)

        # Clear feedback file
        self.feedback_file.write_text("")
        logger.info(f"Archived {len(feedbacks)} feedbacks")
        return len(feedbacks)

    def batch_delete(self, memory_ids: list[str]) -> dict:
        """Delete multiple memories from ChromaDB"""
        deleted = 0
        failed = []
        for mid in memory_ids:
            try:
                self.collection.delete(ids=[mid])
                deleted += 1
            except Exception as e:
                failed.append({"id": mid, "error": str(e)})
        return {"deleted_count": deleted, "failed_count": len(failed)}

    # ========== File Utilities ==========

    def _append_jsonl(self, filepath: Path, data: dict):
        """Append a JSON line to a file"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _read_jsonl(self, filepath: Path) -> list[dict]:
        """Read all entries from a JSONL file"""
        entries = []
        if not filepath.exists():
            return entries
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning(f"Failed to read {filepath}: {e}")
        return entries

    # ========== Reset ==========

    def reset_all(self) -> dict:
        """Delete all memories, insights, feedback, thought logs"""
        result = {
            "chromadb_deleted": 0,
            "insights_deleted": 0,
            "feedback_deleted": 0,
            "thought_logs_deleted": 0,
        }

        # ChromaDB: delete all documents
        try:
            all_ids = self.collection.get()["ids"]
            if all_ids:
                self.collection.delete(ids=all_ids)
                result["chromadb_deleted"] = len(all_ids)
        except Exception as e:
            logger.error(f"Failed to reset ChromaDB: {e}")

        # JSONL files: clear contents
        for name, filepath in [
            ("insights", self.insights_file),
            ("feedback", self.feedback_file),
            ("thought_logs", self.thought_logs_file),
        ]:
            if filepath.exists():
                try:
                    count = len(self._read_jsonl(filepath))
                    filepath.write_text("")
                    result[f"{name}_deleted"] = count
                except Exception as e:
                    logger.error(f"Failed to reset {name}: {e}")

        self._cache_dirty = True
        logger.info(f"Memory reset complete: {result}")
        return result
