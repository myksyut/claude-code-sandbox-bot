"""
進捗通知モジュール。

Design Doc準拠のインターフェースを実装:
- Protocol型でProgressNotifierインターフェース定義
- Redis pub/subで進捗を受信(channel: progress:{task_id})
- 最初の「起動中...」メッセージを編集して進捗を更新
- ステータス表示: 起動中/クローン中/実行中/完了
"""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from src.redis.client import RedisClient
from src.slack.app import SlackBot
from src.task.models import TaskStatus

logger = logging.getLogger(__name__)

# ステータス表示マッピング
STATUS_DISPLAY_MAP: dict[TaskStatus, str] = {
    TaskStatus.PENDING: "待機中...",
    TaskStatus.STARTING: "起動中...",
    TaskStatus.CLONING: "クローン中...",
    TaskStatus.RUNNING: "実行中...",
    TaskStatus.WAITING_USER: "ユーザー回答待ち...",
    TaskStatus.COMPLETED: "完了",
    TaskStatus.FAILED: "エラー",
    TaskStatus.CANCELLED: "キャンセル",
}


def format_progress_message(status: TaskStatus, step: int, total: int) -> str:
    """進捗メッセージをフォーマットする。

    Args:
        status: タスクの状態
        step: 現在のステップ番号
        total: 総ステップ数

    Returns:
        フォーマットされた進捗メッセージ
    """
    display_text = STATUS_DISPLAY_MAP.get(status, str(status.value))
    return f"{display_text} ({step}/{total})"


class ProgressNotifier(Protocol):
    """進捗通知のプロトコル定義。

    Design Docで定義されたインターフェース:
    - notify: 進捗をRedis pub/subに送信
    - start_listening: Redis pub/subを購読してSlackメッセージを更新
    """

    async def notify(
        self,
        task_id: str,
        status: TaskStatus,
        step: int,
        total: int,
    ) -> None:
        """進捗を通知する。

        Args:
            task_id: タスクID
            status: タスクの状態
            step: 現在のステップ番号
            total: 総ステップ数
        """
        ...

    async def start_listening(
        self,
        task_id: str,
        channel_id: str,
        message_ts: str,
    ) -> None:
        """Redis pub/subを購読してSlackメッセージを更新する。

        この関数は購読をキャンセルするまでブロックする。

        Args:
            task_id: 監視対象のタスクID
            channel_id: Slackチャンネル識別子
            message_ts: 更新対象のメッセージタイムスタンプ
        """
        ...


class ProgressNotifierImpl:
    """ProgressNotifierの実装クラス。

    機能:
    - Redis pub/subで進捗メッセージを送受信
    - Slackメッセージの編集による進捗表示
    - 複数タスクの同時監視

    Attributes:
        _redis: Redisクライアント
        _slack: SlackBotクライアント
        _message_registry: タスクIDとSlackメッセージ情報のマッピング
    """

    def __init__(self, redis: RedisClient, slack: SlackBot) -> None:
        """ProgressNotifierImplを初期化する。

        Args:
            redis: Redisクライアント(pub/sub用)
            slack: SlackBotクライアント(メッセージ更新用)
        """
        self._redis = redis
        self._slack = slack
        self._message_registry: dict[str, dict[str, str]] = {}

        logger.info("ProgressNotifierImpl initialized")

    def register_message(
        self,
        task_id: str,
        channel_id: str,
        message_ts: str,
    ) -> None:
        """タスクIDとSlackメッセージ情報を登録する。

        Args:
            task_id: タスクID
            channel_id: Slackチャンネル識別子
            message_ts: メッセージタイムスタンプ
        """
        self._message_registry[task_id] = {
            "channel_id": channel_id,
            "message_ts": message_ts,
        }
        logger.debug(
            "Registered message for task %s: channel=%s, ts=%s",
            task_id,
            channel_id,
            message_ts,
        )

    async def notify(
        self,
        task_id: str,
        status: TaskStatus,
        step: int,
        total: int,
    ) -> None:
        """進捗をRedis pub/subに送信する。

        Args:
            task_id: タスクID
            status: タスクの状態
            step: 現在のステップ番号
            total: 総ステップ数
        """
        channel = f"progress:{task_id}"
        payload = json.dumps(
            {
                "status": status.value,
                "step": step,
                "total": total,
            }
        )

        await self._redis.publish(channel, payload)
        logger.debug(
            "Published progress for task %s: status=%s, step=%d/%d",
            task_id,
            status.value,
            step,
            total,
        )

    async def start_listening(
        self,
        task_id: str,
        channel_id: str,
        message_ts: str,
    ) -> None:
        """Redis pub/subを購読してSlackメッセージを更新する。

        この関数は購読をキャンセルするまでブロックする。

        Args:
            task_id: 監視対象のタスクID
            channel_id: Slackチャンネル識別子
            message_ts: 更新対象のメッセージタイムスタンプ
        """
        channel = f"progress:{task_id}"
        callback = self._create_update_callback(channel_id, message_ts)

        logger.info(
            "Starting to listen for progress on task %s (channel: %s)",
            task_id,
            channel,
        )

        await self._redis.subscribe(channel, callback)

    def _create_update_callback(
        self,
        channel_id: str,
        message_ts: str,
    ) -> Callable[[str], Awaitable[None]]:
        """Slackメッセージ更新用コールバックを作成する。

        Args:
            channel_id: Slackチャンネル識別子
            message_ts: 更新対象のメッセージタイムスタンプ

        Returns:
            メッセージ受信時に呼び出されるコールバック関数
        """

        async def callback(message: str) -> None:
            try:
                data = json.loads(message)
                status = TaskStatus(data["status"])
                step = data["step"]
                total = data["total"]

                text = format_progress_message(status, step, total)

                await self._slack.update_message(
                    channel=channel_id,
                    ts=message_ts,
                    text=text,
                )

                logger.debug(
                    "Updated Slack message: channel=%s, ts=%s, text=%s",
                    channel_id,
                    message_ts,
                    text,
                )
            except json.JSONDecodeError as e:
                logger.error("Failed to decode progress message: %s", e)
            except KeyError as e:
                logger.error("Missing key in progress message: %s", e)
            except Exception as e:
                logger.error("Failed to update Slack message: %s", e)

        return callback
