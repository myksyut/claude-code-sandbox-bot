"""
Slackイベントハンドラモジュール。

app_mentionイベントとスラッシュコマンドのハンドラを提供する。
この段階ではシンプルな実装とし、後続フェーズでタスク管理との連携を追加する。
"""

import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

# GitHub URL抽出用の正規表現
# URLパスに使われる文字(英数字、ハイフン、アンダースコア、スラッシュ、ドット)に対応
GITHUB_URL_PATTERN = re.compile(r"https://github\.com/[^\s]+")


class TaskResult(TypedDict):
    """タスク処理結果の型定義。"""

    task_id: str
    repository_url: str


def extract_github_url(text: str) -> str | None:
    """テキストからGitHub URLを抽出する。

    Args:
        text: 検索対象のテキスト(ボットメンションを含む可能性あり)

    Returns:
        抽出されたGitHub URL。見つからない場合はNone。
        複数URLがある場合は最初のURLを返す。
    """
    match = GITHUB_URL_PATTERN.search(text)
    if match:
        return match.group(0)
    return None


def generate_task_id() -> str:
    """UUID v4形式のタスクIDを生成する。

    Returns:
        UUID v4形式の文字列(例: "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")
    """
    return str(uuid.uuid4())


# 型エイリアス
SayFunction = Callable[..., Awaitable[dict[str, Any]]]
AckFunction = Callable[[], Awaitable[None]]
RespondFunction = Callable[[str], Awaitable[None]]


async def handle_app_mention(
    event: dict[str, Any],
    say: SayFunction,
) -> TaskResult | None:
    """app_mentionイベントを処理する。

    ボットがメンションされた時に呼び出される。
    GitHub URLが含まれている場合はタスクIDを生成し「起動中...」メッセージを返す。
    URLがない場合はエラーメッセージを返す。

    Args:
        event: Slackから受信したイベントデータ
        say: メッセージ送信用の関数

    Returns:
        TaskResult: タスク処理結果(task_id, repository_url)。
        エラー時はNone。
    """
    thread_ts = event.get("ts", "")
    user_id = event.get("user", "")
    text = event.get("text", "")

    logger.info(
        "Received app_mention event",
        extra={"user_id": user_id, "thread_ts": thread_ts},
    )

    # GitHub URLを抽出
    repository_url = extract_github_url(text)

    if repository_url is None:
        # URLがない場合はエラーメッセージを返す
        logger.warning(
            "No GitHub URL found in app_mention",
            extra={"user_id": user_id, "text": text},
        )
        await say(
            text=f"<@{user_id}> リポジトリURLを指定してください",
            thread_ts=thread_ts,
        )
        return None

    # タスクIDを生成
    task_id = generate_task_id()

    logger.info(
        "Task created from app_mention",
        extra={
            "task_id": task_id,
            "user_id": user_id,
            "repository_url": repository_url,
        },
    )

    # 1秒以内に応答するための即時メッセージ
    # TODO: 後続フェーズでタスク管理との連携を追加
    await say(
        text=f"<@{user_id}> 起動中... (タスクID: {task_id})",
        thread_ts=thread_ts,
    )

    return TaskResult(task_id=task_id, repository_url=repository_url)


async def handle_claude_command(
    command: dict[str, Any],
    ack: AckFunction,
    respond: RespondFunction,
) -> TaskResult | None:
    """スラッシュコマンド /claude を処理する。

    即座にackを返し、処理を開始する。
    GitHub URLが含まれている場合はタスクIDを生成し「起動中...」メッセージを返す。
    URLがない場合はエラーメッセージを返す。

    Args:
        command: スラッシュコマンドのデータ
        ack: 即座に応答するためのack関数
        respond: 後続のレスポンス送信用関数

    Returns:
        TaskResult: タスク処理結果(task_id, repository_url)。
        エラー時はNone。
    """
    # 即座にackを返す(3秒以内の応答要件)
    await ack()

    user_id = command.get("user_id", "")
    command_text = command.get("text", "")

    logger.info(
        "Received /claude command",
        extra={"user_id": user_id, "command_text": command_text},
    )

    # GitHub URLを抽出
    repository_url = extract_github_url(command_text)

    if repository_url is None:
        # URLがない場合はエラーメッセージを返す
        logger.warning(
            "No GitHub URL found in /claude command",
            extra={"user_id": user_id, "command_text": command_text},
        )
        await respond(f"<@{user_id}> リポジトリURLを指定してください")
        return None

    # タスクIDを生成
    task_id = generate_task_id()

    logger.info(
        "Task created from /claude command",
        extra={
            "task_id": task_id,
            "user_id": user_id,
            "repository_url": repository_url,
        },
    )

    # 起動中メッセージを送信
    # TODO: 後続フェーズでタスク管理との連携を追加
    await respond(f"<@{user_id}> 起動中... (タスクID: {task_id})")

    return TaskResult(task_id=task_id, repository_url=repository_url)
