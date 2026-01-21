"""
Redis接続クライアントモジュール。

Design Doc準拠のインターフェースを実装:
- Protocol型でインターフェース定義
- 非同期Redis接続(redis-py async)
- pub/sub機能
- 状態保存(set/get)機能
- 接続断時の再接続ロジック(指数バックオフ)
- ローカルキュー(100メッセージ上限、FIFO破棄)
"""

import asyncio
import contextlib
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Protocol

from redis.asyncio import Redis

# ローカルキュー設定
LOCAL_QUEUE_MAX_SIZE = 100

logger = logging.getLogger(__name__)


class RedisClient(Protocol):
    """Redisクライアントのプロトコル型。

    Design Docで定義されたインターフェース:
    - publish: チャンネルへのメッセージ送信
    - subscribe: チャンネルの購読
    - set: キー/値の保存
    - get: キー/値の取得
    """

    async def publish(self, channel: str, message: str) -> None:
        """チャンネルにメッセージを送信する。

        Args:
            channel: 送信先チャンネル名
            message: 送信するメッセージ
        """
        ...

    async def subscribe(self, channel: str, callback: Callable[[str], Awaitable[None]]) -> None:
        """チャンネルを購読し、メッセージ受信時にコールバックを実行する。

        Args:
            channel: 購読するチャンネル名
            callback: メッセージ受信時に呼び出される非同期コールバック関数
        """
        ...

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """キー/値を保存する。

        Args:
            key: 保存するキー
            value: 保存する値
            ex: 有効期限(秒)。Noneの場合は無期限。
        """
        ...

    async def get(self, key: str) -> str | None:
        """キーに対応する値を取得する。

        Args:
            key: 取得するキー

        Returns:
            キーに対応する値。存在しない場合はNone。
        """
        ...


