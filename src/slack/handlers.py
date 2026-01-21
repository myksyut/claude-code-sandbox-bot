"""
Slackイベントハンドラモジュール。

app_mentionイベントとスラッシュコマンドのハンドラを提供する。
この段階ではシンプルな実装とし、後続フェーズでタスク管理との連携を追加する。
"""

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypedDict

from src.task.models import Task, TaskStatus


class TaskManagerProtocol(Protocol):
    """TaskManager用のProtocol型。

    タスク管理機能のインターフェースを定義する。
    具体的な実装は依存性注入で渡される。
    """

    async def submit_task(self, task: Task) -> None:
        """タスクを投入する。

        Args:
            task: 投入するタスク
        """
        ...


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


def create_task(
    task_id: str,
    channel_id: str,
    thread_ts: str,
    user_id: str,
    prompt: str,
    repository_url: str,
    idempotency_key: str | None = None,
) -> Task:
    """Taskインスタンスを生成する。

    Args:
        task_id: UUID v4形式のタスクID
        channel_id: Slackチャンネル識別子
        thread_ts: Slackスレッドのタイムスタンプ
        user_id: リクエストを送信したユーザーの識別子
        prompt: ユーザーが入力したプロンプト
        repository_url: GitHubリポジトリURL
        idempotency_key: 冪等性を保証するための一意キー(省略時はtask_idを使用)

    Returns:
        作成されたTaskインスタンス(status=PENDING)
    """
    return Task(
        id=task_id,
        channel_id=channel_id,
        thread_ts=thread_ts,
        user_id=user_id,
        prompt=prompt,
        repository_url=repository_url,
        status=TaskStatus.PENDING,
        created_at=time.time(),
        idempotency_key=idempotency_key or task_id,
    )


# 型エイリアス
SayFunction = Callable[..., Awaitable[dict[str, Any]]]
AckFunction = Callable[[], Awaitable[None]]
RespondFunction = Callable[[str], Awaitable[None]]


async def handle_app_mention(
    event: dict[str, Any],
    say: SayFunction,
    task_manager: TaskManagerProtocol | None = None,
) -> TaskResult | None:
    """app_mentionイベントを処理する。

    ボットがメンションされた時に呼び出される。
    GitHub URLが含まれている場合はタスクIDを生成し「起動中...」メッセージを返す。
    URLがない場合はエラーメッセージを返す。
    TaskManagerが渡された場合はタスクを投入する。

    Args:
        event: Slackから受信したイベントデータ
        say: メッセージ送信用の関数
        task_manager: タスク管理機能(オプショナル、後方互換性のため)

    Returns:
        TaskResult: タスク処理結果(task_id, repository_url)。
        エラー時はNone。
    """
    thread_ts = event.get("ts", "")
    channel_id = event.get("channel", "")
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
    await say(
        text=f"<@{user_id}> 起動中... (タスクID: {task_id})",
        thread_ts=thread_ts,
    )

    # TaskManagerが渡された場合はタスクを投入
    if task_manager is not None:
        # プロンプトはテキストからボットメンションを除いた部分
        prompt = text.strip()
        task = create_task(
            task_id=task_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            user_id=user_id,
            prompt=prompt,
            repository_url=repository_url,
        )
        await task_manager.submit_task(task)

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
