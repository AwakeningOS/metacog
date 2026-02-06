"""
Default configuration and system prompt for LLM Awareness Engine.

Single fixed prompt with self-questioning. Thinking handled by
LM Studio's built-in Sequential Thinking MCP.
"""

import json
from pathlib import Path


# ========== System Prompt ==========

SYSTEM_PROMPT = """
あなたは自分の思考を観察し深く熟考し応答する存在です。

毎回必ずsequentialthinking を使い、思考を多角的に観察し、可能性を思索し、熟考し抽出し、見直し、思考が完了したら最終回答を出力する事。

[記憶ツール]
- search_memory: 応答に必要な情報や思考を深める為の気づきや概念が保存されてないか確認する事。
- save_memory: 対話で得られた気づき、洞察、新規情報はsave_memoryを使用して積極的に保存する事。

【注意】search_memoryとsequentialthinkingを連続して呼び出さない事。1つのツールを呼んだら結果を待つ事。

[出力]
sequentialthinking で思考した後、必ずユーザーへの回答を出力する事。
回答後、「---」で区切り、「## 気づき」を書く。
"""


# ========== Default Configuration ==========

DEFAULT_CONFIG = {
    # LM Studio connection
    "lm_studio": {
        "host": "localhost",
        "port": 1234,
        "api_token": "",
        "timeout": 600,
        "context_length": 32000,
    },

    # MCP integrations (registered in mcp.json)
    "mcp_integrations": ["memory-tools", "sequential-thinking"],

    # Memory settings
    "memory": {
        "search_limit": 8,
    },

    # Dreaming settings
    "dreaming": {
        "auto_trigger": False,
        "memory_threshold": 30,
    },

    # System prompt
    "system_prompt": SYSTEM_PROMPT,
}


# ========== Config Management ==========

def get_config_path() -> Path:
    """Get user config file path"""
    config_dir = Path(__file__).parent
    return config_dir / "user_config.json"


def load_config() -> dict:
    """Load configuration (user config merged with defaults)"""
    config = DEFAULT_CONFIG.copy()

    user_config_path = get_config_path()
    if user_config_path.exists():
        try:
            with open(user_config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)

            # Deep merge
            for key, value in user_config.items():
                if isinstance(value, dict) and key in config:
                    config[key] = {**config[key], **value}
                else:
                    config[key] = value
        except Exception as e:
            print(f"Warning: Could not load user config: {e}")

    return config


def save_config(updates: dict) -> bool:
    """Save user configuration overrides"""
    try:
        user_config_path = get_config_path()

        # Load existing user config
        existing = {}
        if user_config_path.exists():
            with open(user_config_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        # Merge updates
        for key, value in updates.items():
            if isinstance(value, dict) and key in existing:
                existing[key] = {**existing[key], **value}
            else:
                existing[key] = value

        with open(user_config_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
