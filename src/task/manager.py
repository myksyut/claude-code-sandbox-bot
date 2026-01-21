"""
タスクマネージャーモジュール。

Design Doc準拠のインターフェースを実装:
- Protocol型でTaskManagerインターフェース定義
- TaskManagerImplクラスで実装
- タスク投入(submit)機能
- タスク状態取得(get_status)機能
- タスクキャンセル(cancel)機能
- 冪等性キーによる重複実行防止

依存性注入パターン:
- RedisClient: 状態管理と冪等性キー保存
- SandboxManager: サンドボックス起動(Phase 3で使用)
"""

import logging
from typing import TYPE_CHECKING, Protocol

from src.redis.client import RedisClient
from src.task.models import Task, TaskStatus

if TYPE_CHECKING:
    from src.sandbox.aci import SandboxManager

logger = logging.getLogger(__name__)


# Terminal states (cannot be cancelled)
TERMINAL_STATES = frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED})


class TaskManager(Protocol):
    """タスクマネージャーのプロトコル定義。

    Design Docで定義されたインターフェース:
    - submit: タスクを投入
    - get_status: タスクの状態を取得
    - cancel: タスクをキャンセル
    """

    async def submit(self, task: Task) -> str:
        """タスクを投入する。

        Args:
            task: 投入するタスク

        Returns:
            タスクID。冪等性キーが既存の場合は既存タスクのIDを返す。
        """
        ...

    async def get_status(self, task_id: str) -> TaskStatus:
        """タスクの状態を取得する。

        Args:
            task_id: タスクID

        Returns:
            タスクの現在の状態

        Raises:
            ValueError: タスクが存在しない場合
        """
        ...

    async def cancel(self, task_id: str) -> bool:
        """タスクをキャンセルする。

        Args:
            task_id: タスクID

        Returns:
            キャンセルに成功した場合はTrue、
            タスクが存在しないか終端状態の場合はFalse
        """
        ...


class TaskManagerImpl:
    """TaskManagerの実装クラス。

    機能:
    - 冪等性キーによる重複実行防止
    - Redisへのタスク状態保存
    - 状態遷移管理(PENDING -> STARTING)

    Attributes:
        _redis: Redisクライアント
        _sandbox_manager: サンドボックスマネージャー(Phase 3で使用)
    """

    def __init__(self, redis: RedisClient, sandbox_manager: "SandboxManager") -> None:
        """TaskManagerImplを初期化する。

        Args:
            redis: Redisクライアント(状態管理・冪等性キー)
            sandbox_manager: サンドボックスマネージャー(Phase 3で使用)
        """
        self._redis = redis
        self._sandbox_manager = sandbox_manager

        logger.info("TaskManagerImpl initialized")

    async def submit(self, task: Task) -> str:
        """タスクを投入する。

        データ契約(Design Doc準拠):
        - task_idは一意
        - idempotency_keyが同じ場合、既存タスクのIDを返す

        状態遷移:
        - PENDING -> STARTING

        Args:
            task: 投入するタスク

        Returns:
            タスクID。冪等性キーが既存の場合は既存タスクのIDを返す。
        """
        logger.info(
            "Submitting task: id=%s, idempotency_key=%s",
            task.id,
            task.idempotency_key,
        )

        # 1. idempotency_keyで既存タスク検索
        existing_task_id = await self._redis.get(f"idempotency:{task.idempotency_key}")
        if existing_task_id is not None:
            logger.info(
                "Task with same idempotency_key already exists: %s -> %s",
                task.idempotency_key,
                existing_task_id,
            )
            return existing_task_id

        # 2. 新規タスク登録
        await self._redis.set(
            f"idempotency:{task.idempotency_key}",
            task.id,
        )
        await self._redis.set(
            f"task:{task.id}",
            task.model_dump_json(),
        )

        logger.info(
            "Task registered: id=%s, status=%s",
            task.id,
            task.status.value,
        )

        # 3. サンドボックス起動準備(Phase 2ではステータス遷移のみ)
        task.status = TaskStatus.STARTING
        await self._redis.set(
            f"task:{task.id}",
            task.model_dump_json(),
        )

        logger.info(
            "Task status transitioned: id=%s, status=%s",
            task.id,
            task.status.value,
        )

        return task.id

    async def get_status(self, task_id: str) -> TaskStatus:
        """タスクの状態を取得する。

        Args:
            task_id: タスクID

        Returns:
            タスクの現在の状態

        Raises:
            ValueError: タスクが存在しない場合
        """
        logger.debug("Getting status for task: %s", task_id)

        task_json = await self._redis.get(f"task:{task_id}")
        if task_json is None:
            logger.warning("Task not found: %s", task_id)
            raise ValueError(f"Task not found: {task_id}")

        task = Task.model_validate_json(task_json)
        logger.debug("Task status: id=%s, status=%s", task_id, task.status.value)

        return task.status

    async def cancel(self, task_id: str) -> bool:
        """タスクをキャンセルする。

        終端状態(COMPLETED, FAILED, CANCELLED)のタスクは
        キャンセルできない。

        Args:
            task_id: タスクID

        Returns:
            キャンセルに成功した場合はTrue、
            タスクが存在しないか終端状態の場合はFalse
        """
        logger.info("Cancelling task: %s", task_id)

        task_json = await self._redis.get(f"task:{task_id}")
        if task_json is None:
            logger.warning("Cannot cancel: task not found: %s", task_id)
            return False

        task = Task.model_validate_json(task_json)

        # 終端状態はキャンセル不可
        if task.status in TERMINAL_STATES:
            logger.warning(
                "Cannot cancel: task in terminal state: id=%s, status=%s",
                task_id,
                task.status.value,
            )
            return False

        # 状態をCANCELLEDに更新
        task.status = TaskStatus.CANCELLED
        await self._redis.set(
            f"task:{task.id}",
            task.model_dump_json(),
        )

        logger.info("Task cancelled: %s", task_id)

        return True
