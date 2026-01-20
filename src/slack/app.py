"""
SlackBot実装モジュール。

Design Docで定義されたSlackBotプロトコルの実装を提供する。
- Protocol型でインターフェースを定義
- AsyncAppを使用し、全ハンドラをasync defで統一
- 依存性注入パターン(外部依存は引数で注入)
"""

import logging
from typing import Protocol

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler as SocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)


class SlackBot(Protocol):
    """SlackBotのインターフェース定義(Design Doc準拠)。

    Slack APIとの通信を抽象化するプロトコル型。
    具体的な実装はSlackBotImplで提供される。
    """

    async def start(self) -> None:
        """Socket Mode接続を開始する。"""
        ...

    async def send_message(self, channel: str, text: str, thread_ts: str | None = None) -> str:
        """メッセージを送信する。

        Args:
            channel: 送信先チャンネルID
            text: 送信するテキスト
            thread_ts: スレッドのタイムスタンプ(スレッド返信の場合)

        Returns:
            送信されたメッセージのタイムスタンプ
        """
        ...

    async def update_message(self, channel: str, ts: str, text: str) -> None:
        """既存のメッセージを更新する。

        Args:
            channel: チャンネルID
            ts: 更新対象メッセージのタイムスタンプ
            text: 新しいテキスト
        """
        ...

    async def upload_file(
        self, channel: str, content: str, filename: str, thread_ts: str | None = None
    ) -> None:
        """ファイルをアップロードする。

        Args:
            channel: アップロード先チャンネルID
            content: ファイルの内容
            filename: ファイル名
            thread_ts: スレッドのタイムスタンプ(スレッド内にアップロードする場合)
        """
        ...


class SlackBotImpl:
    """SlackBotプロトコルの具体的な実装。

    slack-boltのAsyncAppとAsyncWebClientを使用してSlack APIと通信する。
    Socket Modeで接続し、リアルタイムでイベントを受信する。

    Attributes:
        _app: slack-boltのAsyncAppインスタンス
        _web_client: Slack Web APIクライアント
        _app_token: Socket Mode用のアプリトークン
        _handler: Socket Modeハンドラ
    """

    def __init__(
        self,
        app: AsyncApp,
        web_client: AsyncWebClient,
        app_token: str | None = None,
    ) -> None:
        """SlackBotImplを初期化する。

        Args:
            app: slack-boltのAsyncAppインスタンス
            web_client: Slack Web APIクライアント
            app_token: Socket Mode用のアプリトークン(xapp-で始まる)
        """
        self._app = app
        self._web_client = web_client
        self._app_token = app_token
        self._handler: SocketModeHandler | None = None

    async def start(self) -> None:
        """Socket Mode接続を開始する。

        Socket Modeを使用してSlackとのリアルタイム接続を確立する。
        この接続はWebSocket経由で維持され、外部公開URLを必要としない。

        Raises:
            ValueError: app_tokenが設定されていない場合
        """
        if self._app_token is None:
            msg = "app_token is required for Socket Mode"
            raise ValueError(msg)

        self._handler = SocketModeHandler(app=self._app, app_token=self._app_token)
        logger.info("Starting Socket Mode connection...")
        await self._handler.start_async()
        logger.info("Socket Mode connection started")

    async def send_message(self, channel: str, text: str, thread_ts: str | None = None) -> str:
        """メッセージを送信する。

        Args:
            channel: 送信先チャンネルID
            text: 送信するテキスト
            thread_ts: スレッドのタイムスタンプ(スレッド返信の場合)

        Returns:
            送信されたメッセージのタイムスタンプ
        """
        response = await self._web_client.chat_postMessage(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
        )
        ts: str = response["ts"]
        return ts

    async def update_message(self, channel: str, ts: str, text: str) -> None:
        """既存のメッセージを更新する。

        Args:
            channel: チャンネルID
            ts: 更新対象メッセージのタイムスタンプ
            text: 新しいテキスト
        """
        await self._web_client.chat_update(
            channel=channel,
            ts=ts,
            text=text,
        )

    async def upload_file(
        self, channel: str, content: str, filename: str, thread_ts: str | None = None
    ) -> None:
        """ファイルをアップロードする。

        Args:
            channel: アップロード先チャンネルID
            content: ファイルの内容
            filename: ファイル名
            thread_ts: スレッドのタイムスタンプ(スレッド内にアップロードする場合)
        """
        await self._web_client.files_upload_v2(
            channel=channel,
            content=content,
            filename=filename,
            thread_ts=thread_ts,
        )
