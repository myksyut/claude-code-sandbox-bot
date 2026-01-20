# クイックスタートガイド

このガイドでは、AI Coding Project Boilerplate（Python版）のセットアップと基本的な使い方を説明します。

## 前提条件

- Python 3.12以上
- [uv](https://github.com/astral-sh/uv) パッケージマネージャー
- [Claude Code](https://claude.ai/code) CLI

## セットアップ手順

### 1. リポジトリをクローン

```bash
git clone <repository-url> my-project
cd my-project
```

### 2. 依存関係のインストール

```bash
uv sync --dev
```

### 3. pre-commitフックのセットアップ

```bash
uv run pre-commit install
```

### 4. 動作確認

```bash
# アプリケーション実行
uv run python src/main.py

# テスト実行
uv run pytest

# リントチェック
uv run ruff check src
```

## Claude Codeでの開発

### 初回セットアップ

1. Claude Codeを起動
   ```bash
   claude
   ```

2. プロジェクトコンテキストを設定
   ```
   /project-inject
   ```

### 機能開発の流れ

1. 機能の実装
   ```
   /implement ユーザー認証機能を追加
   ```

2. 設計のみ作成（大規模機能の場合）
   ```
   /design REST APIエンドポイントの設計
   ```

3. コードレビュー
   ```
   /review
   ```

## 次のステップ

- [ユースケース＆コマンド](use-cases.md) - 日常ワークフローのリファレンス
- [ルール編集ガイド](rule-editing-guide.md) - プロジェクトに合わせてカスタマイズ
