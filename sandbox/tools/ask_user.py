#!/usr/bin/env python3
"""
ask_user.py - Sandbox script to send questions to users.

Design Doc Human-in-the-loop flow implementation:
1. Receive question content via argument
2. Send question to Slack Bot via Redis (publish)
3. Wait for answer via Redis subscription
4. Output answer to stdout
5. Raise exception on timeout (10 minutes)
"""

import asyncio
import logging
import os
import sys

import redis.asyncio as redis

# Timeout setting (seconds)
DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AskUserTimeoutError(Exception):
    """Timeout error waiting for user answer."""

    pass


async def ask_user(question: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Send question to user and wait for answer.

    Args:
        question: Question content
        timeout_seconds: Timeout in seconds (default: 600 = 10 minutes)

    Returns:
        User's answer

    Raises:
        AskUserTimeoutError: On timeout
        ValueError: If environment variables are not set
        ConnectionError: Redis connection error
    """
    # Get environment variables
    task_id = os.environ.get("TASK_ID")
    redis_url = os.environ.get("REDIS_URL")

    if not task_id:
        raise ValueError("TASK_ID environment variable is required")
    if not redis_url:
        raise ValueError("REDIS_URL environment variable is required")

    logger.info("Connecting to Redis: %s", redis_url)

    # Redis connection
    client = redis.from_url(redis_url)

    try:
        # Create PubSub instance and subscribe to answer channel
        pubsub = client.pubsub()
        answer_channel = f"answer:{task_id}"
        await pubsub.subscribe(answer_channel)

        logger.info("Subscribed to answer channel: %s", answer_channel)

        # Send question
        question_channel = f"question:{task_id}"
        await client.publish(question_channel, question)

        logger.info("Published question to channel: %s", question_channel)

        # Wait for answer with timeout
        async def wait_for_answer() -> str:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    return data
            # Should not reach here
            raise RuntimeError("Unexpected end of message stream")

        try:
            answer = await asyncio.wait_for(
                wait_for_answer(),
                timeout=timeout_seconds,
            )
            logger.info("Received answer")
            return answer
        except TimeoutError as e:
            logger.error("Timeout waiting for user answer after %d seconds", timeout_seconds)
            raise AskUserTimeoutError(
                f"Timeout waiting for user answer after {timeout_seconds} seconds"
            ) from e

    finally:
        # Cleanup
        await pubsub.unsubscribe(answer_channel)
        await client.close()
        logger.info("Redis connection closed")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python ask_user.py <question>", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    try:
        answer = asyncio.run(ask_user(question))
        # Output answer to stdout (Claude Code reads this)
        print(answer)
    except AskUserTimeoutError:
        print("Error: Timeout waiting for user answer", file=sys.stderr)
        sys.exit(2)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ConnectionError as e:
        print(f"Error: Redis connection failed: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
