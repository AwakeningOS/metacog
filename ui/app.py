"""
Gradio UI for LLM Awareness Engine

3 tabs:
- Chat: Message input/output + feedback + insight display
- Dashboard: Memory stats, insight history, dreaming controls
- Settings: LM Studio connection, thresholds
"""

import logging
import sys
from pathlib import Path

import gradio as gr


def get_project_root() -> Path:
    """Get project root (works for both dev and frozen exe)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent.parent


# Add project root to path
project_root = get_project_root()
sys.path.insert(0, str(project_root))

from config.default_config import (
    load_config, save_config, load_presets, save_preset, delete_preset,
    SYSTEM_PROMPT, DREAM_PROMPT
)
from engine.core import AwarenessEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ========== Global State ==========

config = load_config()
data_dir = project_root / "data"
engine = AwarenessEngine(config=config, data_dir=data_dir)

# ========== Custom CSS ==========

CUSTOM_CSS = """
.insight-card {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    font-size: 0.9em;
}
.feedback-box textarea {
    border: 2px solid #2d5aa0 !important;
    border-radius: 8px;
}
.dream-button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
}
/* チェックボックスをシンプルに */
.gr-checkbox-group label {
    background: #1a1a1a !important;
    color: #ffffff !important;
    border: 1px solid #333 !important;
}
.gr-checkbox-group label:hover {
    background: #2a2a2a !important;
}
"""


# ========== Chat Handlers ==========

def send_message(message: str, history: list):
    """Process user message and return response"""
    if not message.strip():
        return history, "", ""

    # Send to engine
    response, metadata = engine.send_message(message)

    # Update history
    history = history or []
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})

    # Format thoughts for display
    thoughts = metadata.get("thoughts", [])
    saves = metadata.get("saves", [])

    display_parts = []

    # 思考過程を表示
    if thoughts:
        display_parts.append("### 🧠 思考過程")
        for t in thoughts:
            num = t.get("number", "?")
            total = t.get("total", "?")
            thought = t.get("thought", "")
            if thought:
                # 長い思考は省略
                short = thought[:200] + "..." if len(thought) > 200 else thought
                display_parts.append(f"\n**[{num}/{total}]** {short}")

    # 保存した記憶
    if saves:
        display_parts.append("\n### 💾 保存した記憶")
        for s in saves:
            display_parts.append(f"- {s}")

    insight_display = "\n".join(display_parts)

    return history, "", insight_display


def submit_feedback(feedback: str):
    """Submit user feedback"""
    if not feedback.strip():
        return "フィードバックを入力してください", ""

    success = engine.submit_feedback(feedback)
    if success:
        return "✅ フィードバックを保存しました（次の夢見で処理されます）", ""
    else:
        return "❌ フィードバックの保存に失敗しました", feedback


def clear_chat():
    """Clear conversation"""
    engine.clear_conversation()
    return [], "", ""


def format_chat_for_copy(history: list) -> str:
    """Format chat history for clipboard copy"""
    if not history:
        return ""

    lines = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"【ユーザー】\n{content}")
        elif role == "assistant":
            lines.append(f"【アシスタント】\n{content}")

    return "\n\n---\n\n".join(lines)


# ========== Dashboard Handlers ==========

def get_dashboard_data():
    """Get dashboard statistics"""
    stats = engine.get_stats()
    threshold = engine.check_dream_threshold()

    stats_text = f"""### 📊 蓄積データ

| 項目 | 件数 |
|------|------|
| 📦 記憶（ChromaDB） | {stats['total_chromadb']} |
| 💬 フィードバック | {stats['feedback_count']} |

### 🌙 夢見

