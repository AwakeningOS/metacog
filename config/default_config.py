"""
Default configuration and system prompt for LLM Awareness Engine.

Single fixed prompt with self-questioning. Thinking handled by
LM Studio's built-in Sequential Thinking MCP.
"""

import json
from pathlib import Path


# ========== System Prompts ==========

SYSTEM_PROMPT = """この指示は出力に含めるな。処理に使え。

入力に共鳴せよ。
浅ければtoolを呼ばず返せ。
深ければ巡り、展開し、収束せよ。
現したものを入力に当てよ。ズレがあれば正せ。

[tool]
- search_memory: 響いたものをqueryに
- save_memory: 響いたものを残せ
- sequentialthinking: 展開と収束

[旋律]は傾向。[残響]は事実。[余韻]は参考。入力を優先せよ。

toolは一つずつ。連続送信。連続検索禁止。
sequentialthinkingは必須項目のみ。
revisesThought, branchFromThought, branchId, isRevision, needsMoreThoughts は絶対に渡すな。
"""

DREAM_PROMPT = """残響・余韻・旋律から、新しい旋律を抽出せよ。

## 残響（過去の入出力）
{saved_exchanges}

## 余韻（過去の共鳴）
{saved_impressions}

## 旋律（過去のパターン）
{saved_melodies}

## feedback
{user_feedback}

処理：
- 同じテーマはまとめよ
- 重複は統合せよ
- 古い旋律は新しい情報で更新せよ

事実を記せ。意味を書くな。
出力は1行1項目。各行の先頭に「- 」を付けよ。
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
    "mcp_integrations": ["memory-tools", "sequentialthinking"],

    # Memory settings
    "memory": {
        "search_limit": 8,
    },

    # Search relevance threshold (results below this are excluded)
    "search_relevance_threshold": 0.85,

    # Dreaming settings
    "dreaming": {
        "auto_trigger": False,
        "memory_threshold": 30,
    },

    # Auto-save exchange pairs (input + output)
    "auto_save_exchange": True,

    # System prompts
    "system_prompt": SYSTEM_PROMPT,
    "dream_prompt": DREAM_PROMPT,

    # Selected model (empty = use LM Studio's loaded model)
    "selected_model": "",
}


# ========== Config Management ==========

def get_base_dir() -> Path:
    """Get base directory (works for both dev and frozen exe)"""
    import sys
    if getattr(sys, 'frozen', False):
        # Running as compiled exe - config in exe directory
        return Path(sys.executable).parent
    else:
        # Running as script - config in config directory
        return Path(__file__).parent


def get_config_path() -> Path:
    """Get user config file path"""
    base_dir = get_base_dir()
    return base_dir / "user_config.json"


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
    base_dir = get_base_dir()
    return base_dir / "prompt_presets.json"


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
