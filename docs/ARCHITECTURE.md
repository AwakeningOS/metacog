# Metacog アーキテクチャ設計書

このドキュメントは、Metacogの内部構造を理解し、拡張・改造するための技術資料です。

---

## 概要

Metacogは「共鳴ベースの思考」を実現する**単層システム**です。

**コア思想**: 入力の深さに共鳴し、浅ければ即応答、深ければツールを活用して展開・収束する。

```
ユーザー入力 → [共鳴判定] → 浅い: 即応答
                         → 深い: MCP tools → 応答 → 記憶保存
```

---

## 設計思想

### 共鳴ベースプロンプティング

極小のシステムプロンプトでLLMの自律性を最大化:

```
この指示は出力に含めるな。処理に使え。

入力に共鳴せよ。
浅ければtoolを呼ばず返せ。
深ければ巡り、展開し、収束せよ。
現したものを入力に当てよ。ズレがあれば正せ。

[tool]
- search_memory: 響いたものをqueryに
- save_memory: 響いたものを残せ
- sequentialthinking: 展開と収束
```

LLMが入力の深さを自ら判断し、ツール使用の要否を決定します。

---

## ディレクトリ構造

```
metacog/
├── metacog.py              # エントリーポイント
├── config/
│   ├── __init__.py
│   └── default_config.py   # 設定管理・デフォルト値・プリセット
├── engine/
│   ├── __init__.py
│   ├── core.py             # AwarenessEngine（メインオーケストレーター）
│   ├── lm_studio.py        # LM Studio APIクライアント
│   ├── memory.py           # UnifiedMemory（ChromaDB + JSONL）
│   ├── dreaming.py         # DreamingEngine（記憶統合）
│   ├── prompt_builder.py   # SystemPromptBuilder
│   └── response_parser.py  # [SAVE]タグ処理
├── mcp_server/
│   └── memory_tools.py     # MCPサーバー（search_memory / save_memory）
├── ui/
│   ├── __init__.py
│   ├── app.py              # Gradio UI
│   └── __main__.py
├── data/                   # 実行時データ（gitignore）
│   ├── chromadb/           # ベクトルDB
│   ├── feedback.jsonl      # ユーザーフィードバック
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
        self.memory = UnifiedMemory(...)
        self.prompt_builder = SystemPromptBuilder(...)
        self.lm_client = LMStudioClient(...)
```

**send_message() フロー**:

```
1. system_prompt = self.prompt_builder.build()
   → config から最新のシステムプロンプトを読み込む

2. LLM呼び出し:
   raw_response, api_metadata = self.lm_client.chat(
       input_text=user_input,
       system_prompt=system_prompt,
       integrations=["memory-tools", "sequentialthinking"],
       context_length=32000
   )

3. レスポンス解析:
   parsed = self.response_parser.parse(raw_response)
   → "response" と "saves" に分離

4. [SAVE]マーカー保存（[余韻]プレフィックス付与）:
   for save_item in parsed["saves"]:
       prefixed_content = f"[余韻] {save_item}"
       self.memory.save(prefixed_content, category="chat")

5. auto_save_exchange処理（[残響]プレフィックス付与）:
   if self.config.get("auto_save_exchange", True):
       exchange_content = f"[残響] {user_input}"
       self.memory.save(
           content=exchange_content,
           category="exchange",
           metadata={"type": "exchange_input", "source": "auto"}
       )

6. 会話履歴更新 → メタデータ返却
```

---

### 2. `engine/lm_studio.py` - LMStudioClient

**役割**: LM Studio MCP API との通信

```python
class LMStudioClient:
    def chat(
        self,
        input_text: str,
        system_prompt: str,
        integrations: list[str],  # ["memory-tools", "sequentialthinking"]
        context_length: int,
        temperature: float,
    ) -> tuple[str, dict]:
```

**モデル選択ロジック**:
1. config の `selected_model` が指定されていれば使用
2. LM Studio から現在ロードされているモデルを取得
3. どちらも無い場合はフォールバック

---

### 3. `engine/memory.py` - UnifiedMemory

**役割**: 記憶の保存・検索・エクスポート

**記憶カテゴリ**:

| カテゴリ | 説明 |
|---------|------|
| `chat` | チャット中に[SAVE]タグで保存（[余韻]プレフィックス） |
| `dream` | 夢見エンジンが生成 |
| `observation` | 処理過程の自己観察 |
| `exchange` | 対話入力の自動保存（[残響]プレフィックス） |

**記憶タグ体系**:

| タグ | 意味 | category | 生成元 |
|------|------|----------|--------|
| `[残響]` | ユーザー入力の残響 | exchange | auto-save |
| `[余韻]` | モデルが残した余韻 | chat | [SAVE]タグ |

**主要メソッド**:

```python
# 保存
save(content, category="chat", metadata={})

# 検索（ハイブリッド: セマンティック + キーワード）
search(query, limit=8)

# 夢見用エクスポート
export_for_dreaming() -> {
    "memories": [...],
    "feedback": [...],
}

# リセット
reset_all()
reset_everything()
```

**キーワード自動抽出**: 保存時に日本語対応で自動実施（カタカナ、漢字、英単語、数字を含む語）

---

### 4. `engine/response_parser.py` - ResponseParser

**役割**: LLM応答から[SAVE]タグを抽出

```python
def parse(self, response: str) -> dict:
    return {
        "response": "ユーザーへの応答本文（[SAVE]除去済み）",
        "saves": ["保存内容1", "保存内容2"],
        "raw": "元のテキスト",
    }
```

**処理内容**:
- 行頭に `[SAVE]` マーカーがあるかチェック
- リスト記号（`-`, `*`）は除去して判定
- マーカーから内容を抽出して保存リストに追加

