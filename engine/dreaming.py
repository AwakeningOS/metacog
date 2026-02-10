"""
Dreaming Engine — Feedback Learning Loop

Processes accumulated memories, feedback, and thought logs to generate
insights that are saved to memory for future retrieval.

Simplified from previous project:
- Single memory source (UnifiedMemory) instead of three
- Removed MCP memory / Moltbook / SimpleMemory
- Simplified input: ChromaDB memories + user feedback only
- Natural language output (no categories - semantic search handles retrieval)
- Same insight carry-forward mechanism
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from config.default_config import DREAM_PROMPT, load_config

if TYPE_CHECKING:
    from .memory import UnifiedMemory
    from .lm_studio import LMStudioClient

logger = logging.getLogger(__name__)


class DreamingEngine:
    """Processes memories and feedback into actionable insights"""

    def __init__(
        self,
        memory: "UnifiedMemory",
        data_dir: Path,
        lm_client: "LMStudioClient",
    ):
        self.memory = memory
        self.data_dir = data_dir
        self.lm_client = lm_client

        # Files
        self.archives_file = self.data_dir / "dream_archives.jsonl"

    # ========== Main Dream Method ==========

    def dream(self) -> dict:
        """
        Execute a dreaming cycle.

        Steps:
        1. Collect memories from ChromaDB
        2. Load user feedback (highest priority)
        3. Load previous insights (carry-forward)
        4. Build dream prompt
        5. Call LLM
        6. Parse A/B/C insights
        7. Archive old data, save new insights
        """
        start_time = datetime.now()
        logger.info("=== Dream Cycle Starting ===")

        # Step 1: Export memories
        export = self.memory.export_for_dreaming()
        memories = export.get("memories", [])

        if not memories and not export.get("feedback"):
            logger.warning("No memories or feedback to dream about")
            return {"status": "skipped", "reason": "No memories or feedback"}

        # Step 2: Format user feedback (highest priority)
        feedbacks = export.get("feedback", [])
        if feedbacks:
            feedback_lines = []
            for fb in feedbacks:
                text = fb.get("feedback", "")
                feedback_lines.append(f"- {text}")
            feedback_text = "\n".join(feedback_lines)
        else:
            feedback_text = "(ユーザーからの修正指示なし)"

        # Step 3: Format saved memories by category
        exchanges = []  # 残響 (exchange category)
        impressions = []  # 余韻 (chat category)
        melodies = []  # 旋律 (dream category)
        other_memories = []  # その他

        for mem in memories:
            content = mem.get("content", "")
            category = mem.get("category", "")
            if category == "exchange":
                exchanges.append(f"- {content}")
            elif category == "chat":
                impressions.append(f"- {content}")
            elif category == "dream":
                melodies.append(f"- {content}")
            else:
                other_memories.append(f"- [{category}] {content}")

        exchanges_text = "\n".join(exchanges) if exchanges else "(なし)"
        impressions_text = "\n".join(impressions) if impressions else "(なし)"
        melodies_text = "\n".join(melodies) if melodies else "(なし)"
        memories_text = "\n".join(exchanges + impressions + melodies + other_memories) if memories else "(保存された記憶なし)"

        # Step 4: Build and send dream prompt (load from config)
        config = load_config()
        dream_prompt_template = config.get("dream_prompt", DREAM_PROMPT)
        dream_system_prompt = dream_prompt_template.format(
            user_feedback=feedback_text,
            saved_memories=memories_text,
            saved_exchanges=exchanges_text,
            saved_impressions=impressions_text,
            saved_melodies=melodies_text,
        )

        logger.info(f"Dream prompt: {len(dream_system_prompt)} chars | "
                     f"feedback={len(feedbacks)}, memories={len(memories)}")

        # Call LLM with MCP tools for deep analysis
        # UIの夢見プロンプトをシステムプロンプトとして直接使用
        response, _ = self.lm_client.chat(
            input_text="上記の指示に従って処理を実行してください。",
            system_prompt=dream_system_prompt,
            integrations=["mcp/sequential-thinking"],
            temperature=0.7,
        )

        if not response or response.startswith("Error") or response.startswith("API Error"):
            logger.error(f"Dream LLM call failed: {response}")
            return {"status": "failed", "reason": f"LLM error: {response[:100]}"}

        # Step 7: Parse insights (no categories - semantic search handles it)
        parsed_insights = self._parse_insights(response)
        if not parsed_insights:
            # フォールバック: パースできなければ全文を保存
            parsed_insights = [response.strip()[:500]]
            logger.info("No list items found, saving full response")
        else:
            logger.info(f"Extracted {len(parsed_insights)} insights")

        # Step 8: Archive and save
        timestamp = datetime.now().isoformat()

        # Archive insights to JSONL
        new_insight_entries = [
            {"timestamp": timestamp, "insight": content, "source": "dreaming"}
            for content in parsed_insights
        ]
        self.memory.archive_insights(new_insight_entries)

        # Save dream insights to ChromaDB (category="dream" for all dream-generated memories)
        # [旋律] プレフィックスを付与（夢見で生成されたパターン）
        for content in parsed_insights:
            try:
                formatted_content = f"[旋律] {content.strip()}"
                self.memory.save(
                    content=formatted_content,
                    category="dream",  # 夢見由来の記憶
                    metadata={"source": "dreaming"}
                )
            except Exception as e:
                logger.error(f"Failed to save dream insight to ChromaDB: {e}")

        # Archive feedback
        feedbacks_archived = self.memory.archive_feedback()

        # 使用した記憶をアーカイブに移動（ChromaDBから削除）
        used_memory_ids = [mem["id"] for mem in memories if "id" in mem]
        archive_result = self.memory.archive_memories(used_memory_ids)

        # Save dream archive
        archive_entry = {
            "archived_at": timestamp,
            "memories_processed": len(memories),
            "memories_archived": archive_result.get("archived_count", 0),
            "feedbacks_used": len(feedbacks),
            "insights_generated": parsed_insights,
        }
        self._append_jsonl(self.archives_file, archive_entry)

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"=== Dream Complete: {len(parsed_insights)} insights, "
                     f"archived={archive_result.get('archived_count', 0)}, "
                     f"feedback_archived={feedbacks_archived}, "
                     f"{duration:.1f}s ===")

        return {
            "status": "completed",
            "memories_processed": len(memories),
            "memories_archived": archive_result.get("archived_count", 0),
            "feedbacks_used": len(feedbacks),
            "feedbacks_archived": feedbacks_archived,
            "insights_generated": len(parsed_insights),
            "insights": parsed_insights,
            "duration_seconds": duration,
        }

    # ========== Insight Parser ==========

    def _parse_insights(self, response: str) -> list[str]:
        """
        Parse insights from LLM response.
        Returns list of content strings (no categories - semantic search handles it).

        Accepts:
        - Lines starting with "- " (bullet points)
        - Lines starting with "・" (Japanese bullet)
        - Lines starting with numbers like "1. " or "1) "
        """
        insights = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line or len(line) < 5:
                continue

            # Remove bullet point prefixes
            if line.startswith("- "):
                content = line[2:].strip()
            elif line.startswith("・"):
                content = line[1:].strip()
            elif len(line) > 2 and line[0].isdigit() and line[1] in ".)" :
                content = line[2:].strip()
            elif len(line) > 3 and line[0].isdigit() and line[1].isdigit() and line[2] in ".)":
                content = line[3:].strip()
            else:
                # Skip lines that don't look like list items
                continue

            if content and len(content) >= 5:
                insights.append(content)

        return insights


    # ========== Stats ==========

    def get_stats(self) -> dict:
        """Get dreaming statistics"""
        dream_cycles = 0
        total_archived = 0
        last_dream = None

        if self.archives_file.exists():
            try:
                with open(self.archives_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            dream_cycles += 1
                            total_archived += entry.get("memories_processed", 0)
                            last_dream = entry.get("archived_at")
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass

        return {
            "dream_cycles": dream_cycles,
            "total_archived_memories": total_archived,
            "current_memory_count": self.memory.count(),
            "total_insights": len(self.memory.get_all_insights()),
            "last_dream": last_dream,
        }

    def get_last_report(self) -> Optional[str]:
        """Get formatted last dream report"""
        if not self.archives_file.exists():
            return None

        last_entry = None
        try:
            with open(self.archives_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        last_entry = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return None

        if not last_entry:
            return None

        report = f"# Dream Report\n"
        report += f"Date: {last_entry.get('archived_at', 'Unknown')}\n"
        report += f"Memories Processed: {last_entry.get('memories_processed', 0)}\n\n"
        report += f"## Generated Insights\n"
        for i, insight in enumerate(last_entry.get("insights_generated", []), 1):
            report += f"{i}. {insight}\n"

        return report

    # ========== Utility ==========

    def _append_jsonl(self, filepath: Path, data: dict):
        """Append a JSON line to file"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
