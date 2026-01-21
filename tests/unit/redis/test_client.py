"""
Redis接続モジュールの単体テスト。

モックを使用してRedis依存を分離し、以下の機能をテストする:
- publish/subscribe/set/getの各機能
- 接続断->再接続のシナリオ
- ローカルキュー機能
"""

import asyncio
import contextlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.redis.client import (
    LOCAL_QUEUE_MAX_SIZE,
    AsyncRedisClientImpl,
    RedisClient,
)


class TestRedisClientProtocol:
    """RedisClient Protocolの型定義テスト。"""

    def test_protocol_defines_required_methods(self) -> None:
        """Protocolが必要なメソッドを定義していることを確認。"""
        # Protocol型の必須メソッドをチェック
        assert hasattr(RedisClient, "publish")
        assert hasattr(RedisClient, "subscribe")
        assert hasattr(RedisClient, "set")
        assert hasattr(RedisClient, "get")


class TestAsyncRedisClientImplConnection:
    """AsyncRedisClientImplの接続テスト。"""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """モックRedisクライアントを作成。"""
        mock = MagicMock()
        mock.ping = AsyncMock(return_value=True)
        mock.close = AsyncMock()
        mock.publish = AsyncMock(return_value=1)
        mock.set = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=b"test_value")
        mock.pubsub = MagicMock()
        return mock

    @pytest.fixture
    def client(self, mock_redis: MagicMock) -> AsyncRedisClientImpl:
        """テスト用クライアントを作成。"""
        with patch("src.redis.client.Redis.from_url", return_value=mock_redis):
            return AsyncRedisClientImpl("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_connect_success(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """正常接続のテスト。"""
        await client.connect()
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_sets_connected_flag(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """接続後に_connectedフラグがTrueになることを確認。"""
        await client.connect()
        assert client._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, client: AsyncRedisClientImpl, mock_redis: MagicMock) -> None:
        """切断のテスト。"""
        await client.connect()
        await client.disconnect()
        mock_redis.close.assert_called_once()
        assert client._connected is False


class TestAsyncRedisClientImplPublish:
    """AsyncRedisClientImplのpublishテスト。"""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """モックRedisクライアントを作成。"""
        mock = MagicMock()
        mock.ping = AsyncMock(return_value=True)
        mock.close = AsyncMock()
        mock.publish = AsyncMock(return_value=1)
        return mock

    @pytest.fixture
    def client(self, mock_redis: MagicMock) -> AsyncRedisClientImpl:
        """テスト用クライアントを作成。"""
        with patch("src.redis.client.Redis.from_url", return_value=mock_redis):
            return AsyncRedisClientImpl("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_publish_sends_message(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """publishがメッセージを送信することを確認。"""
        await client.connect()
        await client.publish("test_channel", "test_message")
        mock_redis.publish.assert_called_once_with("test_channel", "test_message")

    @pytest.mark.asyncio
    async def test_publish_queues_when_disconnected(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """切断時にメッセージがローカルキューに追加されることを確認。"""
        # 接続しない状態でpublish
        await client.publish("test_channel", "test_message")
        assert len(client._local_queue) == 1
        assert client._local_queue[0] == ("test_channel", "test_message")


class TestAsyncRedisClientImplSubscribe:
    """AsyncRedisClientImplのsubscribeテスト。"""

    @pytest.fixture
    def mock_pubsub(self) -> MagicMock:
        """モックPubSubを作成。"""
        mock = MagicMock()
        mock.subscribe = AsyncMock()
        mock.unsubscribe = AsyncMock()
        # get_messageは即座にCancelledErrorを発生させる
        mock.get_message = AsyncMock(side_effect=asyncio.CancelledError())
        return mock

    @pytest.fixture
    def mock_redis(self, mock_pubsub: MagicMock) -> MagicMock:
        """モックRedisクライアントを作成。"""
        mock = MagicMock()
        mock.ping = AsyncMock(return_value=True)
        mock.close = AsyncMock()
        mock.pubsub = MagicMock(return_value=mock_pubsub)
        return mock

    @pytest.fixture
    def client(self, mock_redis: MagicMock) -> AsyncRedisClientImpl:
        """テスト用クライアントを作成。"""
        with patch("src.redis.client.Redis.from_url", return_value=mock_redis):
            return AsyncRedisClientImpl("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_subscribe_creates_pubsub(
        self,
        client: AsyncRedisClientImpl,
        mock_redis: MagicMock,
        mock_pubsub: MagicMock,
    ) -> None:
        """subscribeがPubSubインスタンスを作成することを確認。"""
        await client.connect()

        async def callback(message: str) -> None:
            pass

        # キャンセルが発生するまで実行
        with pytest.raises(asyncio.CancelledError):
            await client.subscribe("test_channel", callback)

        mock_pubsub.subscribe.assert_called_once_with("test_channel")
        mock_pubsub.unsubscribe.assert_called_once_with("test_channel")

    @pytest.mark.asyncio
    async def test_subscribe_calls_callback_on_message(
        self,
        client: AsyncRedisClientImpl,
        mock_redis: MagicMock,
        mock_pubsub: MagicMock,
    ) -> None:
        """subscribeがメッセージ受信時にコールバックを呼び出すことを確認。"""
        await client.connect()

        received_messages: list[str] = []

        async def callback(message: str) -> None:
            received_messages.append(message)

        # メッセージを1つ返した後、キャンセルをトリガー
        call_count = 0

        async def get_message_side_effect(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"type": "message", "data": b"test_message"}
            # 2回目以降はCancelledErrorを発生させる
            raise asyncio.CancelledError()

        mock_pubsub.get_message = AsyncMock(side_effect=get_message_side_effect)

        with pytest.raises(asyncio.CancelledError):
            await client.subscribe("test_channel", callback)

        assert received_messages == ["test_message"]

    @pytest.mark.asyncio
    async def test_subscribe_raises_when_not_connected(self, client: AsyncRedisClientImpl) -> None:
        """未接続時にsubscribeがConnectionErrorを発生させることを確認。"""

        async def callback(message: str) -> None:
            pass

        with pytest.raises(ConnectionError, match="Not connected to Redis"):
            await client.subscribe("test_channel", callback)


class TestAsyncRedisClientImplSetGet:
    """AsyncRedisClientImplのset/getテスト。"""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """モックRedisクライアントを作成。"""
        mock = MagicMock()
        mock.ping = AsyncMock(return_value=True)
        mock.close = AsyncMock()
        mock.set = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=b"test_value")
        return mock

    @pytest.fixture
    def client(self, mock_redis: MagicMock) -> AsyncRedisClientImpl:
        """テスト用クライアントを作成。"""
        with patch("src.redis.client.Redis.from_url", return_value=mock_redis):
            return AsyncRedisClientImpl("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_set_stores_value(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """setが値を保存することを確認。"""
        await client.connect()
        await client.set("test_key", "test_value")
        mock_redis.set.assert_called_once_with("test_key", "test_value", ex=None)

    @pytest.mark.asyncio
    async def test_set_with_expiration(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """setが有効期限付きで値を保存することを確認。"""
        await client.connect()
        await client.set("test_key", "test_value", ex=3600)
        mock_redis.set.assert_called_once_with("test_key", "test_value", ex=3600)

    @pytest.mark.asyncio
    async def test_get_returns_value(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """getが値を返すことを確認。"""
        await client.connect()
        result = await client.get("test_key")
        assert result == "test_value"
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """キーが存在しない場合にNoneを返すことを確認。"""
        mock_redis.get = AsyncMock(return_value=None)
        await client.connect()
        result = await client.get("nonexistent_key")
        assert result is None


class TestAsyncRedisClientImplReconnect:
    """AsyncRedisClientImplの再接続テスト。"""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """モックRedisクライアントを作成。"""
        mock = MagicMock()
        mock.ping = AsyncMock(return_value=True)
        mock.close = AsyncMock()
        mock.publish = AsyncMock(return_value=1)
        return mock

    @pytest.fixture
    def client(self, mock_redis: MagicMock) -> AsyncRedisClientImpl:
        """テスト用クライアントを作成。"""
        with patch("src.redis.client.Redis.from_url", return_value=mock_redis):
            return AsyncRedisClientImpl("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_reconnect_with_exponential_backoff(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """指数バックオフで再接続を試みることを確認。"""
        # 最初の2回は失敗、3回目で成功
        call_count = 0

        async def ping_side_effect() -> bool:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return True

        mock_redis.ping = AsyncMock(side_effect=ping_side_effect)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client._reconnect()
            # 指数バックオフで1秒、2秒とスリープ
            assert mock_sleep.call_count >= 2

    @pytest.mark.asyncio
    async def test_reconnect_max_delay_is_30_seconds(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """最大遅延が30秒であることを確認。"""
        # 常に失敗させる
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("Connection failed"))

        delays: list[float] = []

        async def capture_sleep(delay: float) -> None:
            delays.append(delay)
            if len(delays) >= 10:
                raise asyncio.CancelledError()

        with (
            patch("asyncio.sleep", side_effect=capture_sleep),
            contextlib.suppress(asyncio.CancelledError),
        ):
            await client._reconnect()

        # 最大遅延が30秒を超えないことを確認
        assert all(d <= 30 for d in delays)


class TestAsyncRedisClientImplLocalQueue:
    """AsyncRedisClientImplのローカルキューテスト。"""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """モックRedisクライアントを作成。"""
        mock = MagicMock()
        mock.ping = AsyncMock(return_value=True)
        mock.close = AsyncMock()
        mock.publish = AsyncMock(return_value=1)
        return mock

    @pytest.fixture
    def client(self, mock_redis: MagicMock) -> AsyncRedisClientImpl:
        """テスト用クライアントを作成。"""
        with patch("src.redis.client.Redis.from_url", return_value=mock_redis):
            return AsyncRedisClientImpl("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_local_queue_max_size(self, client: AsyncRedisClientImpl) -> None:
        """ローカルキューの最大サイズが100であることを確認。"""
        # 100を超えるメッセージを追加
        for i in range(150):
            await client.publish(f"channel_{i}", f"message_{i}")

        # キューサイズが100を超えないことを確認
        assert len(client._local_queue) == LOCAL_QUEUE_MAX_SIZE

    @pytest.mark.asyncio
    async def test_local_queue_fifo_discard(self, client: AsyncRedisClientImpl) -> None:
        """ローカルキューがFIFO方式で古いメッセージを破棄することを確認。"""
        # 100メッセージを追加
        for i in range(100):
            await client.publish(f"channel_{i}", f"message_{i}")

        # 追加で50メッセージを追加
        for i in range(100, 150):
            await client.publish(f"channel_{i}", f"message_{i}")

        # 最初の50メッセージが破棄され、新しい100メッセージが残っていることを確認
        assert len(client._local_queue) == LOCAL_QUEUE_MAX_SIZE
        # 最も古いメッセージは channel_50 (0-49は破棄)
        assert client._local_queue[0][0] == "channel_50"

    @pytest.mark.asyncio
    async def test_flush_local_queue_on_reconnect(
        self, client: AsyncRedisClientImpl, mock_redis: MagicMock
    ) -> None:
        """再接続時にローカルキューのメッセージがRedisに送信されることを確認。"""
        # 切断状態でメッセージを追加
        await client.publish("channel_1", "message_1")
        await client.publish("channel_2", "message_2")

        assert len(client._local_queue) == 2

        # 接続してフラッシュ
        await client.connect()
        await client._flush_local_queue()

        # キューが空になることを確認
        assert len(client._local_queue) == 0
        # メッセージがRedisに送信されたことを確認
        assert mock_redis.publish.call_count == 2