| 項目 | 値 |
|------|-----|
| 実行回数 | {stats['dream_cycles']}回 |
| 最終実行 | {stats.get('last_dream', '未実行')} |
| 推奨 | {'✨ はい' if threshold['should_dream'] else 'いいえ'} |
"""

    return stats_text


def get_dream_data():
    """Get all memories and feedback for dream tab selection"""
    export = engine.memory.export_for_dreaming()
    memories = export.get("memories", [])
    feedbacks = export.get("feedback", [])

    # 記憶一覧をチェックボックス用に整形
    # content は既に [カテゴリ] 内容 形式で保存されているのでそのまま使用
    memory_choices = []
    for mem in memories:
        content = mem.get("content", "")[:120]  # 表示用に120文字まで
        mem_id = mem.get("id", "")
        memory_choices.append((content, mem_id))

    # フィードバック一覧
    feedback_choices = []
    for i, fb in enumerate(feedbacks):
        text = fb.get("feedback", "")[:100]
        feedback_choices.append((text, str(i)))

    return memory_choices, feedback_choices


def trigger_dream_with_selection(selected_memory_ids: list, selected_feedback_ids: list):
    """Trigger dreaming cycle with selected memories and feedback"""
    # TODO: 選択的な夢見を実装（現在は全記憶で実行）
    result = engine.trigger_dream()

    if result["status"] == "completed":
        generated_memories = "\n".join([f"- {ins}" for ins in result.get("insights", [])])
        return f"""### 🌙 夢見完了！

**【夢見入力】**
- 使用した記憶: {result.get('memories_processed', 0)}件 → アーカイブに移動
- ユーザーフィードバック: {result.get('feedbacks_used', 0)}件

**【生成された記憶】**（ChromaDBに保存済み）
{generated_memories}

処理時間: {result.get('duration_seconds', 0):.1f}秒
"""
    elif result["status"] == "skipped":
        return f"⏭️ スキップ: {result.get('reason', '')}"
    else:
        return f"❌ 失敗: {result.get('reason', '')}"


def trigger_dream():
    """Trigger dreaming cycle (legacy - all memories)"""
    return trigger_dream_with_selection([], [])


def reset_memory():
    """Reset all memories"""
    result = engine.reset_memory()
    return f"""### 🗑️ 記憶リセット完了

- ChromaDB: {result.get('chromadb_deleted', 0)}件 削除
- インサイト: {result.get('insights_deleted', 0)}件 削除
- フィードバック: {result.get('feedback_deleted', 0)}件 削除

記憶が初期化されました。"""


def reset_everything():
    """Reset ALL data including archives and logs"""
    result = engine.reset_everything()
    return f"""### ⚠️ 完全リセット完了

**記憶データ:**
- ChromaDB: {result.get('chromadb_deleted', 0)}件 削除
- インサイト: {result.get('insights_deleted', 0)}件 削除
- フィードバック: {result.get('feedback_deleted', 0)}件 削除

**アーカイブ・ログ:**
- 記憶アーカイブ: {result.get('memory_archive_deleted', 0)}件 削除
- 夢見アーカイブ: {result.get('dream_archives_deleted', 0)}件 削除
- インサイトアーカイブ: {result.get('insights_archived_deleted', 0)}件 削除
- フィードバックアーカイブ: {result.get('feedback_archived_deleted', 0)}件 削除

