# Metacog アーキテクチャ設計書

このドキュメントは、Metacogの内部構造を理解し、拡張・改造するための技術資料です。

---

## 概要

Metacogは「LLMの自己認識・記憶・夢見」を実現するシステムです。

**コア思想**: LLMが自分の思考を観察し、記憶を蓄積し、定期的な「夢見」で統合学習する。

```
ユーザー入力 → システムプロンプト + MCP → LLM応答 → 記憶保存
                                              ↓
                                     夢見（記憶統合）
                                              ↓
                                     洞察として再利用
```

---

## ディレクトリ構造

```
metacog/
├── metacog.py              # エントリーポイント（ui/app.pyを呼び出すだけ）
├── config/
│   └── default_config.py   # 設定管理・デフォルト値・プリセット
├── engine/
│   ├── core.py             # メインオーケストレーター（AwarenessEngine）
│   ├── lm_studio.py        # LM Studio API クライアント
│   ├── memory.py           # 統合メモリシステム（ChromaDB + JSONL）
│   ├── dreaming.py         # 夢見エンジン
│   ├── prompt_builder.py   # システムプロンプト構築
│   └── response_parser.py  # LLM応答のパース（気づき・保存抽出）
├── ui/
│   └── app.py              # Gradio UI（全タブ定義）
├── data/                   # 実行時データ（gitignore）
│   ├── chromadb/           # ベクトルDB
│   ├── feedback.jsonl      # ユーザーフィードバック
│   ├── insights.jsonl      # 夢見で生成された洞察
│   └── dream_archives.jsonl # 夢見履歴
└── presets/                # プロンプトプリセット
```

---

## コアコンポーネント詳細

### 1. `engine/core.py` - AwarenessEngine

**役割**: 全コンポーネントを統合するオーケストレーター

```python
class AwarenessEngine:
    def __init__(self, config, data_dir):
        self.memory = UnifiedMemory(...)      # 記憶システム
        self.prompt_builder = SystemPromptBuilder(...)  # プロンプト構築
        self.lm_client = LMStudioClient(...)  # LLM API
        self._dreaming = None                  # 遅延初期化
```

**主要メソッド**:

| メソッド | 説明 |
|----------|------|
| `send_message(user_input)` | チャット1ターン処理。LLM呼び出し→応答パース→記憶保存 |
| `submit_feedback(feedback)` | ユーザーフィードバック保存（夢見で最優先処理） |
| `trigger_dream()` | 夢見実行 |
| `check_connection()` | LM Studio接続確認 |
| `get_available_models()` | 利用可能モデル一覧取得 |
| `get_model_info(model_key)` | モデル詳細情報（max_context_length等）取得 |

**データフロー（send_message）**:
```
1. prompt_builder.build() → システムプロンプト取得
2. lm_client.chat() → LLM API呼び出し（MCP統合あり）
3. response_parser.parse() → 応答から気づき・保存指示を抽出
4. memory.save_insight() → 気づきを保存
5. memory.save() → [SAVE]タグの内容を保存
6. 会話履歴更新
```

---

### 2. `engine/lm_studio.py` - LMStudioClient

**役割**: LM Studio MCP API との通信

**重要**: OpenAI互換APIではなく、`/api/v1/chat`（MCP統合API）を使用

```python
class LMStudioClient:
    def chat(
        self,
        input_text: str,
        system_prompt: str,
        integrations: list[str],  # ["mcp/sequential-thinking", "mcp/memory_tools"]
        context_length: int,
        temperature: float,
    ) -> tuple[str, dict]:
```

**APIペイロード構造**:
```json
{
  "input": "ユーザー入力",
  "model": "モデル名",
  "system_prompt": "システムプロンプト",
  "integrations": ["mcp/sequential-thinking"],
  "context_length": 32000,
  "temperature": 0.7
}
```

**レスポンス解析**:
- `output[].type == "message"` → 最終応答テキスト
- `output[].type == "tool_call"` → MCPツール呼び出し結果
  - `tool == "sequentialthinking"` → 思考過程を抽出

---

### 3. `engine/memory.py` - UnifiedMemory

**役割**: 記憶の保存・検索・エクスポート

**ストレージ構成**:

| ストレージ | 形式 | 用途 |
|------------|------|------|
| ChromaDB | ベクトルDB | 記憶本体（類似検索可能） |
| `feedback.jsonl` | JSONL | ユーザーフィードバック |
| `insights.jsonl` | JSONL | 夢見で生成された洞察 |
| `memory_archive.jsonl` | JSONL | 夢見で処理済みの記憶 |

