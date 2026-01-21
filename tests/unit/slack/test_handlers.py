"""
Slackハンドラの単体テスト。

app_mentionとslash_commandハンドラのテスト。
"""

from unittest.mock import AsyncMock

import pytest


class TestAppMentionHandler:
    """app_mentionイベントハンドラのテスト。"""

    @pytest.fixture
    def mock_event(self) -> dict:
        """モックされたapp_mentionイベントを返す。"""
        return {
            "type": "app_mention",
            "user": "U12345",
            "text": "<@U_BOT> https://github.com/owner/repo help",
            "ts": "1234567890.000001",
            "channel": "C12345",
        }

    @pytest.fixture
    def mock_say(self) -> AsyncMock:
        """モックされたsay関数を返す。"""
        return AsyncMock(return_value={"ts": "1234567890.123456"})

    @pytest.mark.asyncio
    async def test_app_mention_responds_in_thread(
        self, mock_event: dict, mock_say: AsyncMock
    ) -> None:
        """app_mentionイベントがスレッドで応答することを検証。"""
        from src.slack.handlers import handle_app_mention

        await handle_app_mention(event=mock_event, say=mock_say)

        mock_say.assert_called_once()
        call_kwargs = mock_say.call_args[1]
        assert call_kwargs["thread_ts"] == mock_event["ts"]

    @pytest.mark.asyncio
    async def test_app_mention_includes_startup_message(
        self, mock_event: dict, mock_say: AsyncMock
    ) -> None:
        """app_mentionイベントが「起動中...」メッセージを含むことを検証。"""
        from src.slack.handlers import handle_app_mention

        await handle_app_mention(event=mock_event, say=mock_say)

        call_kwargs = mock_say.call_args[1]
        # 1秒以内に応答するための初期メッセージ
        assert "起動中" in call_kwargs["text"]


