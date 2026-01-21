"""
ACI管理モジュールの単体テスト。

テスト対象:
- SandboxStatus Enum
- Sandbox モデル
- SandboxManager Protocol
- AzureSandboxManagerImpl クラス
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError
from src.sandbox.aci import (
    AzureSandboxManagerImpl,
    Sandbox,
    SandboxCreationError,
    SandboxStatus,
)
from src.task.models import SandboxConfig


class TestSandboxStatus:
    """SandboxStatus Enumのテスト。"""

    def test_sandbox_status_has_all_required_values(self):
        """SandboxStatusが必要な全ての状態を持つこと。"""
        assert SandboxStatus.CREATING.value == "creating"
        assert SandboxStatus.RUNNING.value == "running"
        assert SandboxStatus.TERMINATED.value == "terminated"
        assert SandboxStatus.FAILED.value == "failed"

    def test_sandbox_status_is_enum(self):
        """SandboxStatusがEnumであること。"""
        assert len(SandboxStatus) == 4


class TestSandbox:
    """Sandbox モデルのテスト。"""

    def test_sandbox_creation_with_valid_data(self):
        """有効なデータでSandboxが作成できること。"""
        sandbox = Sandbox(
            task_id="test-task-123",
            container_group_name="sandbox-test1234",
            status=SandboxStatus.RUNNING,
            created_at=time.time(),
        )
        assert sandbox.task_id == "test-task-123"
        assert sandbox.container_group_name == "sandbox-test1234"
        assert sandbox.status == SandboxStatus.RUNNING
        assert sandbox.created_at > 0

    def test_sandbox_requires_task_id(self):
        """task_idが必須であること。"""
        with pytest.raises(ValidationError):
            Sandbox(
                container_group_name="sandbox-test1234",
                status=SandboxStatus.RUNNING,
                created_at=time.time(),
            )

    def test_sandbox_requires_container_group_name(self):
        """container_group_nameが必須であること。"""
        with pytest.raises(ValidationError):
            Sandbox(
                task_id="test-task-123",
                status=SandboxStatus.RUNNING,
                created_at=time.time(),
            )


class TestAzureSandboxManagerImpl:
    """AzureSandboxManagerImpl クラスのテスト。"""

    @pytest.fixture
    def mock_credential(self):
        """Azure認証情報のモック。"""
        return MagicMock()

    @pytest.fixture
    def sandbox_manager(self, mock_credential):
        """テスト用のAzureSandboxManagerImplインスタンス。"""
        return AzureSandboxManagerImpl(
            subscription_id="test-subscription-id",
            resource_group="test-resource-group",
            credential=mock_credential,
        )

    @pytest.fixture
    def sample_config(self):
        """テスト用のSandboxConfig。"""
        return SandboxConfig(
            image="ghcr.io/test/sandbox:latest",
            cpu=1.0,
            memory_gb=2.0,
            environment={"ANTHROPIC_API_KEY": "test-key"},
        )

    @pytest.mark.asyncio
    async def test_create_returns_sandbox_with_running_status(self, sandbox_manager, sample_config):
        """createがRunningステータスのSandboxを返すこと。"""
        with patch.object(
            sandbox_manager, "_create_container_group", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = MagicMock(
                provisioning_state="Succeeded",
                instance_view=MagicMock(state="Running"),
            )

            sandbox = await sandbox_manager.create("test-task-id-1234", sample_config)

            assert sandbox.task_id == "test-task-id-1234"
            assert sandbox.status == SandboxStatus.RUNNING
            assert sandbox.container_group_name == "sandbox-test-tas"

    @pytest.mark.asyncio
    async def test_create_container_group_name_format(self, sandbox_manager, sample_config):
        """コンテナグループ名がsandbox-{task_id[:8]}形式であること。"""
        task_id = "12345678-abcd-efgh-ijkl-mnopqrstuvwx"

        with patch.object(
            sandbox_manager, "_create_container_group", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = MagicMock(
                provisioning_state="Succeeded",
                instance_view=MagicMock(state="Running"),
            )

            sandbox = await sandbox_manager.create(task_id, sample_config)

            assert sandbox.container_group_name == "sandbox-12345678"

    @pytest.mark.asyncio
    async def test_create_raises_error_on_failure(self, sandbox_manager, sample_config):
        """コンテナ起動失敗時にSandboxCreationErrorがraiseされること。"""
        with patch.object(
            sandbox_manager, "_create_container_group", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = Exception("Container creation failed")

            with pytest.raises(SandboxCreationError) as exc_info:
                await sandbox_manager.create("test-task-id", sample_config)

            assert "Container creation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_destroy_calls_delete_container_group(self, sandbox_manager):
        """destroyがコンテナグループ削除を呼び出すこと。"""
        sandbox_manager._sandboxes["test-task-id"] = Sandbox(
            task_id="test-task-id",
            container_group_name="sandbox-test-tas",
            status=SandboxStatus.RUNNING,
            created_at=time.time(),
        )

        with patch.object(
            sandbox_manager, "_delete_container_group", new_callable=AsyncMock
        ) as mock_delete:
            await sandbox_manager.destroy("test-task-id")

            mock_delete.assert_called_once_with("sandbox-test-tas")

    @pytest.mark.asyncio
    async def test_destroy_removes_sandbox_from_tracking(self, sandbox_manager):
        """destroyがトラッキングからサンドボックスを削除すること。"""
        sandbox_manager._sandboxes["test-task-id"] = Sandbox(
            task_id="test-task-id",
            container_group_name="sandbox-test-tas",
            status=SandboxStatus.RUNNING,
            created_at=time.time(),
        )

        with patch.object(sandbox_manager, "_delete_container_group", new_callable=AsyncMock):
            await sandbox_manager.destroy("test-task-id")

            assert "test-task-id" not in sandbox_manager._sandboxes

    @pytest.mark.asyncio
    async def test_destroy_handles_unknown_task_id(self, sandbox_manager):
        """destroyが未知のtask_idでもエラーにならないこと。"""
        with patch.object(sandbox_manager, "_delete_container_group", new_callable=AsyncMock):
            await sandbox_manager.destroy("unknown-task-id")

    @pytest.mark.asyncio
    async def test_get_status_returns_correct_status(self, sandbox_manager):
        """get_statusが正しいステータスを返すこと。"""
        sandbox_manager._sandboxes["test-task-id"] = Sandbox(
            task_id="test-task-id",
            container_group_name="sandbox-test-tas",
            status=SandboxStatus.RUNNING,
            created_at=time.time(),
        )

        status = await sandbox_manager.get_status("test-task-id")

        assert status == SandboxStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_status_returns_terminated_for_unknown(self, sandbox_manager):
        """get_statusが未知のtask_idでTERMINATEDを返すこと。"""
        status = await sandbox_manager.get_status("unknown-task-id")

        assert status == SandboxStatus.TERMINATED


class TestSandboxManagerProtocol:
    """SandboxManager Protocolの準拠テスト。"""

    def test_azure_sandbox_manager_implements_protocol(self, mock_credential):
        """AzureSandboxManagerImplがSandboxManagerプロトコルを実装すること。"""
        mock_credential = MagicMock()
        manager = AzureSandboxManagerImpl(
            subscription_id="test",
            resource_group="test",
            credential=mock_credential,
        )
        # Protocolの必須メソッドが存在することを確認
        assert hasattr(manager, "create")
        assert hasattr(manager, "destroy")
        assert hasattr(manager, "get_status")
        assert callable(manager.create)
        assert callable(manager.destroy)
        assert callable(manager.get_status)

    @pytest.fixture
    def mock_credential(self):
        """Azure認証情報のモック。"""
        return MagicMock()
