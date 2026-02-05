"""
Memory Tools MCP Server - Enhanced Version

高性能記憶システム:
- 日本語対応 Embedding (multilingual-e5-small)
- ハイブリッド検索 (セマンティック + キーワード)
- 拡張カテゴリシステム
- キーワード自動抽出

Launched by LM Studio as a child process via mcp.json.
Receives: sys.argv[1] = data directory
"""

import json
import logging
import re
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
_embedding_function = None

# ========== カテゴリ定義 ==========

CATEGORIES = {
    "user_info": "ユーザーの名前、年齢、職業、属性などのプロフィール情報",
    "preference": "好み、嗜好、趣味、好きなもの・嫌いなもの",
    "episode": "出来事、エピソード、思い出、過去の会話の内容",
    "instruction": "ユーザーからの指示、ルール、お願い",
    "fact": "事実情報、知識、学んだこと",
    "insight": "気づき、洞察、発見",
    "voluntary": "その他の自発的な記憶",
}

# ========== キーワード抽出 ==========

def extract_keywords(content: str) -> list[str]:
    """
    日本語・英語テキストからキーワードを抽出
    - カタカナ語（2文字以上）
    - 漢字語（2文字以上）
    - 英単語（3文字以上）
    - 数字を含む語
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

    # ひらがな+漢字の混合語（名前など）
    mixed = re.findall(r'[\u3040-\u309F\u4E00-\u9FFF]{2,}', content)
    keywords.update(mixed)

    # 数字を含む重要語
    with_numbers = re.findall(r'[\w]+\d+[\w]*|[\d]+[\w]+', content)
    keywords.update(with_numbers)

    return list(keywords)[:20]  # 最大20個


# ========== Initialization ==========

def _ensure_initialized():
    """Lazy initialization — called on first tool invocation"""
    global _initialized, _data_dir, _chromadb_collection, _embedding_function

    if _initialized:
        return

    # Parse args: data_dir
    if len(sys.argv) > 1:
        _data_dir = Path(sys.argv[1])
    else:
        _data_dir = Path("./data")

    _data_dir.mkdir(parents=True, exist_ok=True)
    chromadb_dir = _data_dir / "chromadb"
    chromadb_dir.mkdir(parents=True, exist_ok=True)

    try:
        import chromadb
        from chromadb.config import Settings

        # 日本語対応 Embedding モデル
        try:
            from chromadb.utils import embedding_functions
            _embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="intfloat/multilingual-e5-small"
            )
            logger.info("Using multilingual-e5-small embedding model")
        except Exception as e:
            logger.warning(f"Failed to load multilingual model, using default: {e}")
            _embedding_function = None

        client = chromadb.PersistentClient(
            path=str(chromadb_dir),
            settings=Settings(anonymized_telemetry=False)
        )

        # コレクション作成（カスタム Embedding 使用）
        if _embedding_function:
            _chromadb_collection = client.get_or_create_collection(
                name="awareness_memory_v2",
                embedding_function=_embedding_function,
                metadata={
                    "hnsw:space": "cosine",  # コサイン類似度を使用
                    "description": "Enhanced memory with multilingual support"
                }
            )
        else:
            _chromadb_collection = client.get_or_create_collection(
                name="awareness_memory_v2",
                metadata={
                    "hnsw:space": "cosine",
                    "description": "Enhanced memory system"
                }
            )

        count = _chromadb_collection.count()
        logger.info(f"ChromaDB connected: {count} memories")

    except Exception as e:
        logger.error(f"ChromaDB init failed: {e}")
        _chromadb_collection = None

    _initialized = True
    logger.info(f"Memory Tools Server initialized. data_dir={_data_dir}")


# ========== Tools ==========

@mcp.tool()
def search_memory(
    query: str = "",
    category: str = "",
    limit: int = 8
) -> dict:
    """
    記憶をハイブリッド検索（セマンティック + キーワード）

    使用場面:
    - 会話開始時にユーザー情報を取得: search_memory("", category="user_info")
    - 過去の会話を思い出す: search_memory("チョコレートケーキ")
    - 好みを確認: search_memory("好き", category="preference")

    Args:
        query: 検索クエリ（空でもOK、カテゴリのみ検索可能）
        category: カテゴリフィルタ (user_info, preference, episode, instruction, fact, insight, voluntary)
        limit: 最大結果数 (default: 8)

    Returns:
        検索結果リスト（relevance順）
    """
    _ensure_initialized()

    if _chromadb_collection is None:
        return {"status": "error", "message": "Memory system unavailable", "memories": []}

    results = []
    seen_ids = set()

    try:
        # === 1. カテゴリ指定のみ（クエリなし）の場合は全件取得 ===
        if category and not query.strip():
            filtered = _chromadb_collection.get(
                where={"category": category},
                limit=limit
            )
            if filtered["ids"]:
                for i, doc_id in enumerate(filtered["ids"]):
                    if doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        meta = filtered["metadatas"][i] if filtered["metadatas"] else {}
                        results.append({
                            "content": filtered["documents"][i],
                            "category": meta.get("category", "unknown"),
                            "keywords": meta.get("keywords", ""),
                            "relevance": 0.8,  # カテゴリ完全一致
                            "match_type": "category_filter",
                            "created_at": meta.get("created_at", ""),
                        })
            logger.info(f"search_memory(category='{category}'): {len(results)} results")
            return {"status": "ok", "query": "", "category": category, "count": len(results), "memories": results}

        # === 2. セマンティック検索 ===
        if query.strip():
            # E5モデル用のプレフィックス追加
            search_query = f"query: {query}" if _embedding_function else query

            where_filter = {"category": category} if category else None

            semantic_results = _chromadb_collection.query(
                query_texts=[search_query],
                n_results=min(limit * 2, 20),  # 多めに取得してフィルタ
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

                    # コサイン距離 → 類似度に変換（0-1、1が最も類似）
                    # ChromaDB cosine distance = 1 - cosine_similarity
                    relevance = max(0, 1.0 - distance)

                    # 閾値: 0.3以上（コサイン類似度で0.7以上相当）
                    if relevance >= 0.3:
                        results.append({
                            "content": doc,
                            "category": meta.get("category", "unknown"),
                            "keywords": meta.get("keywords", ""),
                            "relevance": round(relevance, 3),
                            "match_type": "semantic",
                            "created_at": meta.get("created_at", ""),
                        })

        # === 3. キーワード検索（セマンティックを補完） ===
        if query.strip():
            all_docs = _chromadb_collection.get(limit=1000)  # 全件取得
            query_lower = query.lower()
            query_keywords = extract_keywords(query)

            for i, doc in enumerate(all_docs["documents"]):
                doc_id = all_docs["ids"][i]
                if doc_id in seen_ids:
                    continue

                meta = all_docs["metadatas"][i] if all_docs["metadatas"] else {}

                # カテゴリフィルタ
                if category and meta.get("category") != category:
                    continue

                doc_lower = doc.lower()
                doc_keywords = meta.get("keywords", "").lower()

                # キーワードマッチ判定
                match_score = 0

                # 本文に含まれる
                if query_lower in doc_lower:
                    match_score = 0.9  # 完全一致は高スコア
                elif query in doc:  # 大文字小文字区別
                    match_score = 0.85

                # キーワードフィールドに含まれる
                if query_lower in doc_keywords:
                    match_score = max(match_score, 0.85)

                # 抽出キーワードとの部分一致
                for kw in query_keywords:
                    if kw in doc_lower or kw in doc_keywords:
                        match_score = max(match_score, 0.7)
                        break

                if match_score > 0:
                    seen_ids.add(doc_id)
                    results.append({
                        "content": doc,
                        "category": meta.get("category", "unknown"),
                        "keywords": meta.get("keywords", ""),
                        "relevance": match_score,
                        "match_type": "keyword",
                        "created_at": meta.get("created_at", ""),
                    })

        # === 4. 結果をソートして返却 ===
        results.sort(key=lambda x: x["relevance"], reverse=True)
        results = results[:limit]

        logger.info(f"search_memory('{query[:30]}...', category='{category}'): {len(results)} results")
        return {
            "status": "ok",
            "query": query,
            "category": category,
            "count": len(results),
            "memories": results,
        }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"status": "error", "message": str(e), "memories": []}


@mcp.tool()
def save_memory(
    content: str,
    category: str = "voluntary"
) -> dict:
    """
    重要な情報を長期記憶に保存（キーワード自動抽出付き）

    カテゴリガイド:
    - user_info: 名前、年齢、職業など → "ユーザーの名前: パイパイ"
    - preference: 好み、趣味 → "好きな食べ物: チョコレートケーキ"
    - episode: 出来事、思い出 → "2024年に旅行した話"
    - instruction: 指示、ルール → "敬語で話してほしい"
    - fact: 事実、知識 → "〇〇について学んだ"
    - insight: 気づき、洞察
    - voluntary: その他

    Args:
        content: 保存する内容（明確で検索しやすい文を推奨）
        category: カテゴリ (user_info, preference, episode, instruction, fact, insight, voluntary)

    Returns:
        保存結果
    """
    _ensure_initialized()

    if _chromadb_collection is None:
        return {"status": "error", "message": "Memory system unavailable"}

    if not content.strip():
        return {"status": "error", "message": "Empty content"}

    # カテゴリ検証
    if category not in CATEGORIES:
        logger.warning(f"Unknown category '{category}', using 'voluntary'")
        category = "voluntary"

    try:
        # キーワード自動抽出
        keywords = extract_keywords(content)
        keywords_str = ",".join(keywords)

        # E5モデル用のプレフィックス（保存時は passage: を使用）
        embed_content = f"passage: {content}" if _embedding_function else content

        memory_id = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        _chromadb_collection.add(
            ids=[memory_id],
            documents=[embed_content],
            metadatas=[{
                "category": category,
                "keywords": keywords_str,
                "original_content": content,  # 元のコンテンツも保存
                "user_id": "global",
                "created_at": datetime.now().isoformat(),
                "source": "mcp_tool",
            }]
        )

        logger.info(f"save_memory[{category}]: {content[:50]}... | keywords: {keywords_str[:50]}")
        return {
            "status": "ok",
            "memory_id": memory_id,
            "category": category,
            "keywords": keywords,
            "content": content[:100] + "..." if len(content) > 100 else content,
        }

    except Exception as e:
        logger.error(f"Save failed: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def memory_stats() -> dict:
    """
    メモリ統計を取得

    Returns:
        カテゴリ別の記憶数など
    """
    _ensure_initialized()

    if _chromadb_collection is None:
        return {"status": "error", "message": "Memory system unavailable"}

    try:
        total = _chromadb_collection.count()

        # カテゴリ別カウント
        categories = {}
        for cat in CATEGORIES.keys():
            try:
                results = _chromadb_collection.get(where={"category": cat})
                categories[cat] = len(results["ids"])
            except:
                categories[cat] = 0

        return {
            "status": "ok",
            "total_memories": total,
            "by_category": categories,
            "available_categories": list(CATEGORIES.keys()),
        }

    except Exception as e:
        logger.error(f"Stats failed: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def list_categories() -> dict:
    """
    利用可能なカテゴリ一覧を取得

    Returns:
        カテゴリ名と説明のリスト
    """
    return {
        "status": "ok",
        "categories": CATEGORIES,
    }


# ========== Entry Point ==========

if __name__ == "__main__":
    logger.info("Starting Memory Tools MCP Server (Enhanced)...")
    _ensure_initialized()
    logger.info("Starting MCP transport...")
    mcp.run(transport="stdio")
