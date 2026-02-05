"""
Unified Memory System - Enhanced Version

高性能記憶システム:
- 日本語対応 Embedding (multilingual-e5-small)
- ハイブリッド検索 (セマンティック + キーワード)
- 拡張カテゴリシステム
- キーワード自動抽出

Consolidates ChromaDB + JSONL files for insights, thought logs, feedback.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# ========== カテゴリ定義 ==========

CATEGORIES = {
    "user_info": "ユーザーの名前、年齢、職業、属性などのプロフィール情報",
    "preference": "好み、嗜好、趣味、好きなもの・嫌いなもの",
    "episode": "出来事、エピソード、思い出、過去の会話の内容",
    "instruction": "ユーザーからの指示、ルール、お願い",
    "fact": "事実情報、知識、学んだこと",
    "insight": "気づき、洞察、発見",
    "dream_insight": "Dreamingエンジンからの洞察",
    "voluntary": "その他の自発的な記憶",
}


def extract_keywords(content: str) -> list[str]:
    """
    日本語・英語テキストからキーワードを抽出
    """
    keywords = set()

    # カタカナ（2文字以上）
    katakana = re.findall(r'[\u30A0-\u30FF]{2,}', content)
    keywords.update(katakana)

    # 漢字（2文字以上）
    kanji = re.findall(r'[\u4E00-\u9FFF]{2,}', content)
    keywords.update(kanji)

    # 英単語（3文字以上）
    english = re.findall(r'[a-zA-Z]{3,}', content)
    keywords.update([w.lower() for w in english])

    # ひらがな+漢字の混合語
    mixed = re.findall(r'[\u3040-\u309F\u4E00-\u9FFF]{2,}', content)
    keywords.update(mixed)

    # 数字を含む重要語
    with_numbers = re.findall(r'[\w]+\d+[\w]*|[\d]+[\w]+', content)
    keywords.update(with_numbers)

    return list(keywords)[:20]


class UnifiedMemory:
    """Enhanced memory system for the Awareness Engine"""

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

        # 日本語対応 Embedding モデル
        self.embedding_function = None
        try:
            from chromadb.utils import embedding_functions
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="intfloat/multilingual-e5-small"
            )
            logger.info("Using multilingual-e5-small embedding model")
        except Exception as e:
            logger.warning(f"Failed to load multilingual model: {e}")

        # コレクション作成
        if self.embedding_function:
            self.collection = self.client.get_or_create_collection(
                name="awareness_memory_v2",
                embedding_function=self.embedding_function,
                metadata={
                    "hnsw:space": "cosine",
                    "description": "Enhanced memory with multilingual support"
                }
            )
        else:
            self.collection = self.client.get_or_create_collection(
                name="awareness_memory_v2",
                metadata={
                    "hnsw:space": "cosine",
                    "description": "Enhanced memory system"
                }
            )

        # File paths
        self.insights_file = self.data_dir / "insights.jsonl"
        self.thought_logs_file = self.data_dir / "thought_logs.jsonl"
        self.feedback_file = self.data_dir / "feedback.jsonl"

        # RAM cache for insights
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
        Save content to ChromaDB with enhanced metadata
        Format: [カテゴリ] 内容
        """
        if category not in CATEGORIES:
            logger.warning(f"Unknown category '{category}', using 'voluntary'")
            category = "voluntary"

        # [カテゴリ] 内容 形式で統一保存
        formatted_content = f"[{category}] {content}"

        # キーワード抽出（元のcontentから）
        keywords = extract_keywords(content)
        keywords_str = ",".join(keywords)

        memory_id = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # E5モデル用プレフィックス
        embed_content = f"passage: {formatted_content}" if self.embedding_function else formatted_content

        doc_metadata = {
            "category": category,
            "keywords": keywords_str,
            "original_content": formatted_content,
            "user_id": "global",
            "created_at": datetime.now().isoformat(),
        }
        if metadata:
            doc_metadata.update(metadata)

        self.collection.add(
            ids=[memory_id],
            documents=[embed_content],
            metadatas=[doc_metadata]
        )

        logger.debug(f"Saved memory: {formatted_content[:80]}... | keywords: {keywords_str[:50]}")
        return memory_id

    def search(
        self,
        query: str = "",
        limit: int = 8,
        category: Optional[str] = None
    ) -> list[dict]:
        """
        Hybrid search: semantic + keyword matching
        """
        results = []
        seen_ids = set()

        # === 1. カテゴリ指定のみ（クエリなし）===
        if category and not query.strip():
            try:
                filtered = self.collection.get(
                    where={"category": category},
                    limit=limit
                )
                if filtered["ids"]:
                    for i, doc_id in enumerate(filtered["ids"]):
                        meta = filtered["metadatas"][i] if filtered["metadatas"] else {}
                        # original_content があればそれを使用
                        content = meta.get("original_content", filtered["documents"][i])
                        results.append({
                            "id": doc_id,
                            "content": content,
                            "category": meta.get("category", ""),
                            "keywords": meta.get("keywords", ""),
                            "relevance": 0.8,
                            "match_type": "category_filter",
                        })
            except Exception as e:
                logger.warning(f"Category search failed: {e}")
            return results

        # === 2. セマンティック検索 ===
        if query.strip():
            search_query = f"query: {query}" if self.embedding_function else query
            where_filter = {"category": category} if category else None

            try:
                semantic_results = self.collection.query(
                    query_texts=[search_query],
                    n_results=min(limit * 2, 20),
                    where=where_filter
                )

                if semantic_results["documents"] and semantic_results["documents"][0]:
                    for i, doc in enumerate(semantic_results["documents"][0]):
                        doc_id = semantic_results["ids"][0][i]
                        if doc_id in seen_ids:
                            continue
                        seen_ids.add(doc_id)

                        distance = semantic_results["distances"][0][i] if semantic_results["distances"] else 0
                        meta = semantic_results["metadatas"][0][i] if semantic_results["metadatas"] else {}

                        # コサイン距離 → 類似度
                        relevance = max(0, 1.0 - distance)

                        if relevance >= 0.3:
                            content = meta.get("original_content", doc)
                            results.append({
                                "id": doc_id,
                                "content": content,
                                "category": meta.get("category", ""),
                                "keywords": meta.get("keywords", ""),
                                "relevance": round(relevance, 3),
                                "match_type": "semantic",
                            })
            except Exception as e:
                logger.warning(f"Semantic search failed: {e}")

        # === 3. キーワード検索 ===
        if query.strip():
            try:
                all_docs = self.collection.get(limit=1000)
                query_lower = query.lower()
                query_keywords = extract_keywords(query)

                for i, doc in enumerate(all_docs["documents"]):
                    doc_id = all_docs["ids"][i]
                    if doc_id in seen_ids:
                        continue

                    meta = all_docs["metadatas"][i] if all_docs["metadatas"] else {}

                    if category and meta.get("category") != category:
                        continue

                    # original_content を使用
                    original = meta.get("original_content", doc)
                    doc_lower = original.lower()
                    doc_keywords = meta.get("keywords", "").lower()

                    match_score = 0

                    if query_lower in doc_lower:
                        match_score = 0.9
                    elif query in original:
                        match_score = 0.85

                    if query_lower in doc_keywords:
                        match_score = max(match_score, 0.85)

                    for kw in query_keywords:
                        if kw in doc_lower or kw in doc_keywords:
                            match_score = max(match_score, 0.7)
                            break

                    if match_score > 0:
                        seen_ids.add(doc_id)
                        results.append({
                            "id": doc_id,
                            "content": original,
                            "category": meta.get("category", ""),
                            "keywords": meta.get("keywords", ""),
                            "relevance": match_score,
                            "match_type": "keyword",
                        })
            except Exception as e:
                logger.warning(f"Keyword search failed: {e}")

        # === 4. ソートして返却 ===
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:limit]

    def count(self, category: Optional[str] = None) -> int:
        """Count memories, optionally filtered by category"""
        if category:
            try:
                results = self.collection.get(where={"category": category})
                return len(results["ids"])
            except Exception:
                return 0
        return self.collection.count()

    def get_categories(self) -> dict:
        """Get available categories with descriptions"""
        return CATEGORIES.copy()

    def get_category_counts(self) -> dict:
        """Get count for each category"""
        counts = {}
        for cat in CATEGORIES.keys():
            counts[cat] = self.count(cat)
        return counts

    def count_by_source(self, source: str) -> int:
        """Count memories by source (e.g., 'mcp_tool', 'dreaming', 'response')"""
        try:
            results = self.collection.get(where={"source": source})
            return len(results["ids"])
        except Exception:
            return 0

    def get_llm_memory_count(self) -> int:
        """Count memories saved by LLM via MCP (voluntary memories)"""
        return self.count_by_source("mcp_tool")

    # ========== Insights ==========

    def save_insight(self, insight_text: str, source: str = "response") -> str:
        """Save an insight to both ChromaDB and insights.jsonl"""
        # save() が [category] プレフィックスを付けるので、ここでは内容のみ渡す
        memory_id = self.save(
            content=insight_text,
            category="insight",
            metadata={"source": source}
        )

        entry = {
            "timestamp": datetime.now().isoformat(),
            "insight": insight_text,
            "source": source,
        }
        self._append_jsonl(self.insights_file, entry)
        self._cache_dirty = True

        return memory_id

    def get_insights(self, limit: int = 10) -> list[dict]:
        """Get recent insights from insights.jsonl"""
        if self._cache_dirty:
            self._insight_cache = self._read_jsonl(self.insights_file)
            self._cache_dirty = False
        return self._insight_cache[-limit:]

    def get_all_insights(self) -> list[dict]:
        """Get all insights"""
        return self._read_jsonl(self.insights_file)

    # ========== Feedback ==========

    def save_feedback(self, feedback: str, context: Optional[dict] = None) -> bool:
        """Save user feedback"""
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
        """Save a thinking step log"""
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
        all_results = self.collection.get()
        all_memories = []
        if all_results["ids"]:
            for i, doc in enumerate(all_results["documents"]):
                meta = all_results["metadatas"][i] if all_results["metadatas"] else {}
                content = meta.get("original_content", doc)
                all_memories.append({
                    "id": all_results["ids"][i],
                    "content": content,
                    "category": meta.get("category", "unknown"),
                    "keywords": meta.get("keywords", ""),
                    "created_at": meta.get("created_at", ""),
                })

        return {
            "memories": all_memories,
            "feedback": self.get_feedback(),
            "insights": self.get_all_insights(),
            "thought_logs": self.get_thought_logs(limit=20),
            "total_memory_count": len(all_memories),
            "category_counts": self.get_category_counts(),
        }

    def archive_insights(self, new_insights: list[dict]):
        """Archive current insights and replace with new ones"""
        old_insights = self.get_all_insights()
        if old_insights:
            archive_file = self.insights_file.with_suffix(".archived.jsonl")
            timestamp = datetime.now().isoformat()
            for entry in old_insights:
                entry["archived_at"] = timestamp
                self._append_jsonl(archive_file, entry)

        with open(self.insights_file, "w", encoding="utf-8") as f:
            for insight in new_insights:
                f.write(json.dumps(insight, ensure_ascii=False) + "\n")

        self._cache_dirty = True
        logger.info(f"Archived {len(old_insights)} old insights, saved {len(new_insights)} new")

    def archive_feedback(self):
        """Archive processed feedback"""
        feedbacks = self.get_feedback()
        if not feedbacks or not self.feedback_file.exists():
            return 0

        archive_file = self.feedback_file.with_suffix(".archived.jsonl")
        timestamp = datetime.now().isoformat()
        for fb in feedbacks:
            fb["archived_at"] = timestamp
            self._append_jsonl(archive_file, fb)

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

        # ChromaDB: delete all
        try:
            all_ids = self.collection.get()["ids"]
            if all_ids:
                self.collection.delete(ids=all_ids)
                result["chromadb_deleted"] = len(all_ids)
        except Exception as e:
            logger.error(f"Failed to reset ChromaDB: {e}")

        # JSONL files: clear
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
