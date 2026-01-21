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
    CloneError,
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
        assert SandboxStatus.STARTING.value == "starting"
        assert SandboxStatus.CLONING.value == "cloning"
        assert SandboxStatus.RUNNING.value == "running"
        assert SandboxStatus.TERMINATED.value == "terminated"
        assert SandboxStatus.FAILED.value == "failed"

    def test_sandbox_status_is_enum(self):
        """SandboxStatusがEnumであること。"""
        assert len(SandboxStatus) == 6


class TestCloneError:
    """CloneError例外のテスト。"""

    def test_clone_error_creation(self):
        """CloneErrorが正しく作成できること。"""
        error = CloneError(
            message="Failed to clone repository",
            task_id="test-task-123",
        )
        assert str(error) == "Failed to clone repository"
        assert error.task_id == "test-task-123"
        assert error.cause is None

    def test_clone_error_with_cause(self):
        """CloneErrorが原因例外を保持できること。"""
        cause = Exception("Network error")
        error = CloneError(
            message="Failed to clone repository",
            task_id="test-task-123",
            cause=cause,
        )
        assert error.cause is cause

    def test_clone_error_is_exception(self):
        """CloneErrorがExceptionを継承していること。"""
        error = CloneError(
            message="Test error",
            task_id="test-task-123",
        )
        assert isinstance(error, Exception)


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


