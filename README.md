# Claude Code Sandbox Bot

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)](https://www.python.org/)
[![Slack](https://img.shields.io/badge/Slack-Bot-4A154B?logo=slack)](https://api.slack.com/bolt)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Slack経由でクラウド上のClaude Codeサンドボックス環境を操作し、GitHubリポジトリのコードベース調査やMCPタスクを実行するBot。

## 概要

SlackチャンネルからボットをメンションするだけでClaude Codeを起動し、リポジトリを調査した結果をSlackに返信します。

```
@claude-bot https://github.com/org/repo このリポジトリの認証フローを調査して
```

## 主な機能

| 機能 | 説明 |
|------|------|
| **Slack Bot** | メンション/コマンドでリクエスト受信 |
| **サンドボックス起動** | リクエストごとにACIコンテナを起動・破棄 |
| **GitHub連携** | 指定リポジトリをクローン |
| **Claude Code実行** | CLI実行で調査・分析 |
| **進捗通知** | Slackスレッドでリアルタイム進捗更新 |
| **Human-in-the-loop** | Claude Codeからの質問をSlackに転送 |
| **結果返却** | 短文は直接投稿、長文はファイル添付 |

## アーキテクチャ

```
┌─────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Slack  │◄───►│  Slack Bot       │◄───►│  Azure Cache    │
│         │     │  (Container Apps)│     │  for Redis      │
└─────────┘     └──────────────────┘     └────────┬────────┘
                         │                        │
                         ▼                        ▼
                ┌──────────────────┐     ┌─────────────────┐
                │  Azure Container │◄───►│  Claude Code    │
                │  Instances       │     │  CLI            │
                └──────────────────┘     └─────────────────┘
                         │
                         ▼
                ┌──────────────────┐
                │  GitHub          │
                │  (clone)         │
                └──────────────────┘
```

## クイックスタート

### 前提条件

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) パッケージマネージャー
- Slack App (Bot Token + App Token)
- Azure サブスクリプション (ACI, Redis)

### セットアップ

```bash
# 1. リポジトリをクローン
git clone https://github.com/myksyut/claude-code-sandbox-bot.git
cd claude-code-sandbox-bot

# 2. 依存関係インストール
uv sync --dev

# 3. 環境変数を設定
cp .env.example .env
# .envファイルを編集して必要な値を設定
```

### 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `SLACK_BOT_TOKEN` | Yes | `xoxb-`で始まるBot Token |
| `SLACK_APP_TOKEN` | Yes | `xapp-`で始まるApp Token (Socket Mode用) |
| `REDIS_URL` | Yes | Redis接続URL |
| `AZURE_SUBSCRIPTION_ID` | Yes | AzureサブスクリプションID |
| `AZURE_RESOURCE_GROUP` | Yes | Azureリソースグループ名 |
| `MAX_CONCURRENT_TASKS` | No | 同時実行数上限 (デフォルト: 3) |
| `GITHUB_PAT` | No | プライベートリポジトリ用PAT |

### 起動

```bash
uv run python src/main.py
```

## 開発

### コマンド

| コマンド | 説明 |
|---------|------|
| `uv run python src/main.py` | アプリケーション実行 |
| `uv run pytest` | テスト実行 |
| `uv run pytest --cov=src` | カバレッジ測定 |
| `uv run ruff check src` | リントチェック |
| `uv run ruff format src` | フォーマット |

### プロジェクト構成

```
claude-code-sandbox-bot/
├── src/
│   ├── config/        # 設定管理 (pydantic-settings)
│   ├── slack/         # Slack Bot (slack-bolt)
│   ├── task/          # タスク管理 (未実装)
│   ├── sandbox/       # ACI管理 (未実装)
│   ├── redis/         # Redis通信 (未実装)
│   └── main.py        # エントリーポイント
├── tests/
│   ├── unit/          # 単体テスト
│   └── e2e/           # E2Eテスト
├── docs/
│   └── design/        # 設計ドキュメント
└── pyproject.toml
```

## 実装状況

- [x] **Phase 1**: Slack Bot基盤 (メンション受信、起動中応答)
- [ ] **Phase 2**: サンドボックス起動とRedis通信
- [ ] **Phase 3**: Claude Code実行とGitHub連携
- [ ] **Phase 4**: Human-in-the-loop
- [ ] **Phase 5**: 進捗通知と結果返却の改善

## ライセンス

MIT License
