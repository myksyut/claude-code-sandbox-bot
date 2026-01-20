# E2Eテスト共通フィクスチャ - Design Doc: claude-code-sandbox-bot-design.md
# 生成日時: 2026-01-20 | テスト種別: E2E/Integration
"""
E2Eテスト用の共有フィクスチャと設定。

このファイルはE2Eテストで使用される共通のフィクスチャを定義します。
外部サービス（Slack、Redis、ACI）のモックも含みます。
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# 環境設定フィクスチャ
# =============================================================================


@pytest.fixture
def test_config() -> dict[str, str]:
    """テスト用の環境設定を提供。

    Returns:
        テスト用の設定値を含む辞書
    """
    return {
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "SLACK_APP_TOKEN": "xapp-test-token",
        "REDIS_URL": "redis://localhost:6379",
        "MAX_CONCURRENT_TASKS": "3",
        "GITHUB_PAT": "ghp_test_token",
        "AZURE_SUBSCRIPTION_ID": "test-subscription-id",
        "AZURE_RESOURCE_GROUP": "test-resource-group",
    }


# =============================================================================
# Slackモックフィクスチャ
# =============================================================================


@pytest.fixture
def mock_slack_client() -> MagicMock:
    """Slack APIクライアントのモックを提供。

    Returns:
        spec付きのMagicMock（SlackBotプロトコル準拠）
    """
    # TODO: 実装時にSlackBotプロトコルのspecを追加
    mock = MagicMock()
    mock.send_message = AsyncMock(return_value="1234567890.123456")
    mock.update_message = AsyncMock()
    mock.upload_file = AsyncMock()
    return mock


@pytest.fixture
def sample_slack_event() -> dict:
    """サンプルのSlackイベントペイロードを提供。

    Returns:
        Slackメンションイベントの辞書
    """
    return {
        "type": "app_mention",
        "user": "U12345678",
        "text": "<@U_BOT> https://github.com/owner/repo このリポジトリを調査して",
        "channel": "C12345678",
        "ts": "1234567890.123456",
        "event_ts": "1234567890.123456",
    }


@pytest.fixture
def sample_slack_command() -> dict:
    """サンプルのSlackスラッシュコマンドペイロードを提供。

    Returns:
        /claudeコマンドの辞書
    """
    return {
        "command": "/claude",
        "text": "https://github.com/owner/repo このリポジトリを調査して",
        "user_id": "U12345678",
        "channel_id": "C12345678",
        "response_url": "https://hooks.slack.com/commands/xxx",
    }


# =============================================================================
# Redisモックフィクスチャ
# =============================================================================


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Redisクライアントのモックを提供。

    Returns:
        spec付きのMagicMock（RedisClientプロトコル準拠）
    """
    # TODO: 実装時にRedisClientプロトコルのspecを追加
    mock = MagicMock()
    mock.publish = AsyncMock()
    mock.subscribe = AsyncMock()
    mock.set = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    return mock


# =============================================================================
# ACIモックフィクスチャ
# =============================================================================


@pytest.fixture
def mock_sandbox_manager() -> MagicMock:
    """SandboxManagerのモックを提供。

    Returns:
        spec付きのMagicMock（SandboxManagerプロトコル準拠）
    """
    # TODO: 実装時にSandboxManagerプロトコルのspecを追加
    mock = MagicMock()
    mock.create = AsyncMock()
    mock.destroy = AsyncMock()
    mock.get_status = AsyncMock()
    return mock


# =============================================================================
# タスク関連フィクスチャ
# =============================================================================


@pytest.fixture
def sample_task_id() -> str:
    """サンプルのタスクIDを提供。

    Returns:
        UUID v4形式の文字列
    """
    return "12345678-1234-4123-8123-123456789012"


@pytest.fixture
def sample_task() -> dict:
    """サンプルのタスクデータを提供。

    Returns:
        Task型に準拠した辞書
    """
    return {
        "id": "12345678-1234-4123-8123-123456789012",
        "channel_id": "C12345678",
        "thread_ts": "1234567890.123456",
        "user_id": "U12345678",
        "prompt": "このリポジトリを調査して",
        "repository_url": "https://github.com/owner/repo",
        "status": "pending",
        "created_at": 1234567890.0,
        "idempotency_key": "key-12345678",
    }


# =============================================================================
# Human-in-the-loop フィクスチャ
# =============================================================================


@pytest.fixture
def sample_human_question() -> dict:
    """サンプルのユーザー質問データを提供。

    Returns:
        HumanQuestion型に準拠した辞書
    """
    return {
        "task_id": "12345678-1234-4123-8123-123456789012",
        "question": "このファイルを変更してもよいですか？",
        "options": ["はい", "いいえ"],
        "timeout_seconds": 600,
    }


# =============================================================================
# 非同期コンテキストフィクスチャ
# =============================================================================


@pytest.fixture
async def async_context() -> AsyncGenerator[None, None]:
    """非同期テスト用のコンテキストを提供。

    Yields:
        None（セットアップ/クリーンアップ用）
    """
    # セットアップ
    yield
    # クリーンアップ