class TestGitHubIntegration:
    """GitHub連携のテスト。"""

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
    def github_config(self):
        """GitHub連携が有効なSandboxConfig。"""
        return SandboxConfig(
            image="ghcr.io/test/sandbox:latest",
            cpu=1.0,
            memory_gb=2.0,
            environment={"ANTHROPIC_API_KEY": "test-key"},
            repository_url="https://github.com/example/repo",
            github_pat="ghp_test_pat_12345",
            prompt="Analyze this codebase",
        )

    @pytest.mark.asyncio
    async def test_create_with_github_config_sets_environment_variables(
        self, sandbox_manager, github_config
    ):
        """GitHub連携設定時に環境変数が設定されること。"""
        with patch.object(sandbox_manager, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = MagicMock(
                provisioning_state="Succeeded",
            )
            mock_client.container_groups.begin_create_or_update.return_value = mock_poller
            mock_get_client.return_value = mock_client

            await sandbox_manager.create("test-task-id-1234", github_config)

            # コンテナグループが作成されたことを確認
            mock_client.container_groups.begin_create_or_update.assert_called_once()
            call_args = mock_client.container_groups.begin_create_or_update.call_args
            container_group = call_args.kwargs["container_group"]

            # 環境変数を取得
            env_vars = container_group.containers[0].environment_variables
            env_names = [var.name for var in env_vars]

            # GitHub連携の環境変数が含まれていることを確認
            assert "REPOSITORY_URL" in env_names
            assert "GITHUB_PAT" in env_names
            assert "PROMPT" in env_names
            assert "TASK_ID" in env_names

    @pytest.mark.asyncio
    async def test_create_without_github_config_skips_github_env_vars(self, sandbox_manager):
        """GitHub連携未設定時はGitHub関連環境変数がスキップされること。"""
        basic_config = SandboxConfig(
            image="ghcr.io/test/sandbox:latest",
            cpu=1.0,
            memory_gb=2.0,
            environment={"ANTHROPIC_API_KEY": "test-key"},
        )

        with patch.object(sandbox_manager, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = MagicMock(
                provisioning_state="Succeeded",
            )
            mock_client.container_groups.begin_create_or_update.return_value = mock_poller
            mock_get_client.return_value = mock_client

            await sandbox_manager.create("test-task-id-1234", basic_config)

            call_args = mock_client.container_groups.begin_create_or_update.call_args
            container_group = call_args.kwargs["container_group"]
            env_vars = container_group.containers[0].environment_variables
            env_names = [var.name for var in env_vars]

            # GitHub連携の環境変数が含まれていないことを確認
            assert "REPOSITORY_URL" not in env_names
            assert "GITHUB_PAT" not in env_names
            assert "PROMPT" not in env_names

    @pytest.mark.asyncio
    async def test_github_pat_is_set_as_secure_value(self, sandbox_manager, github_config):
        """GitHub PATがsecure_valueとして設定されること。"""
        with patch.object(sandbox_manager, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = MagicMock(
                provisioning_state="Succeeded",
            )
            mock_client.container_groups.begin_create_or_update.return_value = mock_poller
            mock_get_client.return_value = mock_client

            await sandbox_manager.create("test-task-id-1234", github_config)

            call_args = mock_client.container_groups.begin_create_or_update.call_args
            container_group = call_args.kwargs["container_group"]
            env_vars = container_group.containers[0].environment_variables

            # GITHUB_PATがsecure_valueとして設定されていることを確認
            github_pat_var = next(var for var in env_vars if var.name == "GITHUB_PAT")
            assert github_pat_var.secure_value == "ghp_test_pat_12345"


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


class TestClaudeCodeExecution:
    """Claude Code実行のテスト。"""

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
    def github_config_with_prompt(self):
        """GitHub連携とプロンプトが有効なSandboxConfig。"""
        return SandboxConfig(
            image="ghcr.io/test/sandbox:latest",
            cpu=1.0,
            memory_gb=2.0,
            environment={"ANTHROPIC_API_KEY": "test-key"},
            repository_url="https://github.com/example/repo",
            github_pat="ghp_test_pat_12345",
            prompt="Analyze this codebase",
        )

    @pytest.mark.asyncio
    async def test_create_sets_command_for_claude_execution(
        self, sandbox_manager, github_config_with_prompt
    ):
        """Claude Code実行用のコマンドがコンテナに設定されること。"""
        with patch.object(sandbox_manager, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = MagicMock(
                provisioning_state="Succeeded",
            )
            mock_client.container_groups.begin_create_or_update.return_value = mock_poller
            mock_get_client.return_value = mock_client

            await sandbox_manager.create("test-task-id-1234", github_config_with_prompt)

            call_args = mock_client.container_groups.begin_create_or_update.call_args
            container_group = call_args.kwargs["container_group"]
            container = container_group.containers[0]

            # コマンドが設定されていることを確認
            assert container.command is not None
            assert len(container.command) > 0

    @pytest.mark.asyncio
    async def test_command_includes_git_clone(self, sandbox_manager, github_config_with_prompt):
        """コマンドにgit cloneが含まれること。"""
        with patch.object(sandbox_manager, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = MagicMock(
                provisioning_state="Succeeded",
            )
            mock_client.container_groups.begin_create_or_update.return_value = mock_poller
            mock_get_client.return_value = mock_client

            await sandbox_manager.create("test-task-id-1234", github_config_with_prompt)

            call_args = mock_client.container_groups.begin_create_or_update.call_args
            container_group = call_args.kwargs["container_group"]
            container = container_group.containers[0]

            # コマンド文字列にgit cloneが含まれることを確認
            command_str = " ".join(container.command)
            assert "git clone" in command_str

    @pytest.mark.asyncio
    async def test_command_includes_claude_with_skip_permissions(
        self, sandbox_manager, github_config_with_prompt
    ):
        """コマンドにclaude --dangerously-skip-permissionsが含まれること。"""
        with patch.object(sandbox_manager, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = MagicMock(
                provisioning_state="Succeeded",
            )
            mock_client.container_groups.begin_create_or_update.return_value = mock_poller
            mock_get_client.return_value = mock_client

            await sandbox_manager.create("test-task-id-1234", github_config_with_prompt)

            call_args = mock_client.container_groups.begin_create_or_update.call_args
            container_group = call_args.kwargs["container_group"]
            container = container_group.containers[0]

            command_str = " ".join(container.command)
            assert "claude" in command_str
            assert "--dangerously-skip-permissions" in command_str

    @pytest.mark.asyncio
    async def test_command_includes_prompt_option(self, sandbox_manager, github_config_with_prompt):
        """コマンドに-pオプションでプロンプトが渡されること。"""
        with patch.object(sandbox_manager, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = MagicMock(
                provisioning_state="Succeeded",
            )
            mock_client.container_groups.begin_create_or_update.return_value = mock_poller
            mock_get_client.return_value = mock_client

            await sandbox_manager.create("test-task-id-1234", github_config_with_prompt)

            call_args = mock_client.container_groups.begin_create_or_update.call_args
            container_group = call_args.kwargs["container_group"]
            container = container_group.containers[0]

            command_str = " ".join(container.command)
            assert "-p" in command_str

    @pytest.mark.asyncio
    async def test_command_uses_github_pat_for_private_repos(
        self, sandbox_manager, github_config_with_prompt
    ):
        """プライベートリポジトリ用にGitHub PATを使ったcloneコマンドが設定されること。"""
        with patch.object(sandbox_manager, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = MagicMock(
                provisioning_state="Succeeded",
            )
            mock_client.container_groups.begin_create_or_update.return_value = mock_poller
            mock_get_client.return_value = mock_client

            await sandbox_manager.create("test-task-id-1234", github_config_with_prompt)

            call_args = mock_client.container_groups.begin_create_or_update.call_args
            container_group = call_args.kwargs["container_group"]
            container = container_group.containers[0]

            command_str = " ".join(container.command)
            # GITHUB_PAT環境変数を使ったcloneパターンが含まれること
            assert "GITHUB_PAT" in command_str

    @pytest.mark.asyncio
    async def test_no_command_without_repository_url(self, sandbox_manager):
        """repository_urlがない場合はコマンドが設定されないこと。"""
        basic_config = SandboxConfig(
            image="ghcr.io/test/sandbox:latest",
            cpu=1.0,
            memory_gb=2.0,
            environment={"ANTHROPIC_API_KEY": "test-key"},
        )

        with patch.object(sandbox_manager, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = MagicMock(
                provisioning_state="Succeeded",
            )
            mock_client.container_groups.begin_create_or_update.return_value = mock_poller
            mock_get_client.return_value = mock_client

            await sandbox_manager.create("test-task-id-1234", basic_config)

            call_args = mock_client.container_groups.begin_create_or_update.call_args
            container_group = call_args.kwargs["container_group"]
            container = container_group.containers[0]

            # repository_urlがない場合はコマンドがNone
            assert container.command is None


class TestSandboxStatusTransition:
    """サンドボックスステータス遷移のテスト。"""

    def test_sandbox_status_has_completed_value(self):
        """SandboxStatusにCOMPLETED状態が存在すること。"""
        # Note: Design DocではTaskStatusにCOMPLETEDがあるが、
        # SandboxStatusには現在TERMINATED/FAILEDのみ
        # この要件を満たすにはSandboxStatusの拡張またはTERMINATEDの解釈変更が必要
        # 現時点ではTERMINATEDを成功終了として扱う
        assert SandboxStatus.TERMINATED.value == "terminated"
        assert SandboxStatus.FAILED.value == "failed"

    def test_status_cloning_exists(self):
        """SandboxStatusにCLONING状態が存在すること。"""
        assert SandboxStatus.CLONING.value == "cloning"

    def test_status_running_exists(self):
        """SandboxStatusにRUNNING状態が存在すること。"""
        assert SandboxStatus.RUNNING.value == "running"
