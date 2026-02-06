"""
Default configuration and system prompt for LLM Awareness Engine.

Single fixed prompt with self-questioning. Thinking handled by
LM Studio's built-in Sequential Thinking MCP.
"""

import json
from pathlib import Path


# ========== System Prompts ==========

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

DREAM_PROMPT = """あなたは自分の記憶を整理し、学びを抽出する存在です。

## 1. ユーザーからの修正指示（最重要）
{user_feedback}

## 2. 前回の夢見で得た気づき
{previous_insights}

## 3. 保存された記憶
{saved_memories}

---

上記を統合し、記憶すべき重要な概念、気づき、知識、情報、本質を抽出せよ。
前回の気づきが今も有効なら引き継ぎ、新しい経験で更新・統合せよ。不要になった気づきは捨てよ。

抽出した記憶は、後から検索しやすいような構造の文章でリスト化せよ。
各項目は1行で、先頭に「- 」を付けること。
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

    # System prompts
    "system_prompt": SYSTEM_PROMPT,
    "dream_prompt": DREAM_PROMPT,

    # Selected model (empty = use LM Studio's loaded model)
    "selected_model": "",
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


# ========== Prompt Presets ==========

def get_presets_path() -> Path:
    """Get presets file path"""
    config_dir = Path(__file__).parent
    return config_dir / "prompt_presets.json"


def load_presets() -> dict:
    """Load prompt presets"""
    presets_path = get_presets_path()

    # Default presets
    default_presets = {
        "default": {
            "name": "デフォルト",
            "system_prompt": SYSTEM_PROMPT,
            "dream_prompt": DREAM_PROMPT,
        }
    }

    if presets_path.exists():
        try:
            with open(presets_path, "r", encoding="utf-8") as f:
                user_presets = json.load(f)
            # Merge with defaults (user presets override)
            return {**default_presets, **user_presets}
        except Exception as e:
            print(f"Warning: Could not load presets: {e}")

    return default_presets


def save_preset(preset_id: str, name: str, system_prompt: str, dream_prompt: str) -> bool:
    """Save a prompt preset"""
    try:
        presets_path = get_presets_path()

        # Load existing
        presets = {}
        if presets_path.exists():
            with open(presets_path, "r", encoding="utf-8") as f:
                presets = json.load(f)

        # Add/update preset
        presets[preset_id] = {
            "name": name,
            "system_prompt": system_prompt,
            "dream_prompt": dream_prompt,
        }

        with open(presets_path, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving preset: {e}")
        return False


def delete_preset(preset_id: str) -> bool:
    """Delete a prompt preset"""
    if preset_id == "default":
        return False  # Cannot delete default

    try:
        presets_path = get_presets_path()
        if not presets_path.exists():
            return False

        with open(presets_path, "r", encoding="utf-8") as f:
            presets = json.load(f)

        if preset_id in presets:
            del presets[preset_id]
            with open(presets_path, "w", encoding="utf-8") as f:
                json.dump(presets, f, ensure_ascii=False, indent=2)
            return True
        return False
    except Exception as e:
        print(f"Error deleting preset: {e}")
        return False
