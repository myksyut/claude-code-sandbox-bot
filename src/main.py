"""
アプリケーションのエントリーポイント。

Slack BotをSocket Modeで起動する。
環境変数の読み込み、AsyncAppの作成、ハンドラの登録、Socket Mode接続を行う。
"""

import asyncio
import logging

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from src.config import get_settings
from src.slack import SlackBotImpl, handle_app_mention, handle_claude_command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    """アプリケーションのエントリーポイント。

    以下の処理を順次実行する:
    1. 環境変数から設定を読み込み
    2. AsyncAppを作成
    3. イベントハンドラとコマンドハンドラを登録
    4. AsyncWebClientを作成
    5. SlackBotImplを作成してSocket Modeで起動
    """
    settings = get_settings()

    # AsyncAppの作成
    app = AsyncApp(token=settings.slack_bot_token)

    # ハンドラの登録
    app.event("app_mention")(handle_app_mention)
    app.command("/claude")(handle_claude_command)

    # AsyncWebClientの作成
    client = AsyncWebClient(token=settings.slack_bot_token)

    # SlackBotの作成と起動
    bot = SlackBotImpl(
        app=app,
        web_client=client,
        app_token=settings.slack_app_token,
    )

    logger.info("Starting Slack Bot...")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
