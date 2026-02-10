# Metacog - LLM Self-Awareness Engine

ローカルLLMに「共鳴ベースの思考プロセス」を実装するシステム。

LLMが入力の深さに**共鳴**し、浅ければ即座に応答、深ければツールを活用して展開・収束することで、自然な対話を実現します。

---

## 📘 インストールガイド

**初めての方はこちらをお読みください！**

👉 **[Metacog 完全インストールガイド【MacもOK】](https://note.com/jazzy_dill8804/n/nfa61dd378721)**

画像付きで丁寧に解説しています。

---

## Features

- **共鳴ベース処理**: 入力の深さに応じた動的な応答（浅い→即応答、深い→ツール活用）
- **単層システム**: シンプルで軽量な処理フロー
- **Persistent Memory**: ChromaDBによるセマンティック検索 + 関連度フィルタリング（閾値0.85）
- **自動入力保存**: 対話入力を自動でexchangeカテゴリに保存
- **Dreaming Engine**: 蓄積された記憶とフィードバックから新たな洞察を生成
- **MCP Integration**: memory-tools / sequentialthinking によるツール連携

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Gradio Web UI                       │
│                  (Chat / Dashboard / Settings)          │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                   AwarenessEngine                       │
│                                                         │
│  入力 → [共鳴判定] → 浅い: 即応答                       │
│                    → 深い: MCP tools → 応答             │
│                                                         │
│  [SAVE]タグ → memory保存 (category: chat)               │
│  入力 → exchange自動保存                                │
└─────────────────────────┬───────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ UnifiedMemory │ │LMStudioClient │ │  MCP Server   │
│  (ChromaDB)   │ │   (API)       │ │(memory-tools) │
│               │ │               │ │(sequential    │
│ 閾値: 0.85    │ │               │ │ thinking)     │
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
    "memory-tools": {
      "command": "python",
      "args": [
        "/path/to/metacog/mcp_server/memory_tools.py",
        "/path/to/metacog/data"
      ]
    },
    "sequentialthinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

**注意**: MCPサーバー名は `memory-tools` と `sequentialthinking` です。

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

- **Chat**: LLMとの対話。[SAVE]タグで記憶保存、入力は自動保存
- **Dashboard**: 記憶統計、Dreaming実行、フィードバック送信
- **Settings**: 接続設定、記憶閾値、記憶リセット

## How It Works

### 1. 共鳴ベースプロンプティング

極小のシステムプロンプトでLLMの自律性を最大化:

```
入力に共鳴せよ。
浅ければtoolを呼ばず返せ。
深ければ巡り、展開し、収束せよ。
```

入力の深さに応じてLLMが自らツール使用を判断します。

### 2. Memory Tools (MCP)

LLMが自律的に記憶を検索・保存:
- `search_memory`: 過去の対話や記憶を検索（関連度0.85以上のみ返却）
- `save_memory`: 重要な内容を長期記憶に保存

### 3. [SAVE]タグによる記憶保存

LLMが応答中に `[SAVE]重要な情報` と記述すると、その内容がChromaDBに保存されます。

### 4. 記憶カテゴリ

| カテゴリ | 説明 |
|---------|------|
| `chat` | チャット中に[SAVE]タグで保存 |
| `dream` | 夢見エンジンが生成 |
| `observation` | 処理過程の自己観察 |
| `exchange` | 対話入力の自動保存 |

### 5. 関連度フィルタリング

検索結果は `search_relevance_threshold`（デフォルト0.85）以上のもののみ返されます。
低関連度の記憶を除外し、コンテキストの品質を向上。

### 6. Dreaming Engine

蓄積された記憶とフィードバックを元に、LLMが新たな洞察を生成。
具体的なエピソードを残し、過度な抽象化を避ける設計。

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

## Uninstall（アンインストール）

Metacogはレジストリやシステムファイルを一切変更しません。完全に削除するには：

### 1. Metacogフォルダを削除

```
metacog/ フォルダをそのまま削除するだけでOK
```

### 2. （任意）埋め込みモデルのキャッシュを削除

初回起動時にダウンロードされた埋め込みモデルを削除する場合：

```
# Windows
%USERPROFILE%\.cache\huggingface\hub\models--intfloat--multilingual-e5-small

# Mac/Linux
~/.cache/huggingface/hub/models--intfloat--multilingual-e5-small
```

---

**注意**: LM Studio、Python、MCPサーバー（sequential-thinking等）は別途インストールしたものなので、Metacog削除では消えません。それらも不要な場合は個別にアンインストールしてください。

## License

MIT License

## Acknowledgments

- [LM Studio](https://lmstudio.ai/) - ローカルLLMサーバー
- [Model Context Protocol](https://modelcontextprotocol.io/) - ツール連携プロトコル
- [ChromaDB](https://www.trychroma.com/) - ベクトルデータベース
- [Gradio](https://gradio.app/) - Web UIフレームワーク
