"""
並列実行制御モジュール。

Design Doc準拠のインターフェースを実装:
- 同時実行数をMAX_CONCURRENT_TASKSで制限
- 上限到達時はキューに追加
- 既存タスク完了後にキューのタスクを実行
"""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.task.models import Task

logger = logging.getLogger(__name__)


class ConcurrencyController:
    """並列実行制御クラス。

    機能:
    - 同時実行数を設定された上限で制限
    - 上限到達時にタスクをキューイング
    - スロット解放時にキューからタスクを取り出し

    Attributes:
        _max_concurrent: 最大同時実行数
        _running_count: 現在の実行中タスク数
        _queue: 待機中タスクのキュー
        _lock: 並行アクセス制御用ロック
    """

    def __init__(self, max_concurrent: int) -> None:
        """ConcurrencyControllerを初期化する。

        Args:
            max_concurrent: 最大同時実行数
        """
        self._max_concurrent = max_concurrent
        self._running_count = 0
        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._lock = asyncio.Lock()

        logger.info(
            "ConcurrencyController initialized with max_concurrent=%d",
            max_concurrent,
        )

    @property
    def running_count(self) -> int:
        """現在の実行中タスク数を返す。"""
        return self._running_count

    @property
    def queue_size(self) -> int:
        """キューにあるタスク数を返す。"""
        return self._queue.qsize()

    @property
    def is_at_capacity(self) -> bool:
        """同時実行数が上限に達しているかどうかを返す。"""
        return self._running_count >= self._max_concurrent

    async def acquire(self) -> bool:
        """実行スロットを取得する。

        Returns:
            取得できた場合はTrue、上限に達している場合はFalse。
            Falseの場合はenqueueでタスクをキューに追加すること。
        """
        async with self._lock:
            if self._running_count < self._max_concurrent:
                self._running_count += 1
                logger.debug(
                    "Acquired execution slot: running=%d/%d",
                    self._running_count,
                    self._max_concurrent,
                )
                return True

            logger.debug(
                "At capacity: running=%d/%d, cannot acquire",
                self._running_count,
                self._max_concurrent,
            )
            return False

    async def release(self) -> "Task | None":
        """実行スロットを解放する。

        Returns:
            キューにタスクがあればそのタスクを返す。
            なければNoneを返す。
        """
        async with self._lock:
            if self._running_count > 0:
                self._running_count -= 1

            logger.debug(
                "Released execution slot: running=%d/%d",
                self._running_count,
                self._max_concurrent,
            )

            # キューにタスクがあれば取り出す
            if not self._queue.empty():
                try:
                    task = self._queue.get_nowait()
                    self._running_count += 1  # 新しいタスクのためにスロットを確保
                    logger.info(
                        "Dequeued task %s: running=%d/%d, queue=%d",
                        task.id,
                        self._running_count,
                        self._max_concurrent,
                        self._queue.qsize(),
                    )
                    return task
                except asyncio.QueueEmpty:
                    pass

            return None

    async def enqueue(self, task: "Task") -> None:
        """タスクをキューに追加する。

        Args:
            task: キューに追加するタスク
        """
        await self._queue.put(task)
        logger.info(
            "Enqueued task %s: queue_size=%d",
            task.id,
            self._queue.qsize(),
        )
