"""
結果フォーマッターの単体テスト。

post_result関数のテスト。
- 4000文字以下はsend_messageが呼ばれる
- 4001文字以上はupload_fileが呼ばれる
- 境界値テスト(4000文字ちょうど)
"""

from unittest.mock import AsyncMock

import pytest


class TestPostResult:
    """post_result関数のテスト。"""

    @pytest.fixture
    def mock_slack_bot(self) -> AsyncMock:
        """モックされたSlackBotを返す。"""
        mock = AsyncMock()
        mock.send_message = AsyncMock(return_value="1234567890.123456")
        mock.upload_file = AsyncMock(return_value=None)
        return mock

    @pytest.mark.asyncio
    async def test_short_result_uses_send_message(self, mock_slack_bot: AsyncMock) -> None:
        """4000文字以下の結果はsend_messageを使用することを検証。"""
        from src.slack.result_formatter import post_result

        result = "これは短いメッセージです。"
        channel = "C12345"
        thread_ts = "1234567890.000001"
        task_id = "task-123"

        await post_result(mock_slack_bot, result, channel, thread_ts, task_id)

        mock_slack_bot.send_message.assert_called_once_with(channel, result, thread_ts)
        mock_slack_bot.upload_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_long_result_uses_upload_file(self, mock_slack_bot: AsyncMock) -> None:
        """4001文字以上の結果はupload_fileを使用することを検証。"""
        from src.slack.result_formatter import post_result

        result = "x" * 4001
        channel = "C12345"
        thread_ts = "1234567890.000001"
        task_id = "task-123"

        await post_result(mock_slack_bot, result, channel, thread_ts, task_id)

        mock_slack_bot.upload_file.assert_called_once_with(
            channel, result, "result-task-123.txt", thread_ts
        )
        mock_slack_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_boundary_value_4000_uses_send_message(self, mock_slack_bot: AsyncMock) -> None:
        """4000文字ちょうどの結果はsend_messageを使用することを検証。"""
        from src.slack.result_formatter import post_result

        result = "x" * 4000
        channel = "C12345"
        thread_ts = "1234567890.000001"
        task_id = "task-boundary"

        await post_result(mock_slack_bot, result, channel, thread_ts, task_id)

        mock_slack_bot.send_message.assert_called_once_with(channel, result, thread_ts)
        mock_slack_bot.upload_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_boundary_value_4001_uses_upload_file(self, mock_slack_bot: AsyncMock) -> None:
        """4001文字の結果はupload_fileを使用することを検証。"""
        from src.slack.result_formatter import post_result

        result = "y" * 4001
        channel = "C12345"
        thread_ts = "1234567890.000001"
        task_id = "task-boundary-2"

        await post_result(mock_slack_bot, result, channel, thread_ts, task_id)

        mock_slack_bot.upload_file.assert_called_once_with(
            channel, result, "result-task-boundary-2.txt", thread_ts
        )
        mock_slack_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_result_uses_send_message(self, mock_slack_bot: AsyncMock) -> None:
        """空文字の結果はsend_messageを使用することを検証。"""
        from src.slack.result_formatter import post_result

        result = ""
        channel = "C12345"
        thread_ts = "1234567890.000001"
        task_id = "task-empty"

        await post_result(mock_slack_bot, result, channel, thread_ts, task_id)

        mock_slack_bot.send_message.assert_called_once_with(channel, result, thread_ts)
        mock_slack_bot.upload_file.assert_not_called()


class TestSlackMessageLimit:
    """SLACK_MESSAGE_LIMIT定数のテスト。"""

    def test_slack_message_limit_is_4000(self) -> None:
        """SLACK_MESSAGE_LIMITが4000であることを検証。"""
        from src.slack.result_formatter import SLACK_MESSAGE_LIMIT

        assert SLACK_MESSAGE_LIMIT == 4000
