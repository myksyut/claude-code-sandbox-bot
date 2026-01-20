# ユースケース＆コマンド

Claude Codeで利用できるスラッシュコマンドの詳細ガイドです。

## バックエンド開発

### /implement - エンドツーエンド開発

要件から実装、テスト、コミットまでを一貫して行います。

```
/implement ユーザー認証APIを追加
```

**処理の流れ**:
1. 要件分析（規模判定）
2. 必要に応じて設計ドキュメント作成
3. 実装
4. テスト作成
5. 品質チェック
6. コミット

### /task - 単一タスク実行

小規模な変更やバグ修正に適しています。

```
/task ログイン時のエラーメッセージを改善
```

### /design - 設計書作成

アーキテクチャの計画時に使用します。

```
/design マイクロサービス間の通信設計
```

### /plan - 作業計画書作成

設計承認後、実装前の計画立案に使用します。

```
/plan docs/design/auth-api.md
```

### /build - 計画から実行

既存の計画書に基づいて実装を行います。

```
/build docs/plans/auth-implementation.md
```

### /review - コードレビュー

実装完了後のコード品質確認に使用します。

```
/review
```

## フロントエンド開発（FastAPI + HTMX/Jinja2）

### /front-design - フロントエンド設計

```
/front-design ダッシュボードUIの設計
```

### /front-plan - フロントエンド計画

```
/front-plan docs/design/dashboard-ui.md
```

### /front-build - フロントエンド実装

```
/front-build docs/plans/dashboard-implementation.md
```

## トラブルシューティング

### /diagnose - 根本原因分析

デバッグやトラブルシューティングに使用します。

```
/diagnose APIレスポンスが遅い原因を調査
```

**処理の流れ**:
1. 問題調査（investigator）
2. 仮説立案
3. 検証（verifier）
4. 解決策導出（solver）

## ドキュメント化

### /reverse-engineer - コードからドキュメント生成

既存システムのドキュメント化に使用します。

```
/reverse-engineer src/auth/
```

**生成されるドキュメント**:
- PRD（製品要件定義書）
- Design Doc（設計書）

## プロジェクト設定

### /project-inject - プロジェクトコンテキスト設定

プロジェクト固有の設定を行います。

```
/project-inject
```

対話形式でプロジェクト情報を入力し、`.claude/skills/project-context/SKILL.md`に保存されます。
