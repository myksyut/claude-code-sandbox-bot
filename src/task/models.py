"""
タスク関連の型定義モジュール。

Design Docに定義された型をPydanticモデルとして実装する:
- TaskStatus: タスクの状態を表すEnum
- Task: タスク情報(バリデーション付き)
- SandboxConfig: サンドボックス設定
- TaskMessage: Redis pub/sub用メッセージ
- HumanQuestion: ユーザー質問
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TaskStatus(Enum):
    """タスクの状態を表すEnum。

    タスクのライフサイクルに対応する状態を定義する:
    - PENDING: タスク受信、処理待ち
    - STARTING: コンテナ起動開始
    - CLONING: リポジトリクローン中
    - RUNNING: Claude Code実行中
    - WAITING_USER: ユーザー回答待ち(Human-in-the-loop)
    - COMPLETED: 正常完了
    - FAILED: エラー終了
    - CANCELLED: キャンセル(タイムアウト等)
    """

    PENDING = "pending"
    STARTING = "starting"
    CLONING = "cloning"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """タスク情報(バリデーション付き)。

    Slack経由で受信したタスクの全情報を保持する。
    各フィールドにはDesign Docで定義されたバリデーションを適用する。

    Attributes:
        id: UUID v4形式のタスクID(36文字のハイフン区切り)
        channel_id: Slackチャンネル識別子
        thread_ts: Slackスレッドのタイムスタンプ
        user_id: リクエストを送信したユーザーの識別子
        prompt: ユーザーが入力したプロンプト(1文字以上必須)
        repository_url: GitHubリポジトリURL(https://github.com/で始まる)
        status: タスクの現在の状態
        created_at: タスク作成時のUnixタイムスタンプ
        idempotency_key: 冪等性を保証するための一意キー
    """

    id: str = Field(..., pattern=r"^[0-9a-f-]{36}$")
    channel_id: str
    thread_ts: str
    user_id: str
    prompt: str = Field(..., min_length=1)
    repository_url: str = Field(..., pattern=r"^https://github\.com/.+")
    status: TaskStatus
    created_at: float
    idempotency_key: str


class SandboxConfig(BaseModel):
    """サンドボックス設定。

    ACIコンテナ起動時に使用する設定を定義する。

    Attributes:
        image: Dockerイメージ名(タグを含む)
        cpu: 割り当てるCPUコア数(0より大きい値)
        memory_gb: 割り当てるメモリ量(GB単位、0より大きい値)
        environment: 環境変数の辞書
    """

    image: str
    cpu: float = Field(..., gt=0)
    memory_gb: float = Field(..., gt=0)
    environment: dict[str, str]


class TaskMessage(BaseModel):
    """Redis pub/sub用メッセージ。

    サンドボックスとSlack Bot間の通信に使用するメッセージフォーマット。

    Attributes:
        task_id: 対象タスクのID
        type: メッセージの種類(progress/result/question/error)
        payload: メッセージの本体(キー・値のペア)
    """

    task_id: str
    type: Literal["progress", "result", "question", "error"]
    payload: dict[str, str]


class HumanQuestion(BaseModel):
    """ユーザー質問(Human-in-the-loop用)。

    Claude Codeがユーザーに質問を投げかける際のメッセージフォーマット。

    Attributes:
        task_id: 対象タスクのID
        question: 質問内容
        options: 選択肢のリスト(任意)
        timeout_seconds: 回答待機のタイムアウト秒数(デフォルト600秒=10分)
    """

    task_id: str
    question: str
    options: list[str] | None = None
    timeout_seconds: int = 600