**主要メソッド**:

```python
# 保存
save(content, category="chat"|"dream")
save_insight(insight, source)
save_feedback(feedback, context)

# 検索
search(query, limit=5)  # ベクトル類似検索
get_feedback()          # 全フィードバック取得
get_insights()          # 全洞察取得

# 夢見用エクスポート
export_for_dreaming() -> {
    "memories": [...],   # ChromaDBの全記憶
    "feedback": [...],   # 未処理フィードバック
}

# リセット
reset_all()         # 記憶のみ削除（アーカイブ保持）
reset_everything()  # 全データ削除
```

**カテゴリ**:
- `chat`: チャット中に保存された記憶
- `dream`: 夢見で生成された記憶
- `insight`: 気づき（システムプロンプトに注入される）

---

### 4. `engine/dreaming.py` - DreamingEngine

**役割**: 蓄積された記憶を統合し、洞察を生成

**処理フロー**:
```
1. memory.export_for_dreaming() → 記憶・フィードバック取得
2. 夢見プロンプト構築（{user_feedback}, {saved_memories}を置換）
3. lm_client.chat() → LLM呼び出し（MCPあり）
4. 応答から洞察を抽出
5. 洞察をChromaDB + insights.jsonlに保存
6. 処理済み記憶をアーカイブに移動
7. フィードバックをクリア
```

**夢見プロンプトの変数**:
- `{user_feedback}`: ユーザーからの修正指示（最優先）
- `{saved_memories}`: ChromaDBの記憶一覧

---

### 5. `engine/prompt_builder.py` - SystemPromptBuilder

**役割**: 動的なシステムプロンプト構築

```python
class SystemPromptBuilder:
    def build(self) -> str:
        # 設定ファイルから最新のプロンプトを読み込む
        config = load_config()
        return config.get("system_prompt", SYSTEM_PROMPT)
```

**重要**: `build()`は毎回configを再読み込みする（UI変更が即反映される）

---

### 6. `engine/response_parser.py` - ResponseParser

**役割**: LLM応答から構造化データを抽出

**抽出対象**:

| パターン | 説明 |
|----------|------|
| `## 気づき` セクション | 箇条書きの気づきを抽出 |
| `[SAVE]...[/SAVE]` | 明示的な保存指示 |

```python
def parse(self, response: str) -> dict:
    return {
        "response": "ユーザーへの応答本文",
        "insights": ["気づき1", "気づき2"],
        "saves": ["保存内容1"],
    }
```

---

### 7. `config/default_config.py` - 設定管理

**役割**: デフォルト値・ユーザー設定・プリセット管理

**設定の優先順位**:
```
user_config.json > default_config.py
```

**主要関数**:

```python
load_config() -> dict      # 設定読み込み（user_config.json優先）
save_config(updates) -> bool  # 設定保存
load_presets() -> dict     # プリセット一覧
save_preset(...)           # プリセット保存
```

**設定構造**:
```python
{
    "lm_studio": {
        "host": "localhost",
        "port": 1234,
        "api_token": "...",
        "context_length": 32000,
    },
    "dreaming": {
        "memory_threshold": 30,
    },
    "selected_model": "モデル名",
    "system_prompt": "...",
    "dream_prompt": "...",
    "mcp_integrations": ["mcp/sequential-thinking", "mcp/memory_tools"],
}
```

---

### 8. `ui/app.py` - Gradio UI

**役割**: 全UIコンポーネントとイベントハンドラ

**タブ構成**:

| タブ | 機能 |
|------|------|
| 💬 チャット | メッセージ入出力、気づき表示、フィードバック |
| 📊 ダッシュボード | 統計表示 |
| 🌙 夢見 | 記憶一覧、夢見実行、アーカイブ管理 |
| ⚙️ 設定 | プロンプト / 接続・モデル / データ管理 |

**グローバル状態**:
```python
config = load_config()
engine = AwarenessEngine(config=config, data_dir=data_dir)
```

**重要なイベントフロー**:

1. **チャット送信**: `send_message()` → engine.send_message() → 応答表示
2. **夢見実行**: `trigger_dream_with_selection()` → engine.trigger_dream()
3. **設定保存**: `save_settings()` → save_config() → engine再初期化
4. **モデル変更**: `model_dropdown.change()` → スライダー最大値更新

