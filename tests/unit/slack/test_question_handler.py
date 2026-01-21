"""
QuestionHandler unit tests.

Tests question forwarding and answer redirect for Human-in-the-loop flow.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from src.slack.question_handler import (
    DEFAULT_QUESTION_TIMEOUT_SECONDS,
    QuestionHandler,
    QuestionHandlerConfig,
)
from src.task.models import HumanQuestion, Task, TaskStatus


class TestQuestionHandlerConfig:
    """QuestionHandlerConfig tests."""

    def test_default_timeout(self) -> None:
        """Verify default timeout is 600 seconds."""
        config = QuestionHandlerConfig()
        assert config.timeout_seconds == DEFAULT_QUESTION_TIMEOUT_SECONDS
        assert config.timeout_seconds == 600

    def test_custom_timeout(self) -> None:
        """Verify custom timeout can be set."""
        config = QuestionHandlerConfig(timeout_seconds=300)
        assert config.timeout_seconds == 300


class TestQuestionHandlerInit:
    """QuestionHandler initialization tests."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Return mock Redis client."""
        mock = AsyncMock()
        mock.set = AsyncMock(return_value=None)
        mock.get = AsyncMock(return_value=None)
        mock.publish = AsyncMock(return_value=1)
        mock.subscribe = AsyncMock()
        return mock

    @pytest.fixture
    def mock_slack_bot(self) -> AsyncMock:
        """Return mock Slack Bot."""
        mock = AsyncMock()
        mock.send_message = AsyncMock(return_value="1234567890.123456")
        return mock

    def test_init_with_defaults(self, mock_redis: AsyncMock, mock_slack_bot: AsyncMock) -> None:
        """Verify initialization with default settings."""
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot)

        assert handler._config.timeout_seconds == DEFAULT_QUESTION_TIMEOUT_SECONDS
        assert len(handler._pending_questions) == 0
        assert len(handler._answer_futures) == 0

    def test_init_with_custom_config(
        self, mock_redis: AsyncMock, mock_slack_bot: AsyncMock
    ) -> None:
        """Verify initialization with custom settings."""
        config = QuestionHandlerConfig(timeout_seconds=120)
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot, config=config)

        assert handler._config.timeout_seconds == 120


class TestQuestionHandlerHandleQuestion:
    """QuestionHandler.handle_question tests."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Return mock Redis client."""
        mock = AsyncMock()
        mock.set = AsyncMock(return_value=None)
        mock.get = AsyncMock(return_value=None)
        mock.publish = AsyncMock(return_value=1)
        return mock

    @pytest.fixture
    def mock_slack_bot(self) -> AsyncMock:
        """Return mock Slack Bot."""
        mock = AsyncMock()
        mock.send_message = AsyncMock(return_value="1234567890.123456")
        return mock

    @pytest.fixture
    def sample_task(self) -> Task:
        """Return sample task."""
        return Task(
            id="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            channel_id="C12345",
            thread_ts="1234567890.000001",
            user_id="U12345",
            prompt="Test prompt",
            repository_url="https://github.com/owner/repo",
            status=TaskStatus.RUNNING,
            created_at=1234567890.0,
            idempotency_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_updates_task_status_to_waiting_user(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
        sample_task: Task,
    ) -> None:
        """Verify task status is updated to WAITING_USER when processing question."""
        # Short timeout for testing
        config = QuestionHandlerConfig(timeout_seconds=1)
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot, config=config)

        # Process question (will timeout)
        await handler.handle_question(sample_task, "Test question")

        # Verify task state was saved to Redis
        assert mock_redis.set.called

        # First set call is WAITING_USER update
        first_call_args = mock_redis.set.call_args_list[0]
        assert f"task:{sample_task.id}" in first_call_args[0]

    @pytest.mark.asyncio
    async def test_posts_question_to_slack(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
        sample_task: Task,
    ) -> None:
        """Verify question is posted to Slack."""
        config = QuestionHandlerConfig(timeout_seconds=1)
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot, config=config)

        question = "Should I delete this file?"
        await handler.handle_question(sample_task, question)

        # Verify message was sent to Slack (2 calls after timeout)
        mock_slack_bot.send_message.assert_called()
        # Verify first call (question post)
        first_call_kwargs = mock_slack_bot.send_message.call_args_list[0][1]
        assert first_call_kwargs["channel"] == sample_task.channel_id
        assert first_call_kwargs["thread_ts"] == sample_task.thread_ts
        assert question in first_call_kwargs["text"]
        assert f"<@{sample_task.user_id}>" in first_call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_returns_answer_when_provided(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
        sample_task: Task,
    ) -> None:
        """Verify answer is returned when provided."""
        config = QuestionHandlerConfig(timeout_seconds=5)
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot, config=config)

        # Submit answer in background
        async def submit_answer_later() -> None:
            await asyncio.sleep(0.1)
            await handler.submit_answer(sample_task.id, "Yes, please delete it")

        task = asyncio.create_task(submit_answer_later())

        answer = await handler.handle_question(sample_task, "Should I delete it?")

        # Ensure background task completes
        await task

        assert answer == "Yes, please delete it"

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
        sample_task: Task,
    ) -> None:
        """Verify None is returned on timeout."""
        config = QuestionHandlerConfig(timeout_seconds=1)
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot, config=config)

        answer = await handler.handle_question(sample_task, "Test question")

        assert answer is None

    @pytest.mark.asyncio
    async def test_cancels_task_on_timeout(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
        sample_task: Task,
    ) -> None:
        """Verify task is CANCELLED on timeout."""
        config = QuestionHandlerConfig(timeout_seconds=1)
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot, config=config)

        await handler.handle_question(sample_task, "Test question")

        # Verify task status was updated to CANCELLED
        # Last set call is CANCELLED update
        last_call_args = mock_redis.set.call_args_list[-1]
        assert f"task:{sample_task.id}" in last_call_args[0]
        # Verify JSON contains CANCELLED
        task_json = last_call_args[0][1]
        assert "cancelled" in task_json.lower()

    @pytest.mark.asyncio
    async def test_notifies_user_on_timeout(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
        sample_task: Task,
    ) -> None:
        """Verify user is notified on timeout."""
        config = QuestionHandlerConfig(timeout_seconds=1)
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot, config=config)

        await handler.handle_question(sample_task, "Test question")

        # send_message called twice (question post + timeout notification)
        assert mock_slack_bot.send_message.call_count == 2

        # Last call is timeout notification
        last_call_kwargs = mock_slack_bot.send_message.call_args_list[-1][1]
        assert "Timeout" in last_call_kwargs["text"]


