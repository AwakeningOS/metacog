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
- VRAM 12GB以上（推奨: 22-24GB）

## 推奨モデル

実際にテストした結果に基づく推奨モデルリストです（Q4_K_M量子化）。

### 🥇 プレミアム（VRAM 22-24GB）

| モデル | 使用VRAM | 特徴 |
|--------|----------|------|
| **Qwen3-30B-A3B** | 22GB | 安定・高品質・深い思考 |
| **GLM 4.7 Flash** | 23GB | Tool Use特化。エージェント向け設計 |

- MCP（Sequential Thinking, Memory）を正しく使用
- 日本語が自然で流暢
- 哲学的・抽象的な対話も可能

### 🥈 スタンダード（VRAM 16GB）

| モデル | 使用VRAM | 特徴 |
|--------|----------|------|
| **Qwen3 14B** | 16GB | バランス型。内蔵Reasoningあり |

- MCP Sequential Thinking、Memoryを使用可能
- 日本語品質は良好

### 🥉 エントリー（VRAM 12-15GB）

| モデル | 使用VRAM | 特徴 |
|--------|----------|------|
| **gpt-oss 20B** | 15GB | 軽量・高速。記憶と推論も使える。おすすめ |
| **Qwen3 8B** | 12GB | 案外優秀。たまに暴走することあり |

- MCPツール（Sequential Thinking, Memory）を使用可能
- gpt-ossは動作が軽くておすすめ

### ❌ 非推奨モデル

| モデル | 理由 |
|--------|------|
| Phi-4 Reasoning Plus | 無限ループ・フリーズ。内蔵Reasoningが外部MCPと競合 |
| DeepSeek-R1-Distill-Qwen-7B | 日本語・英語・中国語が混在して崩壊。数学/コード特化モデル |
| LFM 1.2B | パラメータ不足。指示理解が困難 |
| Gemma 3 12B | MCPツールを呼び出さない。速度も遅い |
| Mistral 21B | 日本語が弱すぎる |

### AIパートナー用途について

AIパートナー（AI恋人）用途では**記憶機能が必須**です。ユーザーの名前、好み、過去の会話を覚えている必要があります。

- **推奨**: Qwen3-30B-A3B または GLM 4.7 Flash（VRAM 22-24GB）
- **軽量で使うなら**: gpt-oss 20B（VRAM 15GB）も記憶・推論が動作

軽量モデルでも、システムプロンプトのカスタマイズで改善できる可能性があります：

```
[記憶ツール]
- search_memory: 会話の最初に必ず検索。ユーザーの名前・好みを思い出せ
- save_memory: ユーザーの名前、好み、大切な思い出は必ず保存せよ
```

## Installation

### 簡単インストール（推奨）

1. リポジトリをクローン:
```bash
git clone https://github.com/AwakeningOS/metacog.git
cd metacog
```

2. **`install.bat`** をダブルクリック（Windows）
   - 自動で依存関係がインストールされます
   - 初回は数分かかります

3. **`start.bat`** をダブルクリックで起動！

### 手動インストール

```bash
git clone https://github.com/AwakeningOS/metacog.git
cd metacog
pip install -r requirements.txt
python metacog.py
```

### 初回起動時の注意

- **LM Studio** を先に起動してください
- 初回は埋め込みモデル（multilingual-e5-small、約500MB）がダウンロードされます

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