---

## MCP統合

Metacogは LM Studio の MCP (Model Context Protocol) を活用しています。

**使用するMCPツール**:

| ツール | 用途 |
|--------|------|
| `mcp/sequential-thinking` | 多段階推論（思考の可視化） |
| `mcp/memory_tools` | 記憶の検索・保存（LLMが自律的に使用） |

**設定方法（LM Studio側）**:
1. LM Studio > MCP Servers
2. `sequential-thinking`と`memory_tools`を有効化

**注意**: `mcp.json`のキー名とシステムプロンプト内の名前は一致させる必要がある

---

## データフロー図

### チャット時
```
User Input
    ↓
┌─────────────────────────────────────────────┐
│ AwarenessEngine.send_message()              │
│   ├─ SystemPromptBuilder.build()            │
│   │     └─ config から最新プロンプト取得     │
│   ├─ LMStudioClient.chat()                  │
│   │     ├─ MCP: sequential-thinking         │
│   │     └─ MCP: memory_tools (search/save)  │
│   ├─ ResponseParser.parse()                 │
│   │     ├─ insights 抽出                    │
│   │     └─ saves 抽出                       │
│   └─ UnifiedMemory.save_*()                 │
└─────────────────────────────────────────────┘
    ↓
Response + Metadata (thoughts, insights, saves)
```

### 夢見時
```
┌─────────────────────────────────────────────┐
│ DreamingEngine.dream()                      │
│   ├─ memory.export_for_dreaming()           │
│   │     ├─ ChromaDB memories                │
│   │     └─ feedback.jsonl                   │
│   ├─ dream_prompt に変数注入                │
│   ├─ LMStudioClient.chat()                  │
│   │     └─ MCP: sequential-thinking         │
│   ├─ 洞察抽出・保存                         │
│   ├─ 記憶をアーカイブに移動                 │
│   └─ フィードバッククリア                   │
└─────────────────────────────────────────────┘
```

---

## 拡張ポイント

### 1. SNSエージェント化（metacog-agent）

**必要な変更**:
- `engine/` に `sns_agent.py` 追加
- Moltbook/Twitter API クライアント実装
- 定期実行ループ（5分サイクル）
- 参考: `llm_awareness_emergence_system/engines/moltbook_agent.py`

**統合方法**:
```python
class SNSAgent:
    def __init__(self, engine: AwarenessEngine):
        self.engine = engine  # 既存エンジンを再利用

    def run_cycle(self):
        # 1. フィード取得
        # 2. engine経由でLLM分析
        # 3. 投稿/コメント実行
        # 4. 記憶保存
```

### 2. クラウドAPI化（metacog-cloud）

**必要な変更**:
- `engine/lm_studio.py` を `engine/llm_client.py` に抽象化
- OpenAI / Anthropic / Google クライアント実装
- MCP統合の代替（Function Callingで同等機能）

**インターフェース**:
```python
class LLMClient(Protocol):
    def chat(self, input_text, system_prompt, ...) -> tuple[str, dict]: ...
    def get_available_models(self) -> list[str]: ...
```

### 3. 新しいMCPツール追加

1. LM Studioで新MCPサーバー有効化
2. `config/default_config.py` の `MCP_INTEGRATIONS` に追加
3. 必要に応じてシステムプロンプト修正

---

## トラブルシューティング

### LM Studio接続エラー
- ポート確認（デフォルト: 1234）
- `Enable Authentication` がONの場合、APIトークン必須

### MCP動作しない
- LM StudioでMCPサーバー有効化を確認
- システムプロンプトとmcp.jsonの名前一致を確認

### 夢見が失敗する
- コンテキスト長が十分か確認
- 記憶数が多すぎる場合、閾値調整

---

## 開発Tips

### 設定変更の即時反映
`SystemPromptBuilder.build()`は毎回configを再読み込みするため、
UI設定変更後はエンジン再初期化不要（プロンプトのみ）。

### デバッグ
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### テスト実行
```bash
python metacog.py
# ブラウザで http://127.0.0.1:7860
```

---

## 関連リソース

- **LM Studio MCP API**: https://lmstudio.ai/docs/api
- **Gradio**: https://gradio.app/docs
- **ChromaDB**: https://docs.trychroma.com

---

*このドキュメントは Metacog v1.0 時点の情報です。*
