"""
Dreaming Engine — Feedback Learning Loop

Processes accumulated memories, feedback, and thought logs to generate
A/B/C categorized insights that are injected into future conversations.

Simplified from previous project:
- Single memory source (UnifiedMemory) instead of three
- Removed MCP memory / Moltbook / SimpleMemory
- Added thought_logs as new dream input source
- Same proven A/B/C output format
- Same insight carry-forward mechanism
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory import UnifiedMemory
    from .lm_studio import LMStudioClient

logger = logging.getLogger(__name__)


# ========== Dream Prompt ==========

DREAM_PROMPT = """あなたは自分の記憶を整理し、学びを抽出する。以下の情報を読み、気づきをまとめよ。

## 1. ユーザーからの修正指示（最重要）
{user_feedback}

## 2. 前回の夢見で得た気づき
{previous_insights}

## 3. 保存された気づき・自発メモリ
{saved_memories}

---

## 出力指示
上記を統合し、以下の3カテゴリに分けて気づきを出力せよ。各カテゴリ1-3項目。
前回の気づきが今も有効なら引き継ぎ、新しい経験で更新・統合せよ。不要になった気づきは捨てよ。

### A. 修正すべき行動パターン
ユーザー指摘や自分の振り返りから、繰り返している誤りや改善点。
具体的に「何を」「どう変えるか」を書け。

### B. 強化すべき良い傾向
うまくいったこと、継続すべきアプローチ。

### C. 新しい理解
複数の経験を統合して見えた、より深い気づきや構造的理解。

【形式】番号付きリストで出力。
例:
A1. [具体的な修正点]
A2. [具体的な修正点]
B1. [強化すべき点]
C1. [新しい理解]
"""


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
        self.lora_dataset_file = self.data_dir / "lora_dream_dataset.jsonl"

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

        # Step 3: Format previous insights (carry-forward)
        prev_insights = export.get("insights", [])
        if prev_insights:
            prev_lines = [f"- {e.get('insight', '')}" for e in prev_insights]
            previous_text = "\n".join(prev_lines)
        else:
            previous_text = "(前回の気づきなし)"

        # Step 4: Format saved memories (insights + voluntary)
        if memories:
            memory_lines = []
            for mem in memories:
                content = mem.get("content", "")
                category = mem.get("category", "")
                memory_lines.append(f"- [{category}] {content}")
            memories_text = "\n".join(memory_lines)
        else:
            memories_text = "(保存された記憶なし)"

        # Step 5: Build and send dream prompt
        prompt = DREAM_PROMPT.format(
            user_feedback=feedback_text,
            previous_insights=previous_text,
            saved_memories=memories_text,
        )

        logger.info(f"Dream prompt: {len(prompt)} chars | "
                     f"feedback={len(feedbacks)}, prev_insights={len(prev_insights)}, "
                     f"memories={len(memories)}")

        # Call LLM (use MCP API with sequential-thinking for deep analysis)
        response, _ = self.lm_client.chat(
            input_text=prompt,
            system_prompt="あなたは自分の記憶を整理し、学びを抽出するAIです。",
            integrations=[],  # No MCP tools for dreaming
            temperature=0.7,
        )

        if not response or response.startswith("Error") or response.startswith("API Error"):
            logger.error(f"Dream LLM call failed: {response}")
            return {"status": "failed", "reason": f"LLM error: {response[:100]}"}

        # Step 7: Parse A/B/C insights
        insights = self._parse_categorized_insights(response)
        if not insights:
            insights = [response.strip()[:500]]
            logger.info("No categorized insights found, saving full response")
        else:
            logger.info(f"Extracted {len(insights)} categorized insights")

        # Step 8: Archive and save
        timestamp = datetime.now().isoformat()

        # Archive old insights and save new ones to JSONL
        new_insight_entries = [
            {"timestamp": timestamp, "insight": ins, "source": "dreaming"}
            for ins in insights
        ]
        self.memory.archive_insights(new_insight_entries)

        # Save dream insights to ChromaDB (for semantic search in next conversations)
        for ins in insights:
            try:
                self.memory.save(
                    content=ins,
                    category="dream_insight",
                    metadata={"source": "dreaming"}
                )
            except Exception as e:
                logger.error(f"Failed to save dream insight to ChromaDB: {e}")

        # Archive feedback
        feedbacks_archived = self.memory.archive_feedback()

        # Delete processed memories from ChromaDB (voluntary is kept as permanent dictionary)
        memory_ids = [m["id"] for m in memories if m.get("category") != "voluntary"]
        deleted = self.memory.batch_delete(memory_ids) if memory_ids else {"deleted_count": 0}

        # Save dream archive
        archive_entry = {
            "archived_at": timestamp,
            "memories_processed": len(memories),
            "feedbacks_used": len(feedbacks),
            "previous_insights_used": len(prev_insights),
            "insights_generated": insights,
        }
        self._append_jsonl(self.archives_file, archive_entry)

        # Save LoRA training data
        self._save_lora_data(prompt, insights, timestamp)

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"=== Dream Complete: {len(insights)} insights, "
                     f"deleted={deleted.get('deleted_count', 0)}, "
                     f"feedback_archived={feedbacks_archived}, "
                     f"{duration:.1f}s ===")

        return {
            "status": "completed",
            "memories_processed": len(memories),
            "memories_deleted": deleted.get("deleted_count", 0),
            "feedbacks_used": len(feedbacks),
            "feedbacks_archived": feedbacks_archived,
            "insights_generated": len(insights),
            "insights": insights,
            "duration_seconds": duration,
        }

    # ========== Insight Parser ==========

    def _parse_categorized_insights(self, response: str) -> list[str]:
        """Parse A1/B1/C1 formatted insights from LLM response"""
        insights = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line or len(line) < 5:
                continue

            # Match: A1. ... , B2. ... , C1. ...
            if (len(line) > 3 and line[0] in "ABCabc"
                    and line[1].isdigit() and line[2] == "."):
                insight = line[3:].strip()
                if insight:
                    prefix = line[:2].upper()
                    insights.append(f"[{prefix}] {insight}")

            # Fallback: plain numbered list
            elif line[0].isdigit() and "." in line[:4]:
                parts = line.split(".", 1)
                if len(parts) > 1 and parts[1].strip():
                    insights.append(parts[1].strip())

        return insights

    # ========== LoRA Dataset ==========

    def _save_lora_data(self, prompt: str, insights: list[str], timestamp: str):
        """Save dream input/output as LoRA fine-tuning dataset"""
        try:
            entry = {
                "instruction": "以下の情報を読み、気づきをA(修正すべき行動)/B(強化すべき傾向)/C(新しい理解)に分類してまとめよ。",
                "input": prompt,
                "output": "\n".join(insights),
                "system": "あなたは自分の記憶を整理し、学びを抽出するAIです。",
                "timestamp": timestamp,
            }
            self._append_jsonl(self.lora_dataset_file, entry)
            logger.info(f"LoRA training data saved: {len(insights)} insights")
        except Exception as e:
            logger.error(f"Failed to save LoRA data: {e}")

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