class TestSlashCommandHandler:
    """スラッシュコマンドハンドラのテスト。"""

    @pytest.fixture
    def mock_command(self) -> dict:
        """モックされたスラッシュコマンドを返す。"""
        return {
            "command": "/claude",
            "text": "https://github.com/example/repo analyze this",
            "user_id": "U12345",
            "channel_id": "C12345",
            "response_url": "https://hooks.slack.com/commands/xxx",
        }

    @pytest.fixture
    def mock_ack(self) -> AsyncMock:
        """モックされたack関数を返す。"""
        return AsyncMock()

    @pytest.fixture
    def mock_respond(self) -> AsyncMock:
        """モックされたrespond関数を返す。"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_slash_command_acknowledges_immediately(
        self, mock_command: dict, mock_ack: AsyncMock, mock_respond: AsyncMock
    ) -> None:
        """スラッシュコマンドが即座にackを返すことを検証。"""
        from src.slack.handlers import handle_claude_command

        await handle_claude_command(command=mock_command, ack=mock_ack, respond=mock_respond)

        mock_ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_slash_command_responds_with_startup_message(
        self, mock_command: dict, mock_ack: AsyncMock, mock_respond: AsyncMock
    ) -> None:
        """スラッシュコマンドが「起動中...」メッセージで応答することを検証。"""
        from src.slack.handlers import handle_claude_command

        await handle_claude_command(command=mock_command, ack=mock_ack, respond=mock_respond)

        mock_respond.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "起動中" in call_args


class TestExtractGitHubUrl:
    """GitHub URL抽出のテスト。"""

    def test_extracts_valid_github_url(self) -> None:
        """有効なGitHub URLを抽出できることを検証。"""
        from src.slack.handlers import extract_github_url

        text = "https://github.com/owner/repo このリポジトリを調査して"
        result = extract_github_url(text)
        assert result == "https://github.com/owner/repo"

    def test_extracts_url_with_path(self) -> None:
        """パスを含むGitHub URLを抽出できることを検証。"""
        from src.slack.handlers import extract_github_url

        text = "https://github.com/owner/repo/tree/main/src を調査"
        result = extract_github_url(text)
        assert result == "https://github.com/owner/repo/tree/main/src"

    def test_returns_none_when_no_url(self) -> None:
        """URLがない場合はNoneを返すことを検証。"""
        from src.slack.handlers import extract_github_url

        text = "URLなしのテキスト"
        result = extract_github_url(text)
        assert result is None

    def test_extracts_first_url_when_multiple(self) -> None:
        """複数URLがある場合は最初のURLを返すことを検証。"""
        from src.slack.handlers import extract_github_url

        text = "https://github.com/first/repo と https://github.com/second/repo"
        result = extract_github_url(text)
        assert result == "https://github.com/first/repo"

    def test_handles_url_with_special_characters(self) -> None:
        """特殊文字を含むURLを正しく抽出することを検証。"""
        from src.slack.handlers import extract_github_url

        text = "https://github.com/owner/repo-name_v2 を確認"
        result = extract_github_url(text)
        assert result == "https://github.com/owner/repo-name_v2"

    def test_ignores_non_github_urls(self) -> None:
        """GitHub以外のURLは無視することを検証。"""
        from src.slack.handlers import extract_github_url

        text = "https://gitlab.com/owner/repo を調査"
        result = extract_github_url(text)
        assert result is None

    def test_removes_bot_mention_before_extraction(self) -> None:
        """ボットメンションを含むテキストから正しくURLを抽出することを検証。"""
        from src.slack.handlers import extract_github_url

        text = "<@U12345> https://github.com/owner/repo 調査して"
        result = extract_github_url(text)
        assert result == "https://github.com/owner/repo"


class TestGenerateTaskId:
    """タスクID生成のテスト。"""

    def test_generates_uuid_v4_format(self) -> None:
        """UUID v4形式のタスクIDを生成することを検証。"""
        import re

        from src.slack.handlers import generate_task_id

        task_id = generate_task_id()
        # UUID v4形式: 8-4-4-4-12 (4番目のセグメントは4で始まり、5番目のセグメントは8,9,a,bで始まる)
        uuid_v4_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        assert re.match(uuid_v4_pattern, task_id) is not None

    def test_generates_unique_ids(self) -> None:
        """生成されるタスクIDが一意であることを検証。"""
        from src.slack.handlers import generate_task_id

        ids = {generate_task_id() for _ in range(100)}
        assert len(ids) == 100


class TestAppMentionHandlerWithValidation:
    """app_mentionイベントハンドラのバリデーションテスト。"""

    @pytest.fixture
    def mock_event_with_url(self) -> dict:
        """GitHub URLを含むapp_mentionイベントを返す。"""
        return {
            "type": "app_mention",
            "user": "U12345",
            "text": "<@U_BOT> https://github.com/owner/repo このリポを調査して",
            "ts": "1234567890.000001",
            "channel": "C12345",
        }

    @pytest.fixture
    def mock_event_without_url(self) -> dict:
        """GitHub URLを含まないapp_mentionイベントを返す。"""
        return {
            "type": "app_mention",
            "user": "U12345",
            "text": "<@U_BOT> このリポを調査して",
            "ts": "1234567890.000001",
            "channel": "C12345",
        }

    @pytest.fixture
    def mock_say(self) -> AsyncMock:
        """モックされたsay関数を返す。"""
        return AsyncMock(return_value={"ts": "1234567890.123456"})

    @pytest.mark.asyncio
    async def test_returns_error_when_no_github_url(
        self, mock_event_without_url: dict, mock_say: AsyncMock
    ) -> None:
        """GitHub URLがない場合にエラーメッセージを返すことを検証。"""
        from src.slack.handlers import handle_app_mention

        await handle_app_mention(event=mock_event_without_url, say=mock_say)

        call_kwargs = mock_say.call_args[1]
        assert "リポジトリURLを指定してください" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_returns_task_id_when_url_present(
        self, mock_event_with_url: dict, mock_say: AsyncMock
    ) -> None:
        """GitHub URLがある場合に起動中メッセージとタスクIDを返すことを検証。"""
        import re

        from src.slack.handlers import handle_app_mention

        result = await handle_app_mention(event=mock_event_with_url, say=mock_say)

        call_kwargs = mock_say.call_args[1]
        assert "起動中" in call_kwargs["text"]
        # タスクIDがUUID v4形式であることを確認
        uuid_v4_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        assert result is not None
        assert re.match(uuid_v4_pattern, result["task_id"]) is not None


class TestSlashCommandHandlerWithValidation:
    """スラッシュコマンドハンドラのバリデーションテスト。"""

    @pytest.fixture
    def mock_command_with_url(self) -> dict:
        """GitHub URLを含むスラッシュコマンドを返す。"""
        return {
            "command": "/claude",
            "text": "https://github.com/owner/repo このリポを調査して",
            "user_id": "U12345",
            "channel_id": "C12345",
            "response_url": "https://hooks.slack.com/commands/xxx",
        }

    @pytest.fixture
    def mock_command_without_url(self) -> dict:
        """GitHub URLを含まないスラッシュコマンドを返す。"""
        return {
            "command": "/claude",
            "text": "このリポを調査して",
            "user_id": "U12345",
            "channel_id": "C12345",
            "response_url": "https://hooks.slack.com/commands/xxx",
        }

    @pytest.fixture
    def mock_ack(self) -> AsyncMock:
        """モックされたack関数を返す。"""
        return AsyncMock()

    @pytest.fixture
    def mock_respond(self) -> AsyncMock:
        """モックされたrespond関数を返す。"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_returns_error_when_no_github_url(
        self, mock_command_without_url: dict, mock_ack: AsyncMock, mock_respond: AsyncMock
    ) -> None:
        """GitHub URLがない場合にエラーメッセージを返すことを検証。"""
        from src.slack.handlers import handle_claude_command

        await handle_claude_command(
            command=mock_command_without_url, ack=mock_ack, respond=mock_respond
        )

        mock_ack.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "リポジトリURLを指定してください" in call_args

    @pytest.mark.asyncio
    async def test_returns_task_id_when_url_present(
        self, mock_command_with_url: dict, mock_ack: AsyncMock, mock_respond: AsyncMock
    ) -> None:
        """GitHub URLがある場合に起動中メッセージとタスクIDを返すことを検証。"""
        import re

        from src.slack.handlers import handle_claude_command

        result = await handle_claude_command(
            command=mock_command_with_url, ack=mock_ack, respond=mock_respond
        )

        mock_ack.assert_called_once()
        call_args = mock_respond.call_args[0][0]
        assert "起動中" in call_args
        # タスクIDがUUID v4形式であることを確認
        uuid_v4_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        assert result is not None
        assert re.match(uuid_v4_pattern, result["task_id"]) is not None


