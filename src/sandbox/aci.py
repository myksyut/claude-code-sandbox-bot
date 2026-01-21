"""
ACI管理モジュール。

Azure Container Instancesを使用してサンドボックスコンテナの
ライフサイクル管理(起動/破棄/ステータス取得)を行う。

Design Doc準拠のインターフェース:
- SandboxStatus: コンテナの状態を表すEnum
- Sandbox: サンドボックス情報を保持するモデル
- SandboxManager: Protocol型でインターフェース定義
- AzureSandboxManagerImpl: ACI SDKを使用した実装
"""

import logging
import time
from enum import Enum
from typing import Any, Protocol

from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.containerinstance.models import (
    Container,
    ContainerGroup,
    ContainerGroupRestartPolicy,
    EnvironmentVariable,
    OperatingSystemTypes,
    ResourceRequests,
    ResourceRequirements,
)
from pydantic import BaseModel

from src.task.models import SandboxConfig

logger = logging.getLogger(__name__)


class SandboxStatus(Enum):
    """サンドボックスの状態を表すEnum。

    コンテナのライフサイクルに対応する状態を定義する:
    - CREATING: コンテナ作成中
    - STARTING: コンテナ起動開始
    - CLONING: リポジトリクローン中
    - RUNNING: コンテナ実行中
    - TERMINATED: コンテナ終了済み
    - FAILED: コンテナ起動/実行失敗
    """

    CREATING = "creating"
    STARTING = "starting"
    CLONING = "cloning"
    RUNNING = "running"
    TERMINATED = "terminated"
    FAILED = "failed"


class Sandbox(BaseModel):
    """サンドボックス情報。

    ACIコンテナグループの情報を保持するモデル。

    Attributes:
        task_id: 対応するタスクのID
        container_group_name: ACIコンテナグループ名(sandbox-{task_id[:8]}形式)
        status: 現在のサンドボックス状態
        created_at: 作成時のUnixタイムスタンプ
    """

    task_id: str
    container_group_name: str
    status: SandboxStatus
    created_at: float


class SandboxCreationError(Exception):
    """サンドボックス作成エラー。

    ACIコンテナの起動に失敗した場合にraiseされる。

    Attributes:
        message: エラーメッセージ
        task_id: 対象タスクのID
        cause: 原因となった例外
    """

    def __init__(self, message: str, task_id: str, cause: Exception | None = None):
        super().__init__(message)
        self.task_id = task_id
        self.cause = cause


class CloneError(Exception):
    """リポジトリクローンエラー。

    GitHubリポジトリのクローンに失敗した場合にraiseされる。

    Attributes:
        message: エラーメッセージ
        task_id: 対象タスクのID
        cause: 原因となった例外
    """

    def __init__(self, message: str, task_id: str, cause: Exception | None = None):
        super().__init__(message)
        self.task_id = task_id
        self.cause = cause


class SandboxManager(Protocol):
    """サンドボックス管理のプロトコル定義。

    ACIコンテナのライフサイクル管理インターフェースを定義する。
    依存性注入パターンにより、テスト時にモックへ差し替え可能。
    """

    async def create(self, task_id: str, config: SandboxConfig) -> Sandbox:
        """サンドボックスを作成する。

        Args:
            task_id: タスクID
            config: サンドボックス設定

        Returns:
            作成されたSandboxインスタンス

        Raises:
            SandboxCreationError: コンテナ起動に失敗した場合
        """
        ...

    async def destroy(self, task_id: str) -> None:
        """サンドボックスを破棄する。

        Args:
            task_id: タスクID
        """
        ...

    async def get_status(self, task_id: str) -> SandboxStatus:
        """サンドボックスのステータスを取得する。

        Args:
            task_id: タスクID

        Returns:
            現在のSandboxStatus
        """
        ...


