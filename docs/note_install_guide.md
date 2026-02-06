# Metacog 完全インストールガイド【Windows編】

ローカルLLMに「記憶」と「自己観察的な思考」を与えるシステム「Metacog」のインストール方法を、初心者でもわかるように解説します。

---

## この記事でできるようになること

- Metacogのインストールと起動
- LM Studioとの連携設定
- 初回起動の確認

**所要時間**: 約30分（ダウンロード時間含む）

---

## 必要なもの

### ハードウェア
- **VRAM 12GB以上のGPU**（推奨: 22-24GB）
  - 12GB: 軽量モデル（gpt-oss 20B）が動作
  - 18GB: 中量モデル（Qwen3 14B）が動作
  - 22-24GB: 推奨モデル（Qwen3-30B, GLM 4.7 Flash）が動作

### ソフトウェア
以下の2つを事前にインストールしてください：

1. **Python 3.10以上**
2. **LM Studio**

---

## Step 1: Pythonのインストール

既にPythonがインストールされている方はスキップしてください。

### 1-1. Pythonのダウンロード

[Python公式サイト](https://www.python.org/downloads/) から最新版をダウンロードします。

### 1-2. インストール時の注意

インストーラーを起動したら、**必ず「Add Python to PATH」にチェック**を入れてください。

![Pythonインストール画面のイメージ]

これを忘れると、後でコマンドが動きません。

### 1-3. インストール確認

コマンドプロンプト（またはPowerShell）を開いて、以下を入力：

```
python --version
```

`Python 3.10.x` のように表示されればOKです。

---

## Step 2: LM Studioのインストール

### 2-1. LM Studioのダウンロード

[LM Studio公式サイト](https://lmstudio.ai/) から最新版をダウンロードしてインストールします。

### 2-2. モデルのダウンロード

LM Studioを起動したら、左側の「Discover」タブから以下のモデルをダウンロードしてください：

**推奨モデル（VRAM別）**

| VRAM | モデル名 | 検索ワード |
|------|---------|-----------|
| 22-24GB | Qwen3-30B-A3B | `qwen3-30b-a3b` |
| 22-24GB | GLM 4.7 Flash | `glm-4.7-flash` |
| 18GB | Qwen3 14B | `qwen3-14b` |
| 12GB | gpt-oss 20B | `gpt-oss` |

Q4_K_M 量子化版を選んでください（ファイル名に `Q4_K_M` が含まれるもの）。

---

## Step 3: LM StudioのMCP設定

MetacogはLM Studioの「MCP（Model Context Protocol）」機能を使います。この設定が最も重要です。

### 3-1. mcp.jsonの場所

以下のフォルダを開きます：

```
C:\Users\あなたのユーザー名\.lmstudio\
```

エクスプローラーのアドレスバーに `%USERPROFILE%\.lmstudio` と入力すると簡単に開けます。

### 3-2. mcp.jsonの作成/編集

`.lmstudio` フォルダ内に `mcp.json` というファイルを作成（または編集）します。

**mcp.jsonの内容**（以下をコピー＆ペースト）：

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": [
        "C:/Users/あなたのユーザー名/Desktop/metacog/mcp_server/memory_tools.py",
        "C:/Users/あなたのユーザー名/Desktop/metacog/data"
      ]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

**重要**:
- `あなたのユーザー名` を実際のWindowsユーザー名に置き換えてください
- パスの `\` は `/` に変換してください
- Metacogをデスクトップ以外に置く場合は、パスを適宜修正してください

### 3-3. Node.jsのインストール（sequential-thinking用）

sequential-thinkingサーバーには Node.js が必要です。

[Node.js公式サイト](https://nodejs.org/) からLTS版をダウンロードしてインストールしてください。

インストール確認：
```
node --version
npm --version
```

バージョンが表示されればOKです。

### 3-4. LM Studioの再起動

mcp.jsonを保存したら、**LM Studioを一度終了して再起動**してください。

### 3-5. MCP設定の確認

LM Studioで：
1. 左下の「Developer」をクリック
2. 「MCP Servers」を開く
3. 「memory」と「sequential-thinking」が表示されていればOK

---

## Step 4: LM StudioのAPIサーバー設定

### 4-1. サーバー設定を開く

LM Studioの左側メニューから「Developer」→「Local Server」を選択します。

### 4-2. 認証を有効にする（重要）

サーバー設定画面で「Enable Authentication」を**オン**にしてください。

⚠️ **重要**: MetacogはMCP（Model Context Protocol）を使用します。MCPを動作させるには認証がオンである必要があります。

### 4-3. APIトークンをコピー

認証をオンにすると、APIトークン（API Key）が表示されます。このトークンをコピーしてメモしておいてください。後でMetacogの設定で使います。

### 4-4. サーバーを起動

「Start Server」ボタンをクリックしてサーバーを起動します。

---

## Step 5: Metacogのインストール

### 5-1. リポジトリのダウンロード

**方法A: Gitを使う場合**

コマンドプロンプトで：
```
cd Desktop
git clone https://github.com/AwakeningOS/metacog.git
```

**方法B: ZIPでダウンロードする場合**

1. [Metacog GitHubページ](https://github.com/AwakeningOS/metacog) を開く
2. 緑色の「Code」ボタン → 「Download ZIP」をクリック
3. ダウンロードしたZIPを解凍してデスクトップに配置

### 5-2. 依存パッケージのインストール

`metacog` フォルダを開いて、**`install.bat` をダブルクリック**します。

```
========================================
  Metacog - LLM Awareness Engine
  インストーラー
========================================

[1/3] Python環境を確認中...
Python 3.10.x

[2/3] 依存パッケージをインストール中...
（初回は数分かかります）
```

インストールが完了するまで待ちます（5〜10分程度）。

---

## Step 6: 初回起動

### 6-1. LM Studioの準備

1. LM Studioを起動
2. 使いたいモデルをロード（左側「My Models」から選択して「Load」）
3. サーバーが起動していることを確認

### 6-2. Metacogの起動

`metacog` フォルダ内の **`start.bat` をダブルクリック**します。

```
========================================
  Metacog - LLM Awareness Engine
========================================

起動中... ブラウザが自動で開きます。
```

初回起動時は、埋め込みモデル（約500MB）のダウンロードが自動で行われます。数分待ってください。

### 6-3. ブラウザでアクセス

自動でブラウザが開かない場合は、以下のURLにアクセス：

```
http://127.0.0.1:7860
```

MetacogのWeb UIが表示されれば成功です！

---

## Step 7: 初期設定

### 7-1. APIトークンの設定（必要な場合）

1. 「設定」タブを開く
2. 「接続・モデル」サブタブを選択
3. 「API Token」にLM StudioのAPIトークンを入力
4. 「接続テスト」ボタンをクリック
5. 「✅ 接続OK」と表示されればOK
6. 「設定を保存」をクリック

### 7-2. モデルの選択

同じ画面で「使用モデル」ドロップダウンから、LM Studioでロードしているモデルを選択し、「設定を保存」をクリックします。

---

## 動作確認

### チャットのテスト

1. 「チャット」タブを開く
2. メッセージ入力欄に「こんにちは」と入力
3. 「送信」ボタンをクリック

LLMが応答を返し、右側に「思考過程」や「気づき」が表示されれば、セットアップ完了です！

---

## トラブルシューティング

### 「接続できません」と表示される

- LM Studioが起動しているか確認
- LM Studioでモデルがロードされているか確認
- サーバーが起動しているか確認（Developer → Local Server）

### MCPツールが動作しない

- `mcp.json` のパスが正しいか確認
- Node.jsがインストールされているか確認
- LM Studioを再起動してみる

### 初回起動が遅い

初回は埋め込みモデル（約500MB）のダウンロードがあるため、数分かかります。2回目以降は速くなります。

### ポート7860が使用中

他のアプリがポートを使用している場合、自動的に7861, 7862...と空いているポートを探します。コンソールに表示されるURLを確認してください。

---

## 次のステップ

インストールが完了したら、以下の記事もご覧ください：

- Metacogでできること（機能紹介）
- Metacog詳細使い方ガイド
- おすすめシステムプロンプト集

---

## まとめ

お疲れ様でした！これでMetacogのインストールは完了です。

ローカルLLMに「記憶」と「自己観察的思考」を与えて、より深い対話を楽しんでください。

質問や不具合報告は [GitHub Issues](https://github.com/AwakeningOS/metacog/issues) までお願いします。