class AsyncRedisClientImpl:
    """RedisClientの非同期実装。

    機能:
    - 依存性注入パターン(redis URLを引数で受け取る)
    - 指数バックオフによる再接続ロジック(1秒->2秒->4秒...最大30秒)
    - ローカルキュー(100メッセージ上限、FIFO破棄)
    - 接続状態のログ出力

    Attributes:
        _redis_url: Redis接続URL
        _redis: Redisクライアントインスタンス
        _connected: 接続状態フラグ
        _local_queue: 接続断時のメッセージキュー
        _reconnect_task: 再接続タスク
    """

    # 再接続設定
    INITIAL_BACKOFF = 1.0  # 初期バックオフ(秒)
    MAX_BACKOFF = 30.0  # 最大バックオフ(秒)
    BACKOFF_MULTIPLIER = 2.0  # バックオフ乗数

    def __init__(self, redis_url: str) -> None:
        """AsyncRedisClientImplを初期化する。

        Args:
            redis_url: Redis接続URL (例: redis://localhost:6379)
        """
        self._redis_url = redis_url
        self._redis: Redis = Redis.from_url(redis_url)
        self._connected = False
        self._local_queue: deque[tuple[str, str]] = deque(maxlen=LOCAL_QUEUE_MAX_SIZE)
        self._reconnect_task: asyncio.Task[None] | None = None

        logger.info("Redis client initialized with URL: %s", redis_url)

    async def connect(self) -> None:
        """Redisに接続する。

        接続に失敗した場合はConnectionErrorを発生させる(Fail-Fast)。
        """
        try:
            await self._redis.ping()
            self._connected = True
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            raise ConnectionError(f"Failed to connect to Redis: {e}") from e

    async def disconnect(self) -> None:
        """Redisから切断する。"""
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None

        await self._redis.close()
        self._connected = False
        logger.info("Disconnected from Redis")

    async def publish(self, channel: str, message: str) -> None:
        """チャンネルにメッセージを送信する。

        接続が切断されている場合はローカルキューに追加し、
        バックグラウンドで再接続を試みる。

        Args:
            channel: 送信先チャンネル名
            message: 送信するメッセージ
        """
        if not self._connected:
            logger.warning("Not connected to Redis, queuing message for channel: %s", channel)
            self._add_to_local_queue(channel, message)
            self._start_reconnect()
            return

        try:
            await self._redis.publish(channel, message)
            logger.debug("Published message to channel %s", channel)
        except Exception as e:
            logger.error("Failed to publish message: %s", e)
            self._connected = False
            self._add_to_local_queue(channel, message)
            self._start_reconnect()

    async def subscribe(self, channel: str, callback: Callable[[str], Awaitable[None]]) -> None:
        """チャンネルを購読し、メッセージ受信時にコールバックを実行する。

        この関数は購読をキャンセルするまでブロックする。

        Args:
            channel: 購読するチャンネル名
            callback: メッセージ受信時に呼び出される非同期コールバック関数
        """
        if not self._connected:
            logger.error("Cannot subscribe: not connected to Redis")
            raise ConnectionError("Not connected to Redis")

        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        logger.info("Subscribed to channel: %s", channel)

        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is not None and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await callback(data)
        except asyncio.CancelledError:
            logger.info("Subscription cancelled for channel: %s", channel)
            raise
        finally:
            await pubsub.unsubscribe(channel)
            logger.info("Unsubscribed from channel: %s", channel)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """キー/値を保存する。

        Args:
            key: 保存するキー
            value: 保存する値
            ex: 有効期限(秒)。Noneの場合は無期限。

        Raises:
            ConnectionError: Redisに接続されていない場合
        """
        if not self._connected:
            logger.error("Cannot set value: not connected to Redis")
            raise ConnectionError("Not connected to Redis")

        try:
            await self._redis.set(key, value, ex=ex)
            logger.debug("Set key %s with expiration %s", key, ex)
        except Exception as e:
            logger.error("Failed to set key %s: %s", key, e)
            self._connected = False
            raise

    async def get(self, key: str) -> str | None:
        """キーに対応する値を取得する。

        Args:
            key: 取得するキー

        Returns:
            キーに対応する値。存在しない場合はNone。

        Raises:
            ConnectionError: Redisに接続されていない場合
        """
        if not self._connected:
            logger.error("Cannot get value: not connected to Redis")
            raise ConnectionError("Not connected to Redis")

        try:
            result = await self._redis.get(key)
            if result is None:
                return None
            if isinstance(result, bytes):
                return result.decode("utf-8")
            return str(result)
        except Exception as e:
            logger.error("Failed to get key %s: %s", key, e)
            self._connected = False
            raise

    def _add_to_local_queue(self, channel: str, message: str) -> None:
        """ローカルキューにメッセージを追加する。

        キューが最大サイズに達している場合、古いメッセージを破棄する(FIFO)。

        Args:
            channel: チャンネル名
            message: メッセージ
        """
        self._local_queue.append((channel, message))
        logger.debug(
            "Added message to local queue (size: %d/%d)",
            len(self._local_queue),
            LOCAL_QUEUE_MAX_SIZE,
        )

    def _start_reconnect(self) -> None:
        """バックグラウンドで再接続を開始する。"""
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect())
            logger.info("Started reconnection task")

    async def _reconnect(self) -> None:
        """指数バックオフで再接続を試みる。

        再接続に成功した場合、ローカルキューのメッセージをフラッシュする。
        """
        backoff = self.INITIAL_BACKOFF

        while not self._connected:
            logger.info("Attempting to reconnect (backoff: %.1f seconds)", backoff)

            try:
                await self._redis.ping()
                self._connected = True
                logger.info("Reconnected to Redis successfully")
                await self._flush_local_queue()
                return
            except Exception as e:
                logger.warning("Reconnection failed: %s", e)

            await asyncio.sleep(backoff)
            backoff = min(backoff * self.BACKOFF_MULTIPLIER, self.MAX_BACKOFF)

    async def _flush_local_queue(self) -> None:
        """ローカルキューのメッセージをRedisに送信する。"""
        while self._local_queue:
            channel, message = self._local_queue.popleft()
            try:
                await self._redis.publish(channel, message)
                logger.debug("Flushed queued message to channel %s", channel)
            except Exception as e:
                logger.error("Failed to flush queued message: %s", e)
                # 失敗したメッセージをキューの先頭に戻す
                self._local_queue.appendleft((channel, message))
                self._connected = False
                break

        logger.info("Flushed %d messages from local queue", len(self._local_queue))
