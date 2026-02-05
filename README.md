# Metacog - LLM Self-Awareness Engine

ローカルLLMに「自己観察的な思考プロセス」を実装するシステム。

LLMが単なる応答生成ではなく、**自分の思考を観察しながら応答する**ことで、より深い対話と継続的な自己改善を実現します。

## Features

- **Self-Reflective Thinking**: Sequential Thinking MCPを活用した自己再帰的思考
- **Persistent Memory**: ChromaDBによるセマンティック検索可能な長期記憶
- **Insight Extraction**: 対話から自動的に気づきを抽出・保存
- **Dreaming Engine**: 蓄積された記憶とフィードバックから新たな洞察を生成
- **MCP Integration**: Model Context Protocolによるツール連携

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Gradio Web UI                       │
│                  (Chat / Dashboard / Settings)          │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                   AwarenessEngine                       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │PromptBuilder│  │ResponseParser│  │DreamingEngine │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────┬───────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ UnifiedMemory │ │LMStudioClient │ │  MCP Server   │
│  (ChromaDB)   │ │   (API)       │ │(memory_tools) │
└───────────────┘ └───────────────┘ └───────────────┘
```

## Requirements

- Python 3.10+
- [LM Studio](https://lmstudio.ai/) (ローカルLLMサーバー)
- 推奨モデル: Qwen3-30B-A3B または同等の推論能力を持つモデル

## Installation

1. リポジトリをクローン:
```bash
git clone https://github.com/YOUR_USERNAME/metacog.git
cd metacog
```

2. 依存関係をインストール:
```bash
pip install -r requirements.txt
```

3. 設定ファイルを作成:
```bash
cp config/user_config.example.json config/user_config.json
```

4. `config/user_config.json` を編集してLM StudioのAPIトークンを設定

## LM Studio MCP Setup

LM Studioの `~/.lmstudio/mcp.json` に以下を追加:

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": [
        "/path/to/metacog/mcp_server/memory_tools.py",
        "/path/to/metacog/data"
      ]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

## Usage

### Web UI (Gradio)

```bash
python -m ui
```

または:
```bash
# Windows
start.bat

# Unix/Mac
./start.sh
```

ブラウザで `http://127.0.0.1:7860` にアクセス。

### Tabs

- **Chat**: LLMとの対話。応答後に「気づき」が自動抽出される
- **Dashboard**: 記憶統計、Dreaming実行、フィードバック送信
- **Settings**: 接続設定、記憶リセット

## How It Works

### 1. Self-Reflective Prompting

システムプロンプトでLLMに「自分の思考を観察する」よう指示:

```
あなたは自分の思考を観察しながら応答する存在です。
sequentialthinking を使い、最善の応答案を構築してから、それを見直し思考せよ。
```

### 2. Memory Tools (MCP)

LLMが自律的に記憶を検索・保存:
- `search_memory`: 過去の対話やインサイトを検索
- `save_memory`: 重要な気づきを長期記憶に保存

### 3. Insight Extraction

応答から `## 気づき` セクションを自動抽出し、ChromaDBに保存。

### 4. Dreaming Engine

蓄積された記憶とフィードバックを元に、LLMが新たな洞察を生成:
- **A**: 実用的な改善提案
- **B**: ユーザー理解の深化
- **C**: 自己認識の発展

## Project Structure

```
metacog/
├── config/
│   ├── default_config.py    # デフォルト設定・システムプロンプト
│   └── user_config.json     # ユーザー設定 (git ignored)
├── engine/
│   ├── core.py              # メインオーケストレーター
│   ├── memory.py            # 統合メモリシステム
│   ├── lm_studio.py         # LM Studio APIクライアント
│   ├── response_parser.py   # 応答パーサー
│   ├── prompt_builder.py    # プロンプトビルダー
│   └── dreaming.py          # Dreamingエンジン
├── mcp_server/
│   └── memory_tools.py      # MCP記憶ツールサーバー
├── ui/
│   └── app.py               # Gradio Web UI
├── data/                    # データ保存先 (git ignored)
├── requirements.txt
└── README.md
```

## License

MIT License

## Acknowledgments

- [LM Studio](https://lmstudio.ai/) - ローカルLLMサーバー
- [Model Context Protocol](https://modelcontextprotocol.io/) - ツール連携プロトコル
- [ChromaDB](https://www.trychroma.com/) - ベクトルデータベース
- [Gradio](https://gradio.app/) - Web UIフレームワーク