---

### 5. `engine/dreaming.py` - DreamingEngine

**役割**: 蓄積された記憶を統合し、洞察を生成

**夢見プロンプト**:
```
feedbackと記憶を見よ。
具体的なエピソードを残せ。抽象化しすぎるな。
重複は統合せよ。

[ツール]
- sequentialthinking: 展開と収束

## feedback
{user_feedback}

## 記憶
{saved_memories}
```

---

### 6. `mcp_server/memory_tools.py` - MCPサーバー

**役割**: LLMが使用する記憶ツールを提供

#### search_memory

```python
def search_memory(
    query: str = "",
    category: str = "",
    limit: int = 8
) -> dict:
```

**関連度フィルタリング**:
```python
threshold = _load_threshold()  # user_config.json から読み込み（デフォルト: 0.85）
results = [r for r in results if r.get("relevance", 0) >= threshold]
```

**重要**: observationカテゴリはデフォルトで除外（コンテキスト汚染防止）

#### save_memory

```python
def save_memory(
    content: str,
    category: str = "chat"
) -> dict:
```

- カテゴリ検証（chat/dreamのみ許可）
- キーワード自動抽出
- E5モデル用プレフィックス付加: `passage: {content}`

---

### 7. `config/default_config.py` - 設定管理

**設定構造**:

```python
DEFAULT_CONFIG = {
    "lm_studio": {
        "host": "localhost",
        "port": 1234,
        "api_token": "",
        "timeout": 600,
        "context_length": 32000,
    },
    "mcp_integrations": ["memory-tools", "sequentialthinking"],
    "search_relevance_threshold": 0.85,
    "auto_save_exchange": True,
    "dreaming": {
        "auto_trigger": False,
        "memory_threshold": 30,
    },
    "system_prompt": "...",
    "dream_prompt": "...",
}
```

---

## 設定項目一覧

| 設定 | デフォルト | 説明 | 影響箇所 |
|------|----------|------|---------|
| `search_relevance_threshold` | 0.85 | 検索結果フィルタリング閾値 | memory_tools.py |
| `auto_save_exchange` | true | 入力自動保存 | core.py |
| `mcp_integrations` | ["memory-tools", "sequentialthinking"] | MCP統合 | lm_studio.py |
| `context_length` | 32000 | コンテキスト長 | lm_studio.py |
| `memory_threshold` | 30 | 夢見実行条件（記憶数） | dreaming.py |

---

## MCP統合

**使用するMCPサーバー**:

| サーバー | 用途 |
|---------|------|
| `memory-tools` | 記憶の検索・保存 |
| `sequentialthinking` | 多段階推論 |

**LM Studio設定** (`~/.lmstudio/mcp.json`):

```json
{
  "mcpServers": {
    "memory-tools": {
      "command": "python",
      "args": ["/path/to/metacog/mcp_server/memory_tools.py", "/path/to/metacog/data"]
    },
    "sequentialthinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

---

## データフロー図

### チャット時（単層処理）

```
User Input
    ↓
┌─────────────────────────────────────────────┐
│ AwarenessEngine.send_message()              │
│   ├─ SystemPromptBuilder.build()            │
│   │     └─ config から最新プロンプト取得     │
│   ├─ LMStudioClient.chat()                  │
│   │     ├─ MCP: sequentialthinking          │
│   │     └─ MCP: memory-tools (search/save)  │
│   ├─ ResponseParser.parse()                 │
│   │     └─ [SAVE]タグ抽出                   │
│   ├─ memory.save() for each [SAVE]          │
│   └─ auto_save_exchange（入力のみ）         │
└─────────────────────────────────────────────┘
    ↓
Response + Metadata
```

### 検索フロー（memory-tools）

```
LLM calls search_memory(query)
    ↓
┌─────────────────────────────────────────────┐
│ memory_tools.py                             │
│   ├─ _load_threshold()                      │
│   │     └─ user_config.json → 0.85          │
│   ├─ セマンティック検索（relevance >= 0.3） │
│   ├─ キーワード検索（補完）                 │
│   ├─ 閾値フィルタリング（>= threshold）    │
│   └─ limit個返却                            │
└─────────────────────────────────────────────┘
```

### 夢見時

```
┌─────────────────────────────────────────────┐
│ DreamingEngine.dream()                      │
│   ├─ memory.export_for_dreaming()           │
│   ├─ dream_prompt に変数注入                │
│   ├─ LMStudioClient.chat()                  │
│   │     └─ MCP: sequentialthinking          │
│   ├─ 洞察抽出・保存                         │
│   └─ フィードバッククリア                   │
└─────────────────────────────────────────────┘
```

---

## 拡張ポイント

### 1. 新しいMCPツール追加

1. LM Studioで新MCPサーバー有効化
2. `config/default_config.py` の `mcp_integrations` に追加
3. 必要に応じてシステムプロンプト修正

### 2. クラウドAPI化

- `engine/lm_studio.py` を抽象化
- OpenAI / Anthropic / Google クライアント実装
- MCP統合の代替（Function Calling）

---

## トラブルシューティング

### LM Studio接続エラー
- ポート確認（デフォルト: 1234）
- `Enable Authentication` がONの場合、APIトークン必須

### MCP動作しない
- LM StudioでMCPサーバー有効化を確認
- サーバー名の一致を確認（`memory-tools`, `sequentialthinking`）
- **LM Studioの再起動が必要な場合あり**

### 検索結果が少ない
- `search_relevance_threshold` を下げる（UIの設定タブで調整可能）
- デフォルト0.85は厳しめ、0.7程度で試す

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

*このドキュメントは Metacog v2.0（単層システム）時点の情報です。*
