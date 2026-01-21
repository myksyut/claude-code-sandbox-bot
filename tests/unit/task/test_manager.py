"""TaskManagerImplの単体テスト。

テスト対象:
- タスク投入(submit)機能
- タスク状態取得(get_status)機能
- タスクキャンセル(cancel)機能
- 冪等性キーによる重複実行防止
- 状態遷移(PENDING -> STARTING)
- 並列実行制御(ConcurrencyController統合)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.redis.client import RedisClient
from src.sandbox import SandboxManager
from src.task.concurrency import ConcurrencyController
from src.task.manager import TaskManagerImpl
from src.task.models import Task, TaskStatus


@pytest.fixture
def mock_redis() -> MagicMock:
    """RedisClientのモックを生成する。"""
    redis = MagicMock(spec=RedisClient)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    return redis


@pytest.fixture
def mock_sandbox_manager() -> MagicMock:
    """SandboxManagerのモックを生成する。"""
    manager = MagicMock(spec=SandboxManager)
    return manager


@pytest.fixture
def sample_task() -> Task:
    """テスト用のサンプルタスクを生成する。"""
    return Task(
        id=str(uuid.uuid4()),
        channel_id="C12345678",
        thread_ts="1234567890.123456",
        user_id="U12345678",
        prompt="Explain this code",
        repository_url="https://github.com/test/repo",
        status=TaskStatus.PENDING,
        created_at=1234567890.0,
        idempotency_key=f"channel-thread-{uuid.uuid4()}",
    )


class TestTaskManagerSubmit:
    """submit機能のテスト。"""

    @pytest.mark.asyncio
    async def test_submit_new_task_returns_task_id(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """新規タスクを投入すると、タスクIDが返される。"""
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        result = await manager.submit(sample_task)

        assert result == sample_task.id

    @pytest.mark.asyncio
    async def test_submit_saves_idempotency_key_to_redis(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """submitはidempotency_keyをRedisに保存する。"""
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        await manager.submit(sample_task)

        # idempotency_keyの保存を確認
        calls = mock_redis.set.call_args_list
        idempotency_call = next(
            (c for c in calls if f"idempotency:{sample_task.idempotency_key}" in str(c)),
            None,
        )
        assert idempotency_call is not None

    @pytest.mark.asyncio
    async def test_submit_saves_task_to_redis(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """submitはタスク情報をRedisに保存する。"""
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        await manager.submit(sample_task)

        # タスクの保存を確認
        calls = mock_redis.set.call_args_list
        task_call = next(
            (c for c in calls if f"task:{sample_task.id}" in str(c)),
            None,
        )
        assert task_call is not None

    @pytest.mark.asyncio
    async def test_submit_transitions_status_to_starting(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """submitはタスクの状態をSTARTINGに遷移させる。"""
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        await manager.submit(sample_task)

        # 最終的なタスク状態がSTARTINGで保存されることを確認
        calls = mock_redis.set.call_args_list
        # 最後のtaskへのset呼び出しを確認
        task_calls = [c for c in calls if f"task:{sample_task.id}" in str(c)]
        assert len(task_calls) >= 1
        # 最後の呼び出しでSTARTINGが含まれることを確認
        last_call_args = str(task_calls[-1])
        assert "starting" in last_call_args.lower()


class TestTaskManagerIdempotency:
    """冪等性(重複実行防止)のテスト。"""

    @pytest.mark.asyncio
    async def test_submit_with_existing_idempotency_key_returns_existing_task_id(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """同じidempotency_keyのタスクが存在する場合、既存タスクのIDを返す。"""
        existing_task_id = str(uuid.uuid4())
        mock_redis.get = AsyncMock(return_value=existing_task_id)

        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        result = await manager.submit(sample_task)

        assert result == existing_task_id

    @pytest.mark.asyncio
    async def test_submit_with_existing_idempotency_key_does_not_save_new_task(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """同じidempotency_keyのタスクが存在する場合、新規タスクを保存しない。"""
        existing_task_id = str(uuid.uuid4())
        mock_redis.get = AsyncMock(return_value=existing_task_id)

        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        await manager.submit(sample_task)

        # setは呼ばれないことを確認
        mock_redis.set.assert_not_called()


class TestTaskManagerGetStatus:
    """get_status機能のテスト。"""

    @pytest.mark.asyncio
    async def test_get_status_returns_task_status(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """get_statusはタスクの現在の状態を返す。"""
        task_json = sample_task.model_dump_json()
        mock_redis.get = AsyncMock(return_value=task_json)

        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        result = await manager.get_status(sample_task.id)

        assert result == sample_task.status

    @pytest.mark.asyncio
    async def test_get_status_with_unknown_task_raises_error(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
    ) -> None:
        """存在しないタスクIDの場合、ValueErrorを発生させる。"""
        mock_redis.get = AsyncMock(return_value=None)

        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        with pytest.raises(ValueError, match="Task not found"):
            await manager.get_status("nonexistent-task-id")


class TestTaskManagerCancel:
    """cancel機能のテスト。"""

    @pytest.mark.asyncio
    async def test_cancel_existing_task_returns_true(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """存在するタスクをキャンセルすると、Trueを返す。"""
        task_json = sample_task.model_dump_json()
        mock_redis.get = AsyncMock(return_value=task_json)

        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        result = await manager.cancel(sample_task.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_updates_status_to_cancelled(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """cancelはタスクの状態をCANCELLEDに更新する。"""
        task_json = sample_task.model_dump_json()
        mock_redis.get = AsyncMock(return_value=task_json)

        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        await manager.cancel(sample_task.id)

        # setが呼ばれ、CANCELLEDが含まれることを確認
        mock_redis.set.assert_called()
        call_args = str(mock_redis.set.call_args)
        assert "cancelled" in call_args.lower()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task_returns_false(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
    ) -> None:
        """存在しないタスクをキャンセルすると、Falseを返す。"""
        mock_redis.get = AsyncMock(return_value=None)

        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        result = await manager.cancel("nonexistent-task-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_already_completed_task_returns_false(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """既に完了済みのタスクをキャンセルすると、Falseを返す。"""
        sample_task.status = TaskStatus.COMPLETED
        task_json = sample_task.model_dump_json()
        mock_redis.get = AsyncMock(return_value=task_json)

        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        result = await manager.cancel(sample_task.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_task_returns_false(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """既にキャンセル済みのタスクをキャンセルすると、Falseを返す。"""
        sample_task.status = TaskStatus.CANCELLED
        task_json = sample_task.model_dump_json()
        mock_redis.get = AsyncMock(return_value=task_json)

        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        result = await manager.cancel(sample_task.id)

        assert result is False


class TestTaskManagerConcurrencyControl:
    """並列実行制御(ConcurrencyController統合)のテスト。"""

    @pytest.fixture
    def sample_task(self) -> Task:
        """テスト用のサンプルタスクを生成する。"""
        return Task(
            id=str(uuid.uuid4()),
            channel_id="C12345678",
            thread_ts="1234567890.123456",
            user_id="U12345678",
            prompt="Test prompt",
            repository_url="https://github.com/test/repo",
            status=TaskStatus.PENDING,
            created_at=1234567890.0,
            idempotency_key=f"test-key-{uuid.uuid4()}",
        )

    @pytest.mark.asyncio
    async def test_submit_with_concurrency_control_starts_task_when_below_limit(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """同時実行数が上限以下の場合、タスクが開始される。"""
        controller = ConcurrencyController(max_concurrent=3)
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager, controller)

        await manager.submit(sample_task)

        # タスクがSTARTINGに遷移したことを確認
        calls = mock_redis.set.call_args_list
        task_calls = [c for c in calls if f"task:{sample_task.id}" in str(c)]
        assert len(task_calls) >= 1
        last_call_args = str(task_calls[-1])
        assert "starting" in last_call_args.lower()

    @pytest.mark.asyncio
    async def test_submit_with_concurrency_control_queues_task_when_at_limit(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
    ) -> None:
        """同時実行数が上限に達した場合、タスクがキューに追加される。"""
        controller = ConcurrencyController(max_concurrent=1)
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager, controller)

        # 最初のタスクを投入(スロットを占有)
        task1 = Task(
            id=str(uuid.uuid4()),
            channel_id="C12345678",
            thread_ts="1234567890.123456",
            user_id="U12345678",
            prompt="Task 1",
            repository_url="https://github.com/test/repo",
            status=TaskStatus.PENDING,
            created_at=1234567890.0,
            idempotency_key=f"key-{uuid.uuid4()}",
        )
        await manager.submit(task1)

        # 2番目のタスクを投入(キューに追加)
        task2 = Task(
            id=str(uuid.uuid4()),
            channel_id="C12345678",
            thread_ts="1234567890.123456",
            user_id="U12345678",
            prompt="Task 2",
            repository_url="https://github.com/test/repo",
            status=TaskStatus.PENDING,
            created_at=1234567890.0,
            idempotency_key=f"key-{uuid.uuid4()}",
        )
        await manager.submit(task2)

        # キューサイズが1であることを確認
        assert controller.queue_size == 1

    @pytest.mark.asyncio
    async def test_submit_with_result_returns_queued_true_when_at_limit(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
    ) -> None:
        """submit_with_resultはキュー追加時にqueued=Trueを返す。"""
        controller = ConcurrencyController(max_concurrent=1)
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager, controller)

        # 最初のタスクを投入(スロットを占有)
        task1 = Task(
            id=str(uuid.uuid4()),
            channel_id="C12345678",
            thread_ts="1234567890.123456",
            user_id="U12345678",
            prompt="Task 1",
            repository_url="https://github.com/test/repo",
            status=TaskStatus.PENDING,
            created_at=1234567890.0,
            idempotency_key=f"key-{uuid.uuid4()}",
        )
        result1 = await manager.submit_with_result(task1)
        assert result1.queued is False

        # 2番目のタスクを投入(キューに追加)
        task2 = Task(
            id=str(uuid.uuid4()),
            channel_id="C12345678",
            thread_ts="1234567890.123456",
            user_id="U12345678",
            prompt="Task 2",
            repository_url="https://github.com/test/repo",
            status=TaskStatus.PENDING,
            created_at=1234567890.0,
            idempotency_key=f"key-{uuid.uuid4()}",
        )
        result2 = await manager.submit_with_result(task2)
        assert result2.queued is True

    @pytest.mark.asyncio
    async def test_on_task_complete_starts_queued_task(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
    ) -> None:
        """タスク完了時にキューから次のタスクが開始される。"""
        controller = ConcurrencyController(max_concurrent=1)
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager, controller)

        # 最初のタスクを投入
        task1 = Task(
            id=str(uuid.uuid4()),
            channel_id="C12345678",
            thread_ts="1234567890.123456",
            user_id="U12345678",
            prompt="Task 1",
            repository_url="https://github.com/test/repo",
            status=TaskStatus.PENDING,
            created_at=1234567890.0,
            idempotency_key=f"key-{uuid.uuid4()}",
        )
        await manager.submit(task1)

        # 2番目のタスクを投入(キューに追加)
        task2 = Task(
            id=str(uuid.uuid4()),
            channel_id="C12345678",
            thread_ts="1234567890.123456",
            user_id="U12345678",
            prompt="Task 2",
            repository_url="https://github.com/test/repo",
            status=TaskStatus.PENDING,
            created_at=1234567890.0,
            idempotency_key=f"key-{uuid.uuid4()}",
        )
        await manager.submit(task2)

        # タスク1完了
        next_task = await manager.on_task_complete(task1.id)

        # 次のタスクがtask2であることを確認
        assert next_task is not None
        assert next_task.id == task2.id
        assert next_task.status == TaskStatus.STARTING

    @pytest.mark.asyncio
    async def test_on_task_complete_returns_none_when_queue_empty(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """キューが空の場合、on_task_completeはNoneを返す。"""
        controller = ConcurrencyController(max_concurrent=3)
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager, controller)

        await manager.submit(sample_task)
        next_task = await manager.on_task_complete(sample_task.id)

        assert next_task is None

    @pytest.mark.asyncio
    async def test_on_task_complete_without_controller_returns_none(
        self,
        mock_redis: MagicMock,
        mock_sandbox_manager: MagicMock,
        sample_task: Task,
    ) -> None:
        """ConcurrencyControllerがない場合、on_task_completeはNoneを返す。"""
        manager = TaskManagerImpl(mock_redis, mock_sandbox_manager)

        await manager.submit(sample_task)
        next_task = await manager.on_task_complete(sample_task.id)

        assert next_task is None
