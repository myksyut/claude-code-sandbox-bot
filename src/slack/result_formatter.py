"""結果フォーマッターモジュール。

Slackへの結果投稿を処理する。
4000文字以下はテキスト投稿、超過はファイルアップロード。
"""

from typing import Protocol

SLACK_MESSAGE_LIMIT = 4000


class SlackBotProtocol(Protocol):
    """SlackBot依存のProtocol型。"""

    async def send_message(self, channel: str, text: str, thread_ts: str | None = None) -> str: ...

    async def upload_file(
        self, channel: str, content: str, filename: str, thread_ts: str | None = None
    ) -> None: ...


async def post_result(
    slack_bot: SlackBotProtocol,
    result: str,
    channel: str,
    thread_ts: str,
    task_id: str,
) -> None:
    """結果をSlackに投稿する。

    4000文字以下はテキストとして投稿、
    超過はファイルとしてアップロード。

    Args:
        slack_bot: SlackBotProtocolを実装したインスタンス
        result: 投稿する結果テキスト
        channel: 投稿先チャンネルID
        thread_ts: スレッドのタイムスタンプ
        task_id: タスクID(ファイル名生成に使用)
    """
    if len(result) <= SLACK_MESSAGE_LIMIT:
        await slack_bot.send_message(channel, result, thread_ts)
    else:
        filename = f"result-{task_id}.txt"
        await slack_bot.upload_file(channel, result, filename, thread_ts)
