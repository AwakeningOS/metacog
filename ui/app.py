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

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.default_config import load_config, save_config
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
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #4a4a6a;
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

    # Format insights for display
    insights = metadata.get("insights", [])
    saves = metadata.get("saves", [])
    insight_display = ""
    if insights:
        insight_display += "### 💭 気づき\n"
        for ins in insights:
            insight_display += f"- {ins}\n"
    if saves:
        insight_display += "\n### 💾 保存した記憶\n"
        for s in saves:
            insight_display += f"- {s}\n"

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


# ========== Dashboard Handlers ==========

def get_dashboard_data():
    """Get dashboard statistics"""
    stats = engine.get_stats()
    threshold = engine.check_dream_threshold()

    # Format stats
    stats_text = f"""### 📦 記憶 (ChromaDB)

| 種別 | 件数 | 備考 |
|---|---|---|
| LLM自発メモリ | {stats['llm_memory_count']} | MCP経由で保存 |
| 気づき | {stats['insight_count']} | 蒸留対象 |
| 夢見インサイト | {stats['dream_insight_count']} | 蒸留対象 |
| **合計** | **{stats['total_chromadb']}** | |

### 💬 フィードバック: {stats['feedback_count']}件
### 🌙 夢見: {stats['dream_cycles']}回

---
- 蒸留閾値: **{threshold['current_count']}** / **{threshold['threshold']}**
- 夢見推奨: {'**はい** ✨' if threshold['should_dream'] else 'いいえ'}
"""

    # Format insights
    insights = engine.memory.get_insights(limit=10)
    if insights:
        insight_lines = ["### 最新のインサイト\n"]
        for entry in reversed(insights):
            insight = entry.get("insight", "")
            source = entry.get("source", "")
            insight_lines.append(f"- [{source}] {insight}")
        insights_text = "\n".join(insight_lines)
    else:
        insights_text = "インサイトはまだありません"

    return stats_text, insights_text


def trigger_dream():
    """Trigger dreaming cycle"""
    result = engine.trigger_dream()

    if result["status"] == "completed":
        insights_text = "\n".join([f"- {ins}" for ins in result.get("insights", [])])
        return f"""### 🌙 夢見完了！

- 処理した記憶: {result.get('memories_processed', 0)}
- 削除した記憶: {result.get('memories_deleted', 0)}
- 使用したフィードバック: {result.get('feedbacks_used', 0)}
- 生成したインサイト: {result.get('insights_generated', 0)}
- 処理時間: {result.get('duration_seconds', 0):.1f}秒

### 生成されたインサイト
{insights_text}
"""
    elif result["status"] == "skipped":
        return f"⏭️ スキップ: {result.get('reason', '')}"
    else:
        return f"❌ 失敗: {result.get('reason', '')}"


def reset_memory():
    """Reset all memories"""
    result = engine.reset_memory()
    return f"""### 🗑️ 記憶リセット完了

- ChromaDB: {result.get('chromadb_deleted', 0)}件 削除
- インサイト: {result.get('insights_deleted', 0)}件 削除
- フィードバック: {result.get('feedback_deleted', 0)}件 削除
- 思考ログ: {result.get('thought_logs_deleted', 0)}件 削除

記憶が初期化されました。"""


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


def save_settings(host, port, api_token, dream_threshold):
    """Save user settings"""
    updates = {
        "lm_studio": {
            "host": host,
            "port": int(port),
            "api_token": api_token,
        },
        "dreaming": {
            "memory_threshold": int(dream_threshold),
        },
    }

    if save_config(updates):
        # Reinitialize engine with new config
        global engine, config
        config = load_config()
        engine = AwarenessEngine(config=config, data_dir=data_dir)
        return "✅ 設定を保存しました"
    else:
        return "❌ 設定の保存に失敗しました"


# ========== Build UI ==========

def create_app():
    """Create Gradio application"""
    with gr.Blocks(
        title="LLM Awareness Engine",
    ) as app:

        gr.Markdown("# 🧠 LLM Awareness Engine")
        gr.Markdown("*気づきは命じるものではなく、創発するもの*")

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
                                lines=2,
                            )
                            send_btn = gr.Button("送信", variant="primary", scale=1)

                        with gr.Row():
                            clear_btn = gr.Button("🗑️ 会話クリア")

                    with gr.Column(scale=2):
                        insight_display = gr.Markdown(
                            value="",
                            label="気づき・保存記憶",
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

                # Chat events
                send_btn.click(
                    send_message,
                    inputs=[msg_input, chatbot],
                    outputs=[chatbot, msg_input, insight_display],
                )
                msg_input.submit(
                    send_message,
                    inputs=[msg_input, chatbot],
                    outputs=[chatbot, msg_input, insight_display],
                )
                clear_btn.click(
                    clear_chat,
                    outputs=[chatbot, msg_input, insight_display],
                )
                feedback_btn.click(
                    submit_feedback,
                    inputs=[feedback_input],
                    outputs=[feedback_status, feedback_input],
                )

            # ========== Tab 2: Dashboard ==========
            with gr.TabItem("📊 ダッシュボード"):
                with gr.Row():
                    refresh_btn = gr.Button("🔄 更新")

                with gr.Row():
                    with gr.Column():
                        stats_display = gr.Markdown(label="統計")
                    with gr.Column():
                        insights_display = gr.Markdown(label="インサイト")

                gr.Markdown("---")
                gr.Markdown("### 🌙 夢見モード")
                dream_btn = gr.Button(
                    "🌙 今すぐ夢見を実行",
                    variant="primary",
                    elem_classes=["dream-button"],
                )
                dream_result = gr.Markdown(label="夢見結果")

                gr.Markdown("---")
                gr.Markdown("### 🗑️ 記憶リセット")
                reset_btn = gr.Button(
                    "🗑️ 全記憶を消去",
                    variant="stop",
                )
                reset_result = gr.Markdown(label="リセット結果")

                # Dashboard events
                refresh_btn.click(
                    get_dashboard_data,
                    outputs=[stats_display, insights_display],
                )
                dream_btn.click(
                    trigger_dream,
                    outputs=[dream_result],
                )
                reset_btn.click(
                    reset_memory,
                    outputs=[reset_result],
                )

                # Auto-refresh on tab load
                app.load(
                    get_dashboard_data,
                    outputs=[stats_display, insights_display],
                )

            # ========== Tab 3: Settings ==========
            with gr.TabItem("⚙️ 設定"):
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
                gr.Markdown("### 夢見設定")

                dream_threshold_input = gr.Number(
                    value=config.get("dreaming", {}).get("memory_threshold", 30),
                    label="夢見トリガー閾値（メモリ数）",
                    precision=0,
                )

                save_btn = gr.Button("設定を保存", variant="primary")
                save_status = gr.Textbox(label="保存状態", interactive=False)

                # Settings events
                conn_btn.click(
                    test_connection,
                    outputs=[conn_status],
                )
                save_btn.click(
                    save_settings,
                    inputs=[host_input, port_input, api_token_input, dream_threshold_input],
                    outputs=[save_status],
                )

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
