"""
Awareness Engine — Main Orchestrator

Ties together all components:
- Memory system (ChromaDB + JSONL files)
- System prompt builder (dynamic context injection)
- LM Studio API client
- Response parser (response + observations + [SAVE] extraction)
- Dreaming engine (feedback learning loop)

Two-layer observer system:
- Layer 1: Each turn generates an observation
- Layer 2: Auto API call compares prev/current observations → diff
- Diff is injected into next turn's input
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
            selected_model=config.get("selected_model", ""),
        )

        # Dreaming engine (lazy loaded to avoid circular import)
        self._dreaming = None

        # Conversation state
        self.conversation_history: list[dict] = []
        self.last_user_input = ""
        self.last_assistant_output = ""
        self.last_saves: list[str] = []

        # Two-layer observer state
        self.prev_observation: Optional[str] = None
        self.last_observation: Optional[str] = None
        self.last_diff: Optional[str] = None

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
        1. Build system prompt
        2. Build input with diff injection
        3. Single LLM call
        4. Parse response → response + observations + [SAVE]
        5. Save to memory
        6. Shift observations, generate diff if 2 observations exist
        7. Return response to user
        """
        # 1. Build system prompt
        system_prompt = self.prompt_builder.build()

        # 2. Build input with diff injection
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

        # 6. Save extracted observations
        for obs in parsed["observations"]:
            try:
                self.memory.save_insight(obs, source="response")
            except Exception as e:
                logger.error(f"Failed to save observation: {e}")

        # 7. Save chat memories
        for save_item in parsed["saves"]:
            try:
                self.memory.save(save_item, category="chat")
            except Exception as e:
                logger.error(f"Failed to save chat memory: {e}")

        # 8. Update conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        self.conversation_history.append({"role": "assistant", "content": parsed["response"]})

        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # 9. Shift observations and generate diff
        new_obs = parsed["observations"][0] if parsed["observations"] else None
        self.prev_observation = self.last_observation
        self.last_observation = new_obs

        # Generate diff if two observations exist
        self.last_diff = None
        if self.prev_observation and self.last_observation:
            self.last_diff = self._generate_diff(self.prev_observation, self.last_observation)
            if self.last_diff:
                logger.info(f"Generated diff: {self.last_diff[:50]}")
                print(f"DEBUG: Generated diff = {self.last_diff}")

        # 10. Store last turn state
        self.last_user_input = user_input
        self.last_assistant_output = parsed["response"]
        self.last_saves = parsed["saves"]

        # Build metadata
        metadata = {
            "observations": parsed["observations"],
            "diff": self.last_diff,
            "saves": parsed["saves"],
            "tool_calls": api_metadata.get("tool_calls", []),
            "thoughts": api_metadata.get("thoughts", []),
            "model": api_metadata.get("model", ""),
        }

        return parsed["response"], metadata

    def _build_input_with_context(self, user_input: str) -> str:
        """Build input with diff injection only.

        Turn 1, 2: No injection
        Turn 3+: Inject <diff> from previous turn's auto-generated diff
        """
        print(f"DEBUG: prev_observation = {self.prev_observation}")
        print(f"DEBUG: last_observation = {self.last_observation}")
        print(f"DEBUG: last_diff = {self.last_diff}")

        parts = []

        # Inject diff only
        if self.last_diff:
            parts.append(f"<diff>{self.last_diff}</diff>")
            logger.info(f"Injected diff: {self.last_diff[:50]}")

        # Add user input
        parts.append(user_input)

        return "\n\n".join(parts)

    def _generate_diff(self, obs1: str, obs2: str) -> Optional[str]:
        """Auto API call: compare two observations and generate diff.

        Uses diff_prompt from config with {obs1}, {obs2} placeholders.
        Output: one-line diff text
        """
        # Get diff prompt from config (with fallback)
        diff_template = self.config.get("diff_prompt", "「{obs1}」から「{obs2}」への変化を一行で記述せよ。")
        prompt = diff_template.format(obs1=obs1, obs2=obs2)

        try:
            logger.info(f"Generating diff: obs1={obs1[:30]}, obs2={obs2[:30]}")
            raw_response, _ = self.lm_client.chat(
                input_text=prompt,
                system_prompt="",
                integrations=[],
                context_length=4096,
            )

            # Clean up response
            diff = raw_response.strip()

            # Remove markdown list markers
            if diff.startswith("- "):
                diff = diff[2:].strip()
            elif diff.startswith("* "):
                diff = diff[2:].strip()

            # Remove quotes if wrapped
            if diff.startswith("「") and diff.endswith("」"):
                diff = diff[1:-1].strip()

            # Take only first line
            if "\n" in diff:
                diff = diff.split("\n")[0].strip()

            return diff if diff else None

        except Exception as e:
            logger.error(f"Failed to generate diff: {e}")
            return None

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

    def get_available_models(self) -> list[str]:
        """Get list of available models from LM Studio"""
        return self.lm_client.get_available_models()

    def get_loaded_model(self) -> str:
        """Get currently loaded model"""
        return self.lm_client.get_loaded_model() or ""

    def get_model_info(self, model_key: str) -> dict:
        """Get model info including max_context_length"""
        return self.lm_client.get_model_info(model_key)

    # ========== Memory Reset ==========

    def reset_memory(self) -> dict:
        """Reset all memories (ChromaDB + JSONL files)"""
        return self.memory.reset_all()

    def reset_everything(self) -> dict:
        """Reset all memories AND all logs/archives"""
        return self.memory.reset_everything()

    # ========== State Management ==========

    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.last_user_input = ""
        self.last_assistant_output = ""
        self.last_saves = []
        self.prev_observation = None
        self.last_observation = None
        self.last_diff = None

    def get_stats(self) -> dict:
        """Get system statistics"""
        chat_memory_count = self.memory.count(category="chat")
        dream_memory_count = self.memory.count(category="dream")
        total_chromadb = self.memory.count()

        feedback_count = len(self.memory.get_feedback())

        dream_stats = {}
        try:
            dream_stats = self.dreaming.get_stats()
        except Exception:
            pass

        return {
            "total_chromadb": total_chromadb,
            "chat_memory_count": chat_memory_count,
            "dream_memory_count": dream_memory_count,
            "feedback_count": feedback_count,
            "conversation_turns": len(self.conversation_history) // 2,
            "dream_cycles": dream_stats.get("dream_cycles", 0),
        }
