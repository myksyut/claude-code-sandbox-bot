"""
Question handler module.

Provides question forwarding and answer redirect for Human-in-the-loop flow.

Design Doc compliance:
- Receive questions via Redis (subscribe question:{task_id})
- Post questions to Slack thread
- Update task status to WAITING_USER
- Return user answers via Redis (publish answer:{task_id})
- Timeout (10 min) cancels task and notifies user
"""

import asyncio
import logging
from typing import Protocol

from src.redis.client import RedisClient
from src.task.models import HumanQuestion, Task, TaskStatus

# Default timeout (seconds)
DEFAULT_QUESTION_TIMEOUT_SECONDS = 600  # 10 minutes

logger = logging.getLogger(__name__)


class SlackBotProtocol(Protocol):
    """Protocol type for SlackBot.

    Defines message sending interface.
    """

    async def send_message(self, channel: str, text: str, thread_ts: str | None = None) -> str:
        """Send a message.

        Args:
            channel: Destination channel ID
            text: Text to send
            thread_ts: Thread timestamp

        Returns:
            Timestamp of sent message
        """
        ...


class QuestionHandlerConfig:
    """QuestionHandler configuration.

    Attributes:
        timeout_seconds: User answer wait timeout (seconds)
    """

    def __init__(self, timeout_seconds: int = DEFAULT_QUESTION_TIMEOUT_SECONDS) -> None:
        """Initialize QuestionHandlerConfig.

        Args:
            timeout_seconds: Timeout in seconds (default: 600 = 10 minutes)
        """
        self.timeout_seconds = timeout_seconds


class QuestionHandler:
    """Question handler.

    Forwards questions from sandbox to Slack and returns user answers to sandbox.

    Attributes:
        _redis: Redis client
        _slack_bot: Slack Bot client
        _config: Configuration
        _pending_questions: Pending questions (task_id -> HumanQuestion)
        _answer_futures: Answer waiting futures (task_id -> Future)
    """

    def __init__(
        self,
        redis: RedisClient,
        slack_bot: SlackBotProtocol,
        config: QuestionHandlerConfig | None = None,
    ) -> None:
        """Initialize QuestionHandler.

        Args:
            redis: Redis client
            slack_bot: Slack Bot client
            config: Configuration (uses defaults if omitted)
        """
        self._redis = redis
        self._slack_bot = slack_bot
        self._config = config or QuestionHandlerConfig()
        self._pending_questions: dict[str, HumanQuestion] = {}
        self._answer_futures: dict[str, asyncio.Future[str]] = {}

        logger.info(
            "QuestionHandler initialized with timeout=%d seconds",
            self._config.timeout_seconds,
        )

    async def handle_question(
        self,
        task: Task,
        question: str,
    ) -> str | None:
        """Process a question and wait for user answer.

        Args:
            task: Target task
            question: Question content

        Returns:
            User's answer. None on timeout.
        """
        task_id = task.id
        channel_id = task.channel_id
        thread_ts = task.thread_ts
        user_id = task.user_id

        logger.info(
            "Handling question for task: task_id=%s, question=%s",
            task_id,
            question[:50] + "..." if len(question) > 50 else question,
        )

        # Create HumanQuestion
        human_question = HumanQuestion(
            task_id=task_id,
            question=question,
            timeout_seconds=self._config.timeout_seconds,
        )
        self._pending_questions[task_id] = human_question

        # Update task status to WAITING_USER
        task.status = TaskStatus.WAITING_USER
        await self._redis.set(
            f"task:{task_id}",
            task.model_dump_json(),
        )

        logger.info("Task status updated to WAITING_USER: task_id=%s", task_id)

        # Post question to Slack thread
        timeout_minutes = self._config.timeout_seconds // 60
        message_text = (
            f"<@{user_id}> Claude Code question:\n\n"
            f"{question}\n\n"
            f"_Please reply in this thread. (Timeout: {timeout_minutes} min)_"
        )

        await self._slack_bot.send_message(
            channel=channel_id,
            text=message_text,
            thread_ts=thread_ts,
        )

        logger.info("Question posted to Slack: task_id=%s, channel=%s", task_id, channel_id)

        # Wait for answer
        answer_future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        self._answer_futures[task_id] = answer_future

        try:
            answer = await asyncio.wait_for(
                answer_future,
                timeout=self._config.timeout_seconds,
            )
            logger.info("Received answer for task: task_id=%s", task_id)
            return answer

        except TimeoutError:
            logger.warning("Question timed out: task_id=%s", task_id)

            # Update task to CANCELLED
            task.status = TaskStatus.CANCELLED
            await self._redis.set(
                f"task:{task_id}",
                task.model_dump_json(),
            )

            # Notify user
            timeout_message = (
                f"<@{user_id}> Timeout. Task cancelled due to no response to the question."
            )
            await self._slack_bot.send_message(
                channel=channel_id,
                text=timeout_message,
                thread_ts=thread_ts,
            )

            return None

        finally:
            # Cleanup
            self._pending_questions.pop(task_id, None)
            self._answer_futures.pop(task_id, None)

    async def submit_answer(self, task_id: str, answer: str) -> bool:
        """Submit user's answer.

        Args:
            task_id: Task ID
            answer: User's answer

        Returns:
            True if answer was submitted successfully, False if no pending question
        """
        logger.info("Submitting answer for task: task_id=%s", task_id)

        # Set answer if there's a waiting Future
        future = self._answer_futures.get(task_id)
        if future is not None and not future.done():
            future.set_result(answer)
            logger.info("Answer set for task: task_id=%s", task_id)
            return True

        logger.warning("No pending question for task: task_id=%s", task_id)
        return False

    def has_pending_question(self, task_id: str) -> bool:
        """Check if task has a pending question.

        Args:
            task_id: Task ID

        Returns:
            True if there's a pending question
        """
        return task_id in self._pending_questions

    def get_pending_question(self, task_id: str) -> HumanQuestion | None:
        """Get pending question for task.

        Args:
            task_id: Task ID

        Returns:
            Pending HumanQuestion. None if not found.
        """
        return self._pending_questions.get(task_id)


async def handle_question_from_redis(
    redis: RedisClient,
    question_handler: QuestionHandler,
    task_id: str,
) -> None:
    """Handle question received via Redis.

    Receives questions from sandbox's ask_user.py,
    forwards to Slack, and publishes answer to Redis.

    Args:
        redis: Redis client
        question_handler: Question handler
        task_id: Task ID
    """
    question_channel = f"question:{task_id}"
    answer_channel = f"answer:{task_id}"

    logger.info("Starting question handler for task: task_id=%s", task_id)

    async def on_question(question: str) -> None:
        """Callback when question is received."""
        logger.info(
            "Received question from sandbox: task_id=%s, question=%s",
            task_id,
            question[:50] + "..." if len(question) > 50 else question,
        )

        # Get task info
        task_json = await redis.get(f"task:{task_id}")
        if task_json is None:
            logger.error("Task not found: task_id=%s", task_id)
            return

        task = Task.model_validate_json(task_json)

        # Process question and wait for answer
        answer = await question_handler.handle_question(task, question)

        if answer is not None:
            # Return answer to sandbox via Redis
            await redis.publish(answer_channel, answer)
            logger.info("Published answer to Redis: task_id=%s", task_id)

            # Update task status back to RUNNING
            task.status = TaskStatus.RUNNING
            await redis.set(
                f"task:{task_id}",
                task.model_dump_json(),
            )
            logger.info("Task status updated to RUNNING: task_id=%s", task_id)

    # Subscribe to question channel
    await redis.subscribe(question_channel, on_question)
