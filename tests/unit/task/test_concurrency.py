"""ConcurrencyController機能の単体テスト。

テスト対象:
- 同時実行数制御(acquire/release)
- キューイング機能
- 上限到達時のキュー追加
"""

import asyncio
import uuid

import pytest
from src.task.concurrency import ConcurrencyController
from src.task.models import Task, TaskStatus


def create_sample_task(suffix: str = "") -> Task:
    """テスト用のサンプルタスクを生成する。"""
    task_id = str(uuid.uuid4())
    return Task(
        id=task_id,
        channel_id="C12345678",
        thread_ts="1234567890.123456",
        user_id="U12345678",
        prompt=f"Test prompt {suffix}",
        repository_url="https://github.com/test/repo",
        status=TaskStatus.PENDING,
        created_at=1234567890.0,
        idempotency_key=f"test-key-{task_id}",
    )


class TestConcurrencyControllerAcquire:
    """acquire機能のテスト。"""

    @pytest.mark.asyncio
    async def test_acquire_returns_true_when_below_limit(self) -> None:
        """同時実行数が上限以下の場合、Trueを返す。"""
        controller = ConcurrencyController(max_concurrent=3)

        result = await controller.acquire()

        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_increments_running_count(self) -> None:
        """acquireは実行中カウントを増加させる。"""
        controller = ConcurrencyController(max_concurrent=3)

        await controller.acquire()

        assert controller.running_count == 1

    @pytest.mark.asyncio
    async def test_acquire_returns_false_when_at_limit(self) -> None:
        """同時実行数が上限に達した場合、Falseを返す。"""
        controller = ConcurrencyController(max_concurrent=2)

        await controller.acquire()
        await controller.acquire()
        result = await controller.acquire()

        assert result is False

    @pytest.mark.asyncio
    async def test_acquire_does_not_exceed_limit(self) -> None:
        """acquireは上限を超えてカウントを増加させない。"""
        controller = ConcurrencyController(max_concurrent=2)

        await controller.acquire()
        await controller.acquire()
        await controller.acquire()

        assert controller.running_count == 2


class TestConcurrencyControllerRelease:
    """release機能のテスト。"""

    @pytest.mark.asyncio
    async def test_release_decrements_running_count(self) -> None:
        """releaseは実行中カウントを減少させる。"""
        controller = ConcurrencyController(max_concurrent=3)

        await controller.acquire()
        await controller.acquire()
        await controller.release()

        assert controller.running_count == 1

    @pytest.mark.asyncio
    async def test_release_returns_none_when_queue_empty(self) -> None:
        """キューが空の場合、Noneを返す。"""
        controller = ConcurrencyController(max_concurrent=3)

        await controller.acquire()
        result = await controller.release()

        assert result is None

    @pytest.mark.asyncio
    async def test_release_returns_queued_task_when_available(self) -> None:
        """キューにタスクがある場合、タスクを返す。"""
        controller = ConcurrencyController(max_concurrent=1)
        task = create_sample_task("queued")

        await controller.acquire()
        await controller.enqueue(task)
        result = await controller.release()

        assert result == task

    @pytest.mark.asyncio
    async def test_release_does_not_go_negative(self) -> None:
        """releaseはカウントを負にしない。"""
        controller = ConcurrencyController(max_concurrent=3)

        await controller.release()

        assert controller.running_count == 0


class TestConcurrencyControllerEnqueue:
    """enqueue機能のテスト。"""

    @pytest.mark.asyncio
    async def test_enqueue_adds_task_to_queue(self) -> None:
        """enqueueはタスクをキューに追加する。"""
        controller = ConcurrencyController(max_concurrent=1)
        task = create_sample_task("enqueue")

        await controller.enqueue(task)

        assert controller.queue_size == 1

    @pytest.mark.asyncio
    async def test_enqueue_maintains_fifo_order(self) -> None:
        """enqueueはFIFO順序を維持する。"""
        controller = ConcurrencyController(max_concurrent=1)
        task1 = create_sample_task("fifo-1")
        task2 = create_sample_task("fifo-2")
        task3 = create_sample_task("fifo-3")

        await controller.acquire()
        await controller.enqueue(task1)
        await controller.enqueue(task2)
        await controller.enqueue(task3)

        result1 = await controller.release()
        result2 = await controller.release()
        result3 = await controller.release()

        assert result1 == task1
        assert result2 == task2
        assert result3 == task3


class TestConcurrencyControllerProperties:
    """プロパティのテスト。"""

    @pytest.mark.asyncio
    async def test_is_at_capacity_returns_true_when_full(self) -> None:
        """同時実行数が上限に達した場合、is_at_capacityはTrueを返す。"""
        controller = ConcurrencyController(max_concurrent=2)

        await controller.acquire()
        await controller.acquire()

        assert controller.is_at_capacity is True

    @pytest.mark.asyncio
    async def test_is_at_capacity_returns_false_when_not_full(self) -> None:
        """同時実行数が上限以下の場合、is_at_capacityはFalseを返す。"""
        controller = ConcurrencyController(max_concurrent=3)

        await controller.acquire()

        assert controller.is_at_capacity is False

    def test_queue_size_returns_zero_initially(self) -> None:
        """初期状態ではqueue_sizeは0を返す。"""
        controller = ConcurrencyController(max_concurrent=3)

        assert controller.queue_size == 0

    def test_running_count_returns_zero_initially(self) -> None:
        """初期状態ではrunning_countは0を返す。"""
        controller = ConcurrencyController(max_concurrent=3)

        assert controller.running_count == 0


class TestConcurrencyControllerConcurrentAccess:
    """並行アクセスのテスト。"""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_respects_limit(self) -> None:
        """並行acquireは上限を尊重する。"""
        controller = ConcurrencyController(max_concurrent=3)
        results = []

        async def acquire_and_record() -> None:
            result = await controller.acquire()
            results.append(result)

        tasks = [acquire_and_record() for _ in range(5)]
        await asyncio.gather(*tasks)

        # 3つだけがTrueで、2つがFalseであることを確認
        assert results.count(True) == 3
        assert results.count(False) == 2
        assert controller.running_count == 3