class AzureSandboxManagerImpl:
    """Azure Container Instancesを使用したSandboxManager実装。

    ACIコンテナグループの作成・削除・ステータス取得を行う。
    依存性注入パターンにより、subscription_id、resource_group、credentialを
    引数で受け取る。

    Attributes:
        subscription_id: AzureサブスクリプションID
        resource_group: Azureリソースグループ名
        credential: Azure認証情報
    """

    def __init__(
        self,
        subscription_id: str,
        resource_group: str,
        credential: Any,
    ) -> None:
        """AzureSandboxManagerImplを初期化する。

        Args:
            subscription_id: AzureサブスクリプションID
            resource_group: Azureリソースグループ名
            credential: Azure認証情報(DefaultAzureCredential等)
        """
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.credential = credential
        self._client: ContainerInstanceManagementClient | None = None
        self._sandboxes: dict[str, Sandbox] = {}

    def _get_client(self) -> ContainerInstanceManagementClient:
        """ACI管理クライアントを取得する(遅延初期化)。"""
        if self._client is None:
            self._client = ContainerInstanceManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id,
            )
        return self._client

    def _generate_container_group_name(self, task_id: str) -> str:
        """コンテナグループ名を生成する。

        Args:
            task_id: タスクID

        Returns:
            sandbox-{task_id[:8]}形式のコンテナグループ名
        """
        return f"sandbox-{task_id[:8]}"

    def _build_execution_command(self, config: SandboxConfig) -> list[str] | None:
        """サンドボックス実行コマンドを構築する。

        リポジトリURLが設定されている場合、以下の処理を行うコマンドを生成:
        1. GitHub PATがあればPAT認証でgit clone、なければ公開リポジトリとしてclone
        2. クローンしたディレクトリに移動
        3. Claude Code CLIを --dangerously-skip-permissions オプションで起動
        4. プロンプトを -p オプションで渡す

        Args:
            config: サンドボックス設定

        Returns:
            コマンドのリスト (repository_urlがない場合はNone)
        """
        if config.repository_url is None:
            return None

        # シェルスクリプトを構築
        script = """
set -e

# Clone repository
if [ -n "$GITHUB_PAT" ]; then
    # Extract owner/repo from URL
    REPO_PATH=$(echo "$REPOSITORY_URL" | sed 's|https://github.com/||')
    git clone "https://${GITHUB_PAT}@github.com/${REPO_PATH}" /workspace/repo
else
    git clone "$REPOSITORY_URL" /workspace/repo
fi

cd /workspace/repo

# Execute Claude Code
claude --dangerously-skip-permissions -p "$PROMPT" 2>&1
"""

        return ["/bin/bash", "-c", script.strip()]

    async def _create_container_group(
        self, container_group_name: str, config: SandboxConfig, task_id: str
    ) -> ContainerGroup:
        """ACIコンテナグループを作成する。

        Args:
            container_group_name: コンテナグループ名
            config: サンドボックス設定
            task_id: タスクID

        Returns:
            作成されたContainerGroup
        """
        client = self._get_client()

        # 環境変数を設定
        environment_variables = [
            EnvironmentVariable(name=key, secure_value=value)
            for key, value in config.environment.items()
        ]

        # GitHub連携の環境変数を追加
        if config.repository_url is not None:
            environment_variables.append(
                EnvironmentVariable(name="REPOSITORY_URL", value=config.repository_url)
            )
        if config.github_pat is not None:
            environment_variables.append(
                EnvironmentVariable(name="GITHUB_PAT", secure_value=config.github_pat)
            )
        if config.prompt is not None:
            environment_variables.append(EnvironmentVariable(name="PROMPT", value=config.prompt))
        # GitHub連携時にはTASK_IDも設定する
        if config.repository_url is not None or config.github_pat is not None:
            environment_variables.append(EnvironmentVariable(name="TASK_ID", value=task_id))

        # 実行コマンドを構築
        command = self._build_execution_command(config)

        # コンテナ定義
        container = Container(
            name=container_group_name,
            image=config.image,
            resources=ResourceRequirements(
                requests=ResourceRequests(
                    cpu=config.cpu,
                    memory_in_gb=config.memory_gb,
                )
            ),
            environment_variables=environment_variables,
            command=command,
        )

        # コンテナグループ定義
        container_group = ContainerGroup(
            location="japaneast",
            containers=[container],
            os_type=OperatingSystemTypes.LINUX,
            restart_policy=ContainerGroupRestartPolicy.NEVER,
        )

        logger.info(
            "Creating container group: %s in resource group: %s",
            container_group_name,
            self.resource_group,
        )

        # Create container group (sync API wrapped with await)
        poller = client.container_groups.begin_create_or_update(
            resource_group_name=self.resource_group,
            container_group_name=container_group_name,
            container_group=container_group,
        )

        result = poller.result()

        logger.info(
            "Container group created: %s, state: %s",
            container_group_name,
            result.provisioning_state,
        )

        return result

    async def _delete_container_group(self, container_group_name: str) -> None:
        """ACIコンテナグループを削除する。

        Args:
            container_group_name: コンテナグループ名
        """
        client = self._get_client()

        logger.info(
            "Deleting container group: %s from resource group: %s",
            container_group_name,
            self.resource_group,
        )

        try:
            poller = client.container_groups.begin_delete(
                resource_group_name=self.resource_group,
                container_group_name=container_group_name,
            )
            poller.result()

            logger.info("Container group deleted: %s", container_group_name)
        except Exception as e:
            logger.warning(
                "Failed to delete container group %s: %s",
                container_group_name,
                e,
            )

    async def create(self, task_id: str, config: SandboxConfig) -> Sandbox:
        """サンドボックスを作成する。

        ACIコンテナグループを起動し、Sandboxインスタンスを返す。

        Args:
            task_id: タスクID
            config: サンドボックス設定

        Returns:
            作成されたSandboxインスタンス

        Raises:
            SandboxCreationError: コンテナ起動に失敗した場合
        """
        container_group_name = self._generate_container_group_name(task_id)

        logger.info(
            "Starting sandbox creation for task: %s, container: %s",
            task_id,
            container_group_name,
        )

        try:
            result = await self._create_container_group(container_group_name, config, task_id)

            # ステータスを判定
            status = SandboxStatus.RUNNING
            if result.provisioning_state == "Failed":
                status = SandboxStatus.FAILED
            elif result.provisioning_state in ("Creating", "Pending"):
                status = SandboxStatus.CREATING

            sandbox = Sandbox(
                task_id=task_id,
                container_group_name=container_group_name,
                status=status,
                created_at=time.time(),
            )

            # トラッキングに追加
            self._sandboxes[task_id] = sandbox

            logger.info(
                "Sandbox created: task_id=%s, status=%s",
                task_id,
                status.value,
            )

            return sandbox

        except Exception as e:
            logger.error(
                "Failed to create sandbox for task %s: %s",
                task_id,
                e,
            )
            raise SandboxCreationError(
                message=f"Failed to create sandbox: {e}",
                task_id=task_id,
                cause=e,
            ) from e

    async def destroy(self, task_id: str) -> None:
        """サンドボックスを破棄する。

        ACIコンテナグループを削除し、トラッキングから除去する。

        Args:
            task_id: タスクID
        """
        sandbox = self._sandboxes.get(task_id)

        if sandbox is None:
            logger.warning(
                "Attempted to destroy unknown sandbox: task_id=%s",
                task_id,
            )
            return

        logger.info(
            "Destroying sandbox: task_id=%s, container=%s",
            task_id,
            sandbox.container_group_name,
        )

        await self._delete_container_group(sandbox.container_group_name)

        # トラッキングから削除
        del self._sandboxes[task_id]

        logger.info("Sandbox destroyed: task_id=%s", task_id)

    async def get_status(self, task_id: str) -> SandboxStatus:
        """サンドボックスのステータスを取得する。

        Args:
            task_id: タスクID

        Returns:
            現在のSandboxStatus。未知のtask_idの場合はTERMINATED
        """
        sandbox = self._sandboxes.get(task_id)

        if sandbox is None:
            return SandboxStatus.TERMINATED

        return sandbox.status