全てのデータが完全に削除されました。"""


# ========== Settings Handlers ==========

def test_connection():
    """Test LM Studio connection"""
    result = engine.check_connection()
    if result["status"] == "connected":
        models = ", ".join(result.get("loaded_model_names", []))
        return f"✅ 接続成功\nロード済みモデル: {models or 'なし (JITで自動ロード)'}"
    elif result["status"] == "disconnected":
        return "❌ LM Studioに接続できません。起動していますか？"
    else:
        return f"❌ エラー: {result.get('error', '')}"


def save_settings(host, port, api_token, context_length, dream_threshold, search_threshold, auto_save_exchange, selected_model):
    """Save user settings including model selection"""
    logger.info(f"save_settings called with selected_model={selected_model}, context_length={context_length}")

    updates = {
        "lm_studio": {
            "host": host,
            "port": int(port),
            "api_token": api_token,
            "context_length": int(context_length),
        },
        "dreaming": {
            "memory_threshold": int(dream_threshold),
        },
        "search_relevance_threshold": float(search_threshold),
        "auto_save_exchange": bool(auto_save_exchange),
        "selected_model": selected_model,
    }

    if save_config(updates):
        # Reinitialize engine with new config
        global engine, config
        config = load_config()
        logger.info(f"After reload, config selected_model={config.get('selected_model')}")
        engine = AwarenessEngine(config=config, data_dir=data_dir)
        logger.info(f"Engine lm_client.selected_model={engine.lm_client.selected_model}")
        return f"✅ 設定を保存しました（モデル: {selected_model or '自動検出'}）"
    else:
        return "❌ 設定の保存に失敗しました"


# ========== Prompt & Model Handlers ==========

def get_model_choices():
    """Get available models from LM Studio"""
    try:
        models = engine.get_available_models()
        # Get saved selection from config file (reload to get latest)
        current_config = load_config()
        saved_model = current_config.get("selected_model", "")
        logger.info(f"get_model_choices: models={models}, saved_model={saved_model}")
        if models:
            # If saved model exists in list, use it; otherwise use first model
            if saved_model and saved_model in models:
                return models, saved_model
            return models, models[0]
        return ["(モデルなし)"], "(モデルなし)"
    except Exception as e:
        logger.error(f"get_model_choices error: {e}")
        return ["(接続エラー)"], "(接続エラー)"


def refresh_models():
    """Refresh model list from LM Studio"""
    try:
        models = engine.get_available_models()
        logger.info(f"refresh_models: found {len(models)} models: {models}")
        if models:
            # Don't auto-select - just update the list, keep current dropdown value
            return gr.update(choices=models)
        return gr.update(choices=["(モデルなし)"])
    except Exception as e:
        logger.error(f"refresh_models error: {e}")
        return gr.update(choices=["(接続エラー)"])


def update_context_slider_max(selected_model: str):
    """Update context length slider maximum based on selected model"""
    try:
        if not selected_model or selected_model in ["(モデルなし)", "(接続エラー)"]:
            return gr.update()

        model_info = engine.get_model_info(selected_model)
        max_ctx = model_info.get("max_context_length", 32000)
        logger.info(f"Model {selected_model}: max_context_length={max_ctx}")

        # Get current value from config
        current_value = config.get("lm_studio", {}).get("context_length", 32000)
        # Clamp current value to new maximum
        new_value = min(current_value, max_ctx)

        return gr.update(maximum=max_ctx, value=new_value)
    except Exception as e:
        logger.error(f"update_context_slider_max error: {e}")
        return gr.update()


def save_prompts(system_prompt, dream_prompt, selected_model):
    """Save system prompts and model selection"""
    updates = {
        "system_prompt": system_prompt,
        "dream_prompt": dream_prompt,
        "selected_model": selected_model,
    }

    if save_config(updates):
        global engine, config
        config = load_config()
        engine = AwarenessEngine(config=config, data_dir=data_dir)
        return "✅ プロンプトを保存しました"
    else:
        return "❌ 保存に失敗しました"


def get_preset_choices():
    """Get preset list for dropdown"""
    presets = load_presets()
    return [(v["name"], k) for k, v in presets.items()]


def load_preset_prompts(preset_id):
    """Load prompts from a preset"""
    presets = load_presets()
    if preset_id in presets:
        preset = presets[preset_id]
        return preset["system_prompt"], preset["dream_prompt"], f"✅ 「{preset['name']}」を読み込みました"
    return "", "", "❌ プリセットが見つかりません"


def save_new_preset(preset_name, system_prompt, dream_prompt):
    """Save current prompts as a new preset"""
    if not preset_name.strip():
        return gr.update(), "❌ プリセット名を入力してください"

    # Generate ID from name
    import re
    preset_id = re.sub(r'[^\w]', '_', preset_name.lower())

    if save_preset(preset_id, preset_name, system_prompt, dream_prompt):
        choices = get_preset_choices()
        return gr.update(choices=choices, value=preset_id), f"✅ 「{preset_name}」を保存しました"
    else:
        return gr.update(), "❌ 保存に失敗しました"


def delete_current_preset(preset_id):
    """Delete the selected preset"""
    if preset_id == "default":
        return gr.update(), "❌ デフォルトプリセットは削除できません"

    presets = load_presets()
    preset_name = presets.get(preset_id, {}).get("name", preset_id)

    if delete_preset(preset_id):
        choices = get_preset_choices()
        return gr.update(choices=choices, value="default"), f"✅ 「{preset_name}」を削除しました"
    else:
        return gr.update(), "❌ 削除に失敗しました"


def reset_to_default():
    """Reset prompts to default values"""
    return SYSTEM_PROMPT, DREAM_PROMPT, "✅ デフォルトに戻しました"


# ========== Build UI ==========

def create_app():
    """Create Gradio application"""
    with gr.Blocks(
        title="LLM Awareness Engine",
    ) as app:

        with gr.Row():
            with gr.Column(scale=9):
                gr.Markdown("# 🧠 LLM Awareness Engine")
            with gr.Column(scale=1):
                shutdown_btn = gr.Button("🛑 終了", variant="stop", size="sm")

        gr.Markdown("*言語が言語自身を処理する*")

        with gr.Tabs():
            # ========== Tab 1: Chat ==========
            with gr.TabItem("💬 チャット"):
                with gr.Row():
                    with gr.Column(scale=3):
                        chatbot = gr.Chatbot(
                            height=500,
                            label="対話",
                            buttons=["copy"],
                        )
                        with gr.Row():
                            msg_input = gr.Textbox(
                                placeholder="メッセージを入力...",
                                label="入力",
                                scale=5,
                                lines=1,
                                max_lines=5,
                            )
                            send_btn = gr.Button("送信", variant="primary", scale=1)

                        with gr.Row():
                            clear_btn = gr.Button("🗑️ 会話クリア")
                            copy_chat_btn = gr.Button("📋 全体コピー")

                    with gr.Column(scale=2):
                        insight_display = gr.Markdown(
                            value="",
                            label="観察・保存記憶",
                        )

                        gr.Markdown("### 📝 フィードバック")
                        feedback_input = gr.Textbox(
                            placeholder="応答への感想や改善点を入力...",
                            label="フィードバック",
                            lines=2,
                        )
                        feedback_btn = gr.Button("フィードバック送信")
                        feedback_status = gr.Textbox(
                            label="ステータス",
                            interactive=False,
                        )

                # Chat events (time_limit=600 for long LLM responses)
                send_btn.click(
                    send_message,
                    inputs=[msg_input, chatbot],
                    outputs=[chatbot, msg_input, insight_display],
                    time_limit=600,
                )
                msg_input.submit(
                    send_message,
                    inputs=[msg_input, chatbot],
                    outputs=[chatbot, msg_input, insight_display],
                    time_limit=600,
                )
                clear_btn.click(
                    clear_chat,
                    outputs=[chatbot, msg_input, insight_display],
                )

                # Hidden textbox to hold formatted chat for copying
                copy_text = gr.Textbox(visible=False)

                copy_chat_btn.click(
                    format_chat_for_copy,
                    inputs=[chatbot],
                    outputs=[copy_text],
                ).then(
                    None,
                    inputs=[copy_text],
                    js="(text) => { navigator.clipboard.writeText(text); }",
                )

                feedback_btn.click(
                    submit_feedback,
                    inputs=[feedback_input],
                    outputs=[feedback_status, feedback_input],
                )

            # ========== Tab 2: Dashboard (統計のみ) ==========
            with gr.TabItem("📊 ダッシュボード"):
                with gr.Row():
                    refresh_btn = gr.Button("🔄 更新")

                stats_display = gr.Markdown(label="統計")

                # Dashboard events
                refresh_btn.click(
                    get_dashboard_data,
                    outputs=[stats_display],
                )

            # ========== Tab 3: Dream (記憶選択 + 夢見実行) ==========
            with gr.TabItem("🌙 夢見"):
                with gr.Row():
                    refresh_dream_btn = gr.Button("🔄 一覧を更新")
                    dream_btn = gr.Button(
                        "🌙 夢見を実行",
                        variant="primary",
                        elem_classes=["dream-button"],
                    )
                    delete_selected_btn = gr.Button(
                        "🗑️ 選択した記憶を削除",
                        variant="stop",
                    )

                dream_result = gr.Markdown(label="結果")

                gr.Markdown("---")
                gr.Markdown("### 📦 ChromaDB記憶一覧")
                with gr.Row():
                    select_all_btn = gr.Button("☑️ 全選択", size="sm")
                    deselect_all_btn = gr.Button("☐ 全解除", size="sm")

                memory_checkboxes = gr.CheckboxGroup(
                    choices=[],
                    label="記憶一覧",
                    value=[],
                )

                gr.Markdown("---")
                gr.Markdown("### 💬 ユーザーフィードバック一覧")

                feedback_checkboxes = gr.CheckboxGroup(
                    choices=[],
                    label="フィードバック一覧",
                    value=[],
                )

                # ========== アーカイブセクション ==========
                gr.Markdown("---")
                gr.Markdown("### 📁 アーカイブ（夢見で使用済みの記憶）")
                gr.Markdown("*夢見処理で統合された記憶がここに保存されています。必要に応じて復元できます。*")

                with gr.Row():
                    refresh_archive_btn = gr.Button("🔄 更新", size="sm")
                    select_all_archive_btn = gr.Button("☑️ 全選択", size="sm")
                    deselect_all_archive_btn = gr.Button("☐ 全解除", size="sm")
                    restore_btn = gr.Button("♻️ 選択を復元", variant="primary", size="sm")
                    delete_archive_btn = gr.Button("🗑️ 完全に削除", variant="stop", size="sm")

                archive_status = gr.Markdown("")

                archive_checkboxes = gr.CheckboxGroup(
                    choices=[],
                    label="アーカイブ一覧",
                    value=[],
                )

                # Dream tab events
                def refresh_dream_lists():
                    memory_choices, feedback_choices = get_dream_data()
                    # 全選択状態で返す
                    memory_values = [m[1] for m in memory_choices]
                    feedback_values = [f[1] for f in feedback_choices]
                    return (
                        gr.update(choices=memory_choices, value=memory_values),
                        gr.update(choices=feedback_choices, value=feedback_values),
                    )

                def show_processing():
                    return "### ⏳ 夢見処理中...\n\n*MCPツールを使って記憶を統合しています。しばらくお待ちください...*"

                def delete_selected_memories(selected_ids):
                    if not selected_ids:
                        return "⚠️ 削除する記憶を選択してください"
                    result = engine.memory.batch_delete(selected_ids)
                    return f"✅ {result['deleted_count']}件の記憶を削除しました"

                # 全選択/全解除関数
                def select_all_memories():
                    memory_choices, _ = get_dream_data()
                    all_ids = [m[1] for m in memory_choices]
                    return gr.update(value=all_ids)

                def deselect_all_memories():
                    return gr.update(value=[])

                # アーカイブ用関数
                def get_archive_data():
                    """アーカイブから記憶一覧を取得"""
                    archived = engine.memory.get_archived_memories()
                    choices = []
                    for i, entry in enumerate(archived):
                        content = entry.get("content", "")[:80]
                        archived_at = entry.get("archived_at", "")[:10]
                        choices.append((f"[{archived_at}] {content}", str(i)))
                    return gr.update(choices=choices, value=[])

                def select_all_archive():
                    """アーカイブ全選択"""
                    archived = engine.memory.get_archived_memories()
                    all_ids = [str(i) for i in range(len(archived))]
                    return gr.update(value=all_ids)

                def deselect_all_archive():
                    """アーカイブ全解除"""
                    return gr.update(value=[])

                def restore_selected_archive(selected_indices):
                    """選択したアーカイブを復元"""
                    if not selected_indices:
                        return "⚠️ 復元する記憶を選択してください"
                    indices = [int(i) for i in selected_indices]
                    result = engine.memory.restore_memories(indices)
                    return f"✅ {result['restored_count']}件の記憶を復元しました"

                def delete_selected_archive(selected_indices):
                    """選択したアーカイブを完全削除"""
                    if not selected_indices:
                        return "⚠️ 削除する記憶を選択してください"
                    indices = [int(i) for i in selected_indices]
                    result = engine.memory.delete_archived_memories(indices)
                    return f"✅ {result['deleted_count']}件の記憶を完全に削除しました"

                refresh_dream_btn.click(
                    refresh_dream_lists,
                    outputs=[memory_checkboxes, feedback_checkboxes],
                )
                # 全選択/全解除ボタン
                select_all_btn.click(
                    select_all_memories,
                    outputs=[memory_checkboxes],
                )
                deselect_all_btn.click(
                    deselect_all_memories,
                    outputs=[memory_checkboxes],
                )
                # 夢見ボタン: まず「処理中」を表示してから実行
                dream_btn.click(
                    show_processing,
                    outputs=[dream_result],
                ).then(
                    trigger_dream_with_selection,
                    inputs=[memory_checkboxes, feedback_checkboxes],
                    outputs=[dream_result],
                ).then(
                    refresh_dream_lists,
                    outputs=[memory_checkboxes, feedback_checkboxes],
                ).then(
                    get_archive_data,
                    outputs=[archive_checkboxes],
                )
                # 削除ボタン
                delete_selected_btn.click(
                    delete_selected_memories,
                    inputs=[memory_checkboxes],
                    outputs=[dream_result],
                ).then(
                    refresh_dream_lists,
                    outputs=[memory_checkboxes, feedback_checkboxes],
                )

                # アーカイブ操作
                refresh_archive_btn.click(
                    get_archive_data,
                    outputs=[archive_checkboxes],
                )
                select_all_archive_btn.click(
                    select_all_archive,
                    outputs=[archive_checkboxes],
                )
                deselect_all_archive_btn.click(
                    deselect_all_archive,
                    outputs=[archive_checkboxes],
                )
                restore_btn.click(
                    restore_selected_archive,
                    inputs=[archive_checkboxes],
                    outputs=[archive_status],
                ).then(
                    get_archive_data,
                    outputs=[archive_checkboxes],
                ).then(
                    refresh_dream_lists,
                    outputs=[memory_checkboxes, feedback_checkboxes],
                )
                delete_archive_btn.click(
                    delete_selected_archive,
                    inputs=[archive_checkboxes],
                    outputs=[archive_status],
                ).then(
                    get_archive_data,
                    outputs=[archive_checkboxes],
                )

                # Auto-refresh on tab load
                app.load(
                    get_dashboard_data,
                    outputs=[stats_display],
                )

            # ========== Tab 4: Settings ==========
            with gr.TabItem("⚙️ 設定"):

                with gr.Tabs():
                    # ===== Sub-tab: Prompts =====
                    with gr.TabItem("📝 プロンプト"):
                        gr.Markdown("### システムプロンプト設定")

                        # Preset management
                        with gr.Row():
                            preset_dropdown = gr.Dropdown(
                                choices=get_preset_choices(),
                                value="default",
                                label="プリセット",
                                scale=3,
                            )
                            load_preset_btn = gr.Button("📂 読込", scale=1)
                            delete_preset_btn = gr.Button("🗑️ 削除", scale=1)

                        with gr.Row():
                            new_preset_name = gr.Textbox(
                                placeholder="新しいプリセット名...",
                                label="プリセット名",
                                scale=3,
                            )
                            save_preset_btn = gr.Button("💾 新規保存", scale=1)

                        preset_status = gr.Textbox(label="ステータス", interactive=False)

                        gr.Markdown("---")

                        # Chat system prompt
                        gr.Markdown("#### 💬 チャット用システムプロンプト")
                        system_prompt_input = gr.Textbox(
                            value=config.get("system_prompt", SYSTEM_PROMPT),
                            label="",
                            lines=12,
                            max_lines=20,
                        )

                        gr.Markdown("#### 🌙 夢見用プロンプト")
                        gr.Markdown("*`{user_feedback}`, `{saved_memories}` が自動置換されます*")
                        dream_prompt_input = gr.Textbox(
                            value=config.get("dream_prompt", DREAM_PROMPT),
                            label="",
                            lines=12,
                            max_lines=20,
                        )

                        gr.Markdown("---")

                        with gr.Row():
                            reset_prompts_btn = gr.Button("🔄 デフォルトに戻す")
                            save_prompts_btn = gr.Button("💾 プロンプトを保存", variant="primary")

                        prompts_status = gr.Textbox(label="保存状態", interactive=False)

                        # Prompt events
                        load_preset_btn.click(
                            load_preset_prompts,
                            inputs=[preset_dropdown],
                            outputs=[system_prompt_input, dream_prompt_input, preset_status],
                        )
                        save_preset_btn.click(
                            save_new_preset,
                            inputs=[new_preset_name, system_prompt_input, dream_prompt_input],
                            outputs=[preset_dropdown, preset_status],
                        )
                        delete_preset_btn.click(
                            delete_current_preset,
                            inputs=[preset_dropdown],
                            outputs=[preset_dropdown, preset_status],
                        )
                        reset_prompts_btn.click(
                            reset_to_default,
                            outputs=[system_prompt_input, dream_prompt_input, prompts_status],
                        )

                    # ===== Sub-tab: Model & Connection =====
                    with gr.TabItem("🔌 接続・モデル"):
                        gr.Markdown("### LM Studio 接続設定")

                        with gr.Row():
                            host_input = gr.Textbox(
                                value=config.get("lm_studio", {}).get("host", "localhost"),
                                label="Host",
                            )
                            port_input = gr.Number(
                                value=config.get("lm_studio", {}).get("port", 1234),
                                label="Port",
                                precision=0,
                            )

                        api_token_input = gr.Textbox(
                            value=config.get("lm_studio", {}).get("api_token", ""),
                            label="API Token",
                            type="password",
                        )

                        conn_btn = gr.Button("接続テスト")
                        conn_status = gr.Textbox(label="接続状態", interactive=False)

                        gr.Markdown("---")
                        gr.Markdown("### 🤖 モデル選択")

                        models, current_model = get_model_choices()
                        with gr.Row():
                            model_dropdown = gr.Dropdown(
                                choices=models,
                                value=config.get("selected_model") or current_model,
                                label="使用モデル",
                                scale=4,
                            )
                            refresh_models_btn = gr.Button("🔄 更新", scale=1)

                        gr.Markdown("*LM Studioで読み込んだモデルが表示されます*")

                        gr.Markdown("---")
                        gr.Markdown("### コンテキスト長")

                        # 選択中モデルのmax_context_lengthを取得
                        initial_model = config.get("selected_model") or current_model
                        initial_max_ctx = 131072  # fallback
                        if initial_model and initial_model not in ["(モデルなし)", "(接続エラー)"]:
                            try:
                                model_info = engine.get_model_info(initial_model)
                                initial_max_ctx = model_info.get("max_context_length", 131072)
                            except Exception:
                                pass

                        context_length_slider = gr.Slider(
                            minimum=4096,
                            maximum=initial_max_ctx,
                            step=1024,
                            value=min(config.get("lm_studio", {}).get("context_length", 32000), initial_max_ctx),
                            label="コンテキスト長（トークン数）",
                        )
                        gr.Markdown("*モデル変更時に最大値が自動調整されます。長いほどVRAM使用量が増加します。*")

                        gr.Markdown("---")
                        gr.Markdown("### 🔍 記憶検索設定")

                        search_threshold_slider = gr.Slider(
                            minimum=0.5,
                            maximum=1.0,
                            step=0.01,
                            value=config.get("search_relevance_threshold", 0.85),
                            label="検索閾値（この値未満の結果は除外）",
                        )
                        gr.Markdown("*高いほど厳格。0.85推奨。*")

                        gr.Markdown("---")
                        gr.Markdown("### 💾 自動保存設定")

                        auto_save_checkbox = gr.Checkbox(
                            value=config.get("auto_save_exchange", True),
                            label="入出力ペアを自動保存（category: exchange）",
                        )

                        gr.Markdown("---")
                        gr.Markdown("### 夢見設定")

                        dream_threshold_input = gr.Number(
                            value=config.get("dreaming", {}).get("memory_threshold", 30),
                            label="夢見トリガー閾値（メモリ数）",
                            precision=0,
                        )

                        save_btn = gr.Button("設定を保存", variant="primary")
                        save_status = gr.Textbox(label="保存状態", interactive=False)

                        # Connection & Model events
                        conn_btn.click(
                            test_connection,
                            outputs=[conn_status],
                        )
                        refresh_models_btn.click(
                            refresh_models,
                            outputs=[model_dropdown],
                        )
                        # モデル選択時にスライダーの最大値を更新
                        model_dropdown.change(
                            update_context_slider_max,
                            inputs=[model_dropdown],
                            outputs=[context_length_slider],
                        )
                        save_btn.click(
                            save_settings,
                            inputs=[host_input, port_input, api_token_input, context_length_slider, dream_threshold_input, search_threshold_slider, auto_save_checkbox, model_dropdown],
                            outputs=[save_status],
                        )

                        # Save prompts with model (connected to prompts tab)
                        save_prompts_btn.click(
                            save_prompts,
                            inputs=[system_prompt_input, dream_prompt_input, model_dropdown],
                            outputs=[prompts_status],
                        )

                    # ===== Sub-tab: Data Reset =====
                    with gr.TabItem("🗑️ データ管理"):
                        gr.Markdown("### データリセット")

                        gr.Markdown("**通常リセット**: 記憶、フィードバック、思考ログを削除（アーカイブは保持）")
                        reset_btn = gr.Button(
                            "🗑️ 記憶を消去",
                            variant="stop",
                        )

                        gr.Markdown("---")

                        gr.Markdown("**完全リセット**: 全データ（記憶 + アーカイブ + ログ全て）を完全削除")
                        reset_all_btn = gr.Button(
                            "⚠️ 全データを完全消去",
                            variant="stop",
                        )

                        reset_result = gr.Markdown(label="リセット結果")

                        reset_btn.click(
                            reset_memory,
                            outputs=[reset_result],
                        )
                        reset_all_btn.click(
                            reset_everything,
                            outputs=[reset_result],
                        )

        # ========== Global: Shutdown Button ==========
        def shutdown_server():
            """Gradioサーバーを停止してポートを解放"""
            import os
            os._exit(0)

        shutdown_btn.click(
            shutdown_server,
            inputs=[],
            outputs=[],
        )

    # Enable queue with longer timeout for LLM responses
    app.queue(default_concurrency_limit=1)

    return app


# ========== Entry Point ==========

def main():
    """Launch the application"""
    app = create_app()

    # Try ports 7860-7863
    for port in range(7860, 7864):
        try:
            app.launch(
                server_name="127.0.0.1",
                server_port=port,
                share=False,
                inbrowser=True,
                css=CUSTOM_CSS,
                theme=gr.themes.Soft(),
            )
            break
        except OSError:
            logger.warning(f"Port {port} in use, trying next...")
            continue


if __name__ == "__main__":
    main()
