"""
SlackBot実装の単体テスト。

Design Docで定義されたSlackBotプロトコルの実装をテストする。
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from src.slack.app import SlackBotImpl


class TestSlackBotProtocol:
    """SlackBotプロトコルの型チェックテスト。"""

    def test_slack_bot_impl_implements_protocol(self) -> None:
        """SlackBotImplがSlackBotプロトコルを実装していることを検証。"""
        from src.slack.app import SlackBot, SlackBotImpl

        # プロトコル適合性チェック - 必要なメソッドが存在するか
        impl = SlackBotImpl(
            app=MagicMock(),
            web_client=MagicMock(),
        )

        # Protocol型に必要なメソッドがすべて存在することを検証
        assert hasattr(impl, "start")
        assert hasattr(impl, "send_message")
        assert hasattr(impl, "update_message")
        assert hasattr(impl, "upload_file")

        # 型チェック用 - 静的解析で検証される
        bot: SlackBot = impl
        assert bot is not None


class TestSlackBotImplSendMessage:
    """send_messageメソッドのテスト。"""

    @pytest.fixture
    def mock_web_client(self) -> MagicMock:
        """モックされたSlack WebClientを返す。"""
        client = MagicMock()
        client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.123456"})
        return client

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """モックされたSlack Appを返す。"""
        return MagicMock()

    @pytest.fixture
    def slack_bot(self, mock_app: MagicMock, mock_web_client: MagicMock) -> "SlackBotImpl":
        """テスト用のSlackBotImplインスタンスを返す。"""
        from src.slack.app import SlackBotImpl

        return SlackBotImpl(app=mock_app, web_client=mock_web_client)

    @pytest.mark.asyncio
    async def test_send_message_without_thread(
        self, slack_bot: "SlackBotImpl", mock_web_client: MagicMock
    ) -> None:
        """スレッドなしでメッセージを送信できることを検証。"""
        result = await slack_bot.send_message(channel="C12345", text="Hello")

        mock_web_client.chat_postMessage.assert_called_once_with(
            channel="C12345",
            text="Hello",
            thread_ts=None,
        )
        assert result == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_send_message_with_thread(
        self, slack_bot: "SlackBotImpl", mock_web_client: MagicMock
    ) -> None:
        """スレッドありでメッセージを送信できることを検証。"""
        result = await slack_bot.send_message(
            channel="C12345", text="Reply", thread_ts="1234567890.000001"
        )

        mock_web_client.chat_postMessage.assert_called_once_with(
            channel="C12345",
            text="Reply",
            thread_ts="1234567890.000001",
        )
        assert result == "1234567890.123456"


class TestSlackBotImplUpdateMessage:
    """update_messageメソッドのテスト。"""

    @pytest.fixture
    def mock_web_client(self) -> MagicMock:
        """モックされたSlack WebClientを返す。"""
        client = MagicMock()
        client.chat_update = AsyncMock(return_value={"ok": True})
        return client

    @pytest.fixture
    def slack_bot(self, mock_web_client: MagicMock) -> "SlackBotImpl":
        """テスト用のSlackBotImplインスタンスを返す。"""
        from src.slack.app import SlackBotImpl

        return SlackBotImpl(app=MagicMock(), web_client=mock_web_client)

    @pytest.mark.asyncio
    async def test_update_message(
        self, slack_bot: "SlackBotImpl", mock_web_client: MagicMock
    ) -> None:
        """メッセージを更新できることを検証。"""
        await slack_bot.update_message(
            channel="C12345",
            ts="1234567890.123456",
            text="Updated message",
        )

        mock_web_client.chat_update.assert_called_once_with(
            channel="C12345",
            ts="1234567890.123456",
            text="Updated message",
        )


class TestSlackBotImplUploadFile:
    """upload_fileメソッドのテスト。"""

    @pytest.fixture
    def mock_web_client(self) -> MagicMock:
        """モックされたSlack WebClientを返す。"""
        client = MagicMock()
        client.files_upload_v2 = AsyncMock(return_value={"ok": True})
        return client

    @pytest.fixture
    def slack_bot(self, mock_web_client: MagicMock) -> "SlackBotImpl":
        """テスト用のSlackBotImplインスタンスを返す。"""
        from src.slack.app import SlackBotImpl

        return SlackBotImpl(app=MagicMock(), web_client=mock_web_client)

    @pytest.mark.asyncio
    async def test_upload_file_without_thread(
        self, slack_bot: "SlackBotImpl", mock_web_client: MagicMock
    ) -> None:
        """スレッドなしでファイルをアップロードできることを検証。"""
        await slack_bot.upload_file(
            channel="C12345",
            content="file content",
            filename="result.txt",
        )

        mock_web_client.files_upload_v2.assert_called_once_with(
            channel="C12345",
            content="file content",
            filename="result.txt",
            thread_ts=None,
        )

    @pytest.mark.asyncio
    async def test_upload_file_with_thread(
        self, slack_bot: "SlackBotImpl", mock_web_client: MagicMock
    ) -> None:
        """スレッドありでファイルをアップロードできることを検証。"""
        await slack_bot.upload_file(
            channel="C12345",
            content="file content",
            filename="result.txt",
            thread_ts="1234567890.000001",
        )

        mock_web_client.files_upload_v2.assert_called_once_with(
            channel="C12345",
            content="file content",
            filename="result.txt",
            thread_ts="1234567890.000001",
        )


class TestSlackBotImplStart:
    """startメソッドのテスト。"""

    @pytest.fixture
    def mock_handler(self) -> MagicMock:
        """モックされたSocketModeHandlerを返す。"""
        handler = MagicMock()
        handler.start_async = AsyncMock()
        return handler

    @pytest.mark.asyncio
    async def test_start_initiates_socket_mode(self, mock_handler: MagicMock) -> None:
        """startメソッドがSocket Mode接続を開始することを検証。"""
        from src.slack.app import SlackBotImpl

        mock_app = MagicMock()
        mock_web_client = MagicMock()

        with patch("src.slack.app.SocketModeHandler", return_value=mock_handler):
            bot = SlackBotImpl(
                app=mock_app,
                web_client=mock_web_client,
                app_token="xapp-test-token",
            )
            await bot.start()

        mock_handler.start_async.assert_called_once()