class TestQuestionHandlerSubmitAnswer:
    """QuestionHandler.submit_answer tests."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Return mock Redis client."""
        mock = AsyncMock()
        mock.set = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def mock_slack_bot(self) -> AsyncMock:
        """Return mock Slack Bot."""
        mock = AsyncMock()
        mock.send_message = AsyncMock(return_value="1234567890.123456")
        return mock

    @pytest.mark.asyncio
    async def test_returns_false_when_no_pending_question(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
    ) -> None:
        """Verify False is returned when no pending question."""
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot)

        result = await handler.submit_answer("nonexistent-task-id", "answer")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_answer_submitted(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
    ) -> None:
        """Verify True is returned when answer is submitted successfully."""
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot)

        task_id = "test-task-id"
        # Manually create Future
        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        handler._answer_futures[task_id] = future
        handler._pending_questions[task_id] = HumanQuestion(
            task_id=task_id,
            question="Test question",
        )

        result = await handler.submit_answer(task_id, "Test answer")

        assert result is True
        assert future.result() == "Test answer"


class TestQuestionHandlerPendingQuestions:
    """QuestionHandler pending questions management tests."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Return mock Redis client."""
        return AsyncMock()

    @pytest.fixture
    def mock_slack_bot(self) -> AsyncMock:
        """Return mock Slack Bot."""
        return AsyncMock()

    def test_has_pending_question_returns_false_when_empty(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
    ) -> None:
        """Verify False is returned when no pending question."""
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot)

        assert handler.has_pending_question("nonexistent-task") is False

    def test_has_pending_question_returns_true_when_exists(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
    ) -> None:
        """Verify True is returned when pending question exists."""
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot)

        task_id = "test-task-id"
        handler._pending_questions[task_id] = HumanQuestion(
            task_id=task_id,
            question="Test question",
        )

        assert handler.has_pending_question(task_id) is True

    def test_get_pending_question_returns_none_when_not_exists(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
    ) -> None:
        """Verify None is returned when pending question does not exist."""
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot)

        assert handler.get_pending_question("nonexistent-task") is None

    def test_get_pending_question_returns_question_when_exists(
        self,
        mock_redis: AsyncMock,
        mock_slack_bot: AsyncMock,
    ) -> None:
        """Verify HumanQuestion is returned when pending question exists."""
        handler = QuestionHandler(redis=mock_redis, slack_bot=mock_slack_bot)

        task_id = "test-task-id"
        question = HumanQuestion(
            task_id=task_id,
            question="Test question",
        )
        handler._pending_questions[task_id] = question

        result = handler.get_pending_question(task_id)

        assert result is not None
        assert result.task_id == task_id
        assert result.question == "Test question"
