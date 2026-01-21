"""ProgressNotifier機能の単体テスト。

テスト対象:
- 進捗通知(notify)機能
- Redis pub/sub購読(start_listening)機能
- ステータス表示フォーマット(起動中/クローン中/実行中/完了)
- メッセージ編集によるSlack進捗更新
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.redis.client import RedisClient
from src.slack.app import SlackBot
from src.task.models import TaskStatus
from src.task.progress import ProgressNotifierImpl, format_progress_message


class TestFormatProgressMessage:
    """進捗メッセージフォーマットのテスト。"""

    def test_format_starting_status(self) -> None:
        """STARTING状態は「起動中...」と表示される。"""
        result = format_progress_message(TaskStatus.STARTING, step=1, total=4)
        assert result == "起動中... (1/4)"

    def test_format_cloning_status(self) -> None:
        """CLONING状態は「クローン中...」と表示される。"""
        result = format_progress_message(TaskStatus.CLONING, step=2, total=4)
        assert result == "クローン中... (2/4)"

    def test_format_running_status(self) -> None:
        """RUNNING状態は「実行中...」と表示される。"""
        result = format_progress_message(TaskStatus.RUNNING, step=3, total=4)
        assert result == "実行中... (3/4)"

    def test_format_completed_status(self) -> None:
        """COMPLETED状態は「完了」と表示される。"""
        result = format_progress_message(TaskStatus.COMPLETED, step=4, total=4)
        assert result == "完了 (4/4)"

    def test_format_failed_status(self) -> None:
        """FAILED状態は「エラー」と表示される。"""
        result = format_progress_message(TaskStatus.FAILED, step=3, total=4)
        assert result == "エラー (3/4)"

    def test_format_waiting_user_status(self) -> None:
        """WAITING_USER状態は「ユーザー回答待ち...」と表示される。"""
        result = format_progress_message(TaskStatus.WAITING_USER, step=3, total=4)
        assert result == "ユーザー回答待ち... (3/4)"


@pytest.fixture
def mock_redis() -> MagicMock:
    """RedisClientのモックを生成する。"""
    redis = MagicMock(spec=RedisClient)
    redis.subscribe = AsyncMock()
    redis.publish = AsyncMock()
    return redis


@pytest.fixture
def mock_slack() -> MagicMock:
    """SlackBotのモックを生成する。"""
    slack = MagicMock(spec=SlackBot)
    slack.update_message = AsyncMock()
    return slack


class TestProgressNotifierNotify:
    """notify機能のテスト。"""

    @pytest.mark.asyncio
    async def test_notify_publishes_to_redis(
        self,
        mock_redis: MagicMock,
        mock_slack: MagicMock,
    ) -> None:
        """notifyはRedis pub/subにメッセージを送信する。"""
        notifier = ProgressNotifierImpl(
            redis=mock_redis,
            slack=mock_slack,
        )

        await notifier.notify(
            task_id="task-123",
            status=TaskStatus.RUNNING,
            step=3,
            total=4,
        )

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "progress:task-123"
        payload = json.loads(call_args[0][1])
        assert payload["status"] == "running"
        assert payload["step"] == 3
        assert payload["total"] == 4


class TestProgressNotifierStartListening:
    """start_listening機能のテスト。"""

    @pytest.mark.asyncio
    async def test_start_listening_subscribes_to_channel(
        self,
        mock_redis: MagicMock,
        mock_slack: MagicMock,
    ) -> None:
        """start_listeningはRedis pub/subチャンネルを購読する。"""
        notifier = ProgressNotifierImpl(
            redis=mock_redis,
            slack=mock_slack,
        )

        # start_listeningはsubscribeをブロッキングで呼び出すため、
        # CancelledErrorで終了させる
        async def cancel_after_subscribe(channel: str, callback) -> None:
            await asyncio.sleep(0.01)
            raise asyncio.CancelledError

        mock_redis.subscribe = cancel_after_subscribe

        with pytest.raises(asyncio.CancelledError):
            await notifier.start_listening(
                task_id="task-123",
                channel_id="C12345",
                message_ts="1234567890.123456",
            )

    @pytest.mark.asyncio
    async def test_callback_updates_slack_message(
        self,
        mock_redis: MagicMock,
        mock_slack: MagicMock,
    ) -> None:
        """コールバックはSlackメッセージを更新する。"""
        notifier = ProgressNotifierImpl(
            redis=mock_redis,
            slack=mock_slack,
        )

        # コールバックを直接テスト
        callback = notifier._create_update_callback(
            channel_id="C12345",
            message_ts="1234567890.123456",
        )

        progress_data = json.dumps(
            {
                "status": "running",
                "step": 3,
                "total": 4,
            }
        )

        await callback(progress_data)

        mock_slack.update_message.assert_called_once_with(
            channel="C12345",
            ts="1234567890.123456",
            text="実行中... (3/4)",
        )


class TestProgressNotifierSlackIntegration:
    """SlackBot連携機能のテスト。"""

    @pytest.mark.asyncio
    async def test_register_message_stores_ts(
        self,
        mock_redis: MagicMock,
        mock_slack: MagicMock,
    ) -> None:
        """register_messageはメッセージのtsを保存する。"""
        notifier = ProgressNotifierImpl(
            redis=mock_redis,
            slack=mock_slack,
        )

        notifier.register_message(
            task_id="task-123",
            channel_id="C12345",
            message_ts="1234567890.123456",
        )

        assert notifier._message_registry["task-123"] == {
            "channel_id": "C12345",
            "message_ts": "1234567890.123456",
        }
