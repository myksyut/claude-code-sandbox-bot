# ルール編集ガイド

このガイドでは、ボイラープレートのルールをプロジェクトに合わせてカスタマイズする方法を説明します。

## スキルの編集

スキルは`.claude/skills/`ディレクトリに配置されています。

### スキルの構造

```
.claude/skills/
├── coding-standards/
│   └── SKILL.md
├── python-rules/
│   └── SKILL.md
├── python-testing/
│   └── SKILL.md
├── technical-spec/
│   └── SKILL.md
├── project-context/
│   └── SKILL.md          # プロジェクト固有設定
└── frontend/
    ├── python-rules/
    │   └── SKILL.md
    └── python-testing/
        └── SKILL.md
```

### SKILL.mdの形式

```markdown
---
name: skill-name
description: スキルの説明
---

# スキルのタイトル

## セクション1

ルールの内容...

## セクション2

ルールの内容...
```

## プロジェクト固有設定

`/project-inject`コマンドを実行すると、対話形式でプロジェクト情報を設定できます。

設定は`.claude/skills/project-context/SKILL.md`に保存されます。

### 手動編集

直接編集することも可能です：

```markdown
---
name: project-context
description: プロジェクト固有の設定
---

# プロジェクトコンテキスト

## 基本設定

- プロジェクト名: My Project
- 技術スタック: FastAPI, PostgreSQL, Redis

## 実装原則

- すべてのAPIエンドポイントにはPydanticスキーマを使用
- データベースアクセスはリポジトリパターンで実装
```

## エージェントの編集

エージェントは`.claude/agents/`ディレクトリに配置されています。

### エージェントの構造

```markdown
---
name: agent-name
description: エージェントの説明
---

# エージェント名

## 役割

エージェントの役割を説明...

## 実行手順

1. ステップ1
2. ステップ2
3. ステップ3

## 使用するスキル

- coding-standards
- python-rules
```

## コマンドの編集

コマンドは`.claude/commands/`ディレクトリに配置されています。

### コマンドの構造

```markdown
---
name: command-name
description: コマンドの説明
---

# コマンド名

このコマンドの目的と使い方...

## 実行フロー

1. ステップ1
2. ステップ2

## 使用するエージェント

- requirement-analyzer
- technical-designer
```

## ベストプラクティス

1. **段階的に変更**: 大きな変更は避け、少しずつ調整
2. **テスト**: 変更後は実際のタスクで動作確認
3. **バックアップ**: 重要な変更前はバックアップを取る
4. **ドキュメント**: 変更理由をコメントで残す
