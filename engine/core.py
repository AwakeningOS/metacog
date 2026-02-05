"""
Awareness Engine — Main Orchestrator

Ties together all components:
- Memory system (ChromaDB + JSONL files)
- System prompt builder (dynamic context injection)
- LM Studio API client
- Response parser (response + insights + [SAVE] extraction)
- Dreaming engine (feedback learning loop)

One LLM call per conversation turn.
LM Studio's built-in Sequential Thinking handles structured reasoning.
"""

import logging
from pathlib import Path
from typing import Optional

from .memory import UnifiedMemory
from .prompt_builder import SystemPromptBuilder
from .response_parser import ResponseParser
from .lm_studio import LMStudioClient

logger = logging.getLogger(__name__)


class AwarenessEngine:
    """Main orchestrator — one LLM call per conversation turn"""

    def __init__(self, config: dict, data_dir: Optional[Path] = None):
        self.config = config
        self.data_dir = data_dir or Path("./data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.memory = UnifiedMemory(data_dir=str(self.data_dir))

        self.prompt_builder = SystemPromptBuilder(config)
        self.response_parser = ResponseParser()

        lm_config = config.get("lm_studio", {})
        self.lm_client = LMStudioClient(
            host=lm_config.get("host", "localhost"),
            port=lm_config.get("port", 1234),
            api_token=lm_config.get("api_token", ""),
            timeout=lm_config.get("timeout", 300),
        )

        # Dreaming engine (lazy loaded to avoid circular import)
        self._dreaming = None

        # Conversation state
        self.conversation_history: list[dict] = []
        self.last_user_input = ""
        self.last_assistant_output = ""
        self.last_insights: list[str] = []
        self.last_saves: list[str] = []

        logger.info(f"AwarenessEngine initialized. data_dir={self.data_dir}")

    @property
    def dreaming(self):
        """Lazy load dreaming engine"""
        if self._dreaming is None:
            from .dreaming import DreamingEngine
            self._dreaming = DreamingEngine(
                memory=self.memory,
                data_dir=self.data_dir,
                lm_client=self.lm_client,
            )
        return self._dreaming

    # ========== Chat ==========

    def send_message(self, user_input: str) -> tuple[str, dict]:
        """
        Process one conversation turn.

        Flow:
        1. Build system prompt (fixed base prompt)
        2. Build input with related memories from ChromaDB
        3. Single LLM call (with MCP awareness-thinking)
        4. Parse response → response + insights + [SAVE]
        5. Save everything to memory
        6. Return response to user

        Returns:
            tuple: (response_text, metadata)
        """
        # 1. Build system prompt (fixed base prompt only)
        system_prompt = self.prompt_builder.build()

        # 2. Build input with saved memories as context
        full_input = self._build_input_with_context(user_input)

        # 3. Get MCP integrations from config
        integrations = self.config.get("mcp_integrations", [])

        # 4. Single LLM call
        raw_response, api_metadata = self.lm_client.chat(
            input_text=full_input,
            system_prompt=system_prompt,
            integrations=integrations,
            context_length=self.config.get("lm_studio", {}).get("context_length", 32000),
        )

        # 5. Parse response
        parsed = self.response_parser.parse(raw_response)

        # 6. Save extracted insights
        for insight in parsed["insights"]:
            try:
                self.memory.save_insight(insight, source="response")
            except Exception as e:
                logger.error(f"Failed to save insight: {e}")

        # 7. Save voluntary memories
        for save_item in parsed["saves"]:
            try:
                self.memory.save(save_item, category="voluntary")
            except Exception as e:
                logger.error(f"Failed to save voluntary memory: {e}")

        # 8. Update conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": parsed["response"]})

        # Trim history (keep last 20 messages = 10 turns)
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # 9. Store last turn state
        self.last_user_input = user_input
        self.last_assistant_output = parsed["response"]
        self.last_insights = parsed["insights"]
        self.last_saves = parsed["saves"]

        # Build metadata
        metadata = {
            "insights": parsed["insights"],
            "saves": parsed["saves"],
            "tool_calls": api_metadata.get("tool_calls", []),
            "model": api_metadata.get("model", ""),
        }

        return parsed["response"], metadata

    def _build_input_with_context(self, user_input: str) -> str:
        """Build input text.

        Memory search is now handled by LLM via MCP tools (search_memory).
        No automatic injection - LLM decides when to search.
        """
        # Simply return user input as-is
        # LLM will use search_memory tool when needed
        return user_input

    # ========== Feedback ==========

    def submit_feedback(self, feedback: str) -> bool:
        """Save user feedback (highest priority in dreaming)"""
        if not feedback:
            return False

        context = {
            "last_user_input": self.last_user_input,
            "last_response": self.last_assistant_output[:300],
        }
        return self.memory.save_feedback(feedback, context=context)

    # ========== Dreaming ==========

    def trigger_dream(self) -> dict:
        """Trigger a dreaming cycle"""
        return self.dreaming.dream()

    def check_dream_threshold(self) -> dict:
        """Check if memory count exceeds dream threshold"""
        threshold = self.config.get("dreaming", {}).get("memory_threshold", 30)
        count = self.memory.count()
        return {
            "current_count": count,
            "threshold": threshold,
            "should_dream": count >= threshold,
        }

    # ========== Connection ==========

    def check_connection(self) -> dict:
        """Check LM Studio connection"""
        return self.lm_client.check_connection()

    # ========== Memory Reset ==========

    def reset_memory(self) -> dict:
        """Reset all memories (ChromaDB + JSONL files)"""
        return self.memory.reset_all()

    # ========== State Management ==========

    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.last_user_input = ""
        self.last_assistant_output = ""
        self.last_insights = []
        self.last_saves = []

    def get_stats(self) -> dict:
        """Get system statistics"""
        # LLM自発メモリ = MCP経由で保存されたもの全て
        llm_memory_count = self.memory.get_llm_memory_count()
        insight_count_chromadb = self.memory.count(category="insight")
        dream_insight_count = self.memory.count(category="dream_insight")
        total_chromadb = self.memory.count()

        feedback_count = len(self.memory.get_feedback())

        dream_stats = {}
        try:
            dream_stats = self.dreaming.get_stats()
        except Exception:
            pass

        return {
            "total_chromadb": total_chromadb,
            "llm_memory_count": llm_memory_count,
            "insight_count": insight_count_chromadb,
            "dream_insight_count": dream_insight_count,
            "feedback_count": feedback_count,
            "conversation_turns": len(self.conversation_history) // 2,
            "dream_cycles": dream_stats.get("dream_cycles", 0),
        }