class TestCreateTask:
    """create_task関数のテスト。"""

    def test_creates_task_with_required_fields(self) -> None:
        """必須フィールドでTaskインスタンスを生成することを検証。"""
        from src.slack.handlers import create_task
        from src.task.models import TaskStatus

        task = create_task(
            task_id="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            channel_id="C12345",
            thread_ts="1234567890.000001",
            user_id="U12345",
            prompt="リポジトリを調査して",
            repository_url="https://github.com/owner/repo",
        )

        assert task.id == "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        assert task.channel_id == "C12345"
        assert task.thread_ts == "1234567890.000001"
        assert task.user_id == "U12345"
        assert task.prompt == "リポジトリを調査して"
        assert task.repository_url == "https://github.com/owner/repo"
        assert task.status == TaskStatus.PENDING
        assert task.created_at > 0
        assert task.idempotency_key == "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"

    def test_creates_task_with_custom_idempotency_key(self) -> None:
        """カスタムidempotency_keyでTaskインスタンスを生成することを検証。"""
        from src.slack.handlers import create_task

        task = create_task(
            task_id="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            channel_id="C12345",
            thread_ts="1234567890.000001",
            user_id="U12345",
            prompt="リポジトリを調査して",
            repository_url="https://github.com/owner/repo",
            idempotency_key="custom-key-123",
        )

        assert task.idempotency_key == "custom-key-123"

    def test_task_created_at_is_current_timestamp(self) -> None:
        """created_atが現在時刻付近のタイムスタンプであることを検証。"""
        import time

        from src.slack.handlers import create_task

        before = time.time()
        task = create_task(
            task_id="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            channel_id="C12345",
            thread_ts="1234567890.000001",
            user_id="U12345",
            prompt="リポジトリを調査して",
            repository_url="https://github.com/owner/repo",
        )
        after = time.time()

        assert before <= task.created_at <= after


class TestTaskManagerIntegration:
    """TaskManager連携のテスト。"""

    @pytest.fixture
    def mock_task_manager(self) -> AsyncMock:
        """モックされたTaskManagerを返す。"""
        mock = AsyncMock()
        mock.submit_task = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def mock_event_with_url(self) -> dict:
        """GitHub URLを含むapp_mentionイベントを返す。"""
        return {
            "type": "app_mention",
            "user": "U12345",
            "text": "<@U_BOT> https://github.com/owner/repo このリポを調査して",
            "ts": "1234567890.000001",
            "channel": "C12345",
        }

    @pytest.fixture
    def mock_say(self) -> AsyncMock:
        """モックされたsay関数を返す。"""
        return AsyncMock(return_value={"ts": "1234567890.123456"})

    @pytest.mark.asyncio
    async def test_app_mention_submits_task_to_manager(
        self, mock_event_with_url: dict, mock_say: AsyncMock, mock_task_manager: AsyncMock
    ) -> None:
        """TaskManagerが渡された場合にタスクが投入されることを検証。"""
        from src.slack.handlers import handle_app_mention
        from src.task.models import Task

        await handle_app_mention(
            event=mock_event_with_url,
            say=mock_say,
            task_manager=mock_task_manager,
        )

        mock_task_manager.submit_task.assert_called_once()
        submitted_task = mock_task_manager.submit_task.call_args[0][0]
        assert isinstance(submitted_task, Task)
        assert submitted_task.repository_url == "https://github.com/owner/repo"

    @pytest.mark.asyncio
    async def test_app_mention_works_without_task_manager(
        self, mock_event_with_url: dict, mock_say: AsyncMock
    ) -> None:
        """TaskManagerがない場合でも正常に動作することを検証(後方互換性)。"""
        from src.slack.handlers import handle_app_mention

        result = await handle_app_mention(
            event=mock_event_with_url,
            say=mock_say,
        )

        assert result is not None
        assert result["task_id"] is not None
        mock_say.assert_called_once()
