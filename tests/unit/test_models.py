"""
タスク関連モデルの単体テスト。

Design Docの型定義に準拠したPydanticモデルのテスト:
- TaskStatus Enum
- Task, SandboxConfig, TaskMessage, HumanQuestion Pydanticモデル
- 各モデルのバリデーション(正常・異常ケース)
"""

import pytest
from pydantic import ValidationError
from src.task.models import (
    HumanQuestion,
    SandboxConfig,
    Task,
    TaskMessage,
    TaskStatus,
)


class TestTaskStatus:
    """TaskStatus Enumのテスト。"""

    def test_all_status_values_exist(self):
        """全てのステータス値が存在することを確認。"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.STARTING.value == "starting"
        assert TaskStatus.CLONING.value == "cloning"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.WAITING_USER.value == "waiting_user"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_status_count(self):
        """ステータスの数が8個であることを確認。"""
        assert len(TaskStatus) == 8


class TestTask:
    """Taskモデルのテスト。"""

    def test_valid_task_creation(self):
        """有効なタスクが作成できることを確認。"""
        task = Task(
            id="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            channel_id="C12345678",
            thread_ts="1234567890.123456",
            user_id="U12345678",
            prompt="Analyze this repository",
            repository_url="https://github.com/example/repo",
            status=TaskStatus.PENDING,
            created_at=1234567890.123456,
            idempotency_key="unique-key-123",
        )
        assert task.id == "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        assert task.channel_id == "C12345678"
        assert task.thread_ts == "1234567890.123456"
        assert task.user_id == "U12345678"
        assert task.prompt == "Analyze this repository"
        assert task.repository_url == "https://github.com/example/repo"
        assert task.status == TaskStatus.PENDING
        assert task.created_at == 1234567890.123456
        assert task.idempotency_key == "unique-key-123"

    def test_invalid_task_id_format(self):
        """無効なタスクIDフォーマットでバリデーションエラーが発生することを確認。"""
        with pytest.raises(ValidationError) as exc_info:
            Task(
                id="invalid-id",
                channel_id="C12345678",
                thread_ts="1234567890.123456",
                user_id="U12345678",
                prompt="Test",
                repository_url="https://github.com/example/repo",
                status=TaskStatus.PENDING,
                created_at=1234567890.123456,
                idempotency_key="key",
            )
        assert "id" in str(exc_info.value)

    def test_empty_prompt_validation(self):
        """空のプロンプトでバリデーションエラーが発生することを確認。"""
        with pytest.raises(ValidationError) as exc_info:
            Task(
                id="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                channel_id="C12345678",
                thread_ts="1234567890.123456",
                user_id="U12345678",
                prompt="",
                repository_url="https://github.com/example/repo",
                status=TaskStatus.PENDING,
                created_at=1234567890.123456,
                idempotency_key="key",
            )
        assert "prompt" in str(exc_info.value)

    def test_invalid_repository_url_format(self):
        """無効なリポジトリURLでバリデーションエラーが発生することを確認。"""
        with pytest.raises(ValidationError) as exc_info:
            Task(
                id="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                channel_id="C12345678",
                thread_ts="1234567890.123456",
                user_id="U12345678",
                prompt="Test",
                repository_url="https://gitlab.com/example/repo",
                status=TaskStatus.PENDING,
                created_at=1234567890.123456,
                idempotency_key="key",
            )
        assert "repository_url" in str(exc_info.value)

    def test_non_github_url_rejected(self):
        """GitHub以外のURLが拒否されることを確認。"""
        invalid_urls = [
            "http://github.com/example/repo",  # httpsではない
            "https://bitbucket.org/example/repo",
            "ftp://github.com/example/repo",
            "github.com/example/repo",  # プロトコルなし
        ]
        for url in invalid_urls:
            with pytest.raises(ValidationError):
                Task(
                    id="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                    channel_id="C12345678",
                    thread_ts="1234567890.123456",
                    user_id="U12345678",
                    prompt="Test",
                    repository_url=url,
                    status=TaskStatus.PENDING,
                    created_at=1234567890.123456,
                    idempotency_key="key",
                )


class TestSandboxConfig:
    """SandboxConfigモデルのテスト。"""

    def test_valid_sandbox_config_creation(self):
        """有効なサンドボックス設定が作成できることを確認。"""
        config = SandboxConfig(
            image="claude-sandbox:latest",
            cpu=2.0,
            memory_gb=4.0,
            environment={"ANTHROPIC_API_KEY": "test-key"},
        )
        assert config.image == "claude-sandbox:latest"
        assert config.cpu == 2.0
        assert config.memory_gb == 4.0
        assert config.environment == {"ANTHROPIC_API_KEY": "test-key"}

    def test_zero_cpu_validation(self):
        """CPU=0でバリデーションエラーが発生することを確認。"""
        with pytest.raises(ValidationError) as exc_info:
            SandboxConfig(
                image="claude-sandbox:latest",
                cpu=0,
                memory_gb=4.0,
                environment={},
            )
        assert "cpu" in str(exc_info.value)

    def test_negative_cpu_validation(self):
        """負のCPU値でバリデーションエラーが発生することを確認。"""
        with pytest.raises(ValidationError) as exc_info:
            SandboxConfig(
                image="claude-sandbox:latest",
                cpu=-1.0,
                memory_gb=4.0,
                environment={},
            )
        assert "cpu" in str(exc_info.value)

    def test_zero_memory_validation(self):
        """メモリ=0でバリデーションエラーが発生することを確認。"""
        with pytest.raises(ValidationError) as exc_info:
            SandboxConfig(
                image="claude-sandbox:latest",
                cpu=2.0,
                memory_gb=0,
                environment={},
            )
        assert "memory_gb" in str(exc_info.value)

    def test_negative_memory_validation(self):
        """負のメモリ値でバリデーションエラーが発生することを確認。"""
        with pytest.raises(ValidationError) as exc_info:
            SandboxConfig(
                image="claude-sandbox:latest",
                cpu=2.0,
                memory_gb=-1.0,
                environment={},
            )
        assert "memory_gb" in str(exc_info.value)

    def test_empty_environment_allowed(self):
        """空の環境変数辞書が許可されることを確認。"""
        config = SandboxConfig(
            image="claude-sandbox:latest",
            cpu=1.0,
            memory_gb=1.0,
            environment={},
        )
        assert config.environment == {}

    def test_optional_github_fields_default_to_none(self):
        """GitHub連携フィールドがデフォルトでNoneであることを確認。"""
        config = SandboxConfig(
            image="claude-sandbox:latest",
            cpu=1.0,
            memory_gb=1.0,
            environment={},
        )
        assert config.repository_url is None
        assert config.github_pat is None
        assert config.prompt is None

    def test_sandbox_config_with_github_fields(self):
        """GitHub連携フィールドが設定できることを確認。"""
        config = SandboxConfig(
            image="claude-sandbox:latest",
            cpu=1.0,
            memory_gb=1.0,
            environment={},
            repository_url="https://github.com/example/repo",
            github_pat="ghp_test_pat_12345",
            prompt="Analyze this codebase",
        )
        assert config.repository_url == "https://github.com/example/repo"
        assert config.github_pat == "ghp_test_pat_12345"
        assert config.prompt == "Analyze this codebase"

    def test_sandbox_config_with_partial_github_fields(self):
        """GitHub連携フィールドが部分的に設定できることを確認。"""
        config = SandboxConfig(
            image="claude-sandbox:latest",
            cpu=1.0,
            memory_gb=1.0,
            environment={},
            repository_url="https://github.com/example/repo",
        )
        assert config.repository_url == "https://github.com/example/repo"
        assert config.github_pat is None
        assert config.prompt is None


class TestTaskMessage:
    """TaskMessageモデルのテスト。"""

    def test_valid_progress_message(self):
        """有効な進捗メッセージが作成できることを確認。"""
        message = TaskMessage(
            task_id="task-123",
            type="progress",
            payload={"status": "running", "progress": "50%"},
        )
        assert message.task_id == "task-123"
        assert message.type == "progress"
        assert message.payload == {"status": "running", "progress": "50%"}

    def test_valid_result_message(self):
        """有効な結果メッセージが作成できることを確認。"""
        message = TaskMessage(
            task_id="task-123",
            type="result",
            payload={"output": "Analysis complete"},
        )
        assert message.type == "result"

    def test_valid_question_message(self):
        """有効な質問メッセージが作成できることを確認。"""
        message = TaskMessage(
            task_id="task-123",
            type="question",
            payload={"question": "Should I proceed?"},
        )
        assert message.type == "question"

    def test_valid_error_message(self):
        """有効なエラーメッセージが作成できることを確認。"""
        message = TaskMessage(
            task_id="task-123",
            type="error",
            payload={"error": "Clone failed"},
        )
        assert message.type == "error"

    def test_invalid_message_type(self):
        """無効なメッセージタイプでバリデーションエラーが発生することを確認。"""
        with pytest.raises(ValidationError) as exc_info:
            TaskMessage(
                task_id="task-123",
                type="invalid_type",
                payload={},
            )
        assert "type" in str(exc_info.value)

    def test_empty_payload_allowed(self):
        """空のペイロードが許可されることを確認。"""
        message = TaskMessage(
            task_id="task-123",
            type="progress",
            payload={},
        )
        assert message.payload == {}


class TestHumanQuestion:
    """HumanQuestionモデルのテスト。"""

    def test_valid_question_with_options(self):
        """オプション付きの質問が作成できることを確認。"""
        question = HumanQuestion(
            task_id="task-123",
            question="Which approach should I use?",
            options=["Approach A", "Approach B", "Approach C"],
            timeout_seconds=300,
        )
        assert question.task_id == "task-123"
        assert question.question == "Which approach should I use?"
        assert question.options == ["Approach A", "Approach B", "Approach C"]
        assert question.timeout_seconds == 300

    def test_valid_question_without_options(self):
        """オプションなしの質問が作成できることを確認。"""
        question = HumanQuestion(
            task_id="task-123",
            question="What is your preference?",
        )
        assert question.options is None
        assert question.timeout_seconds == 600  # デフォルト値

    def test_default_timeout_is_600(self):
        """デフォルトタイムアウトが600秒であることを確認。"""
        question = HumanQuestion(
            task_id="task-123",
            question="Test question",
        )
        assert question.timeout_seconds == 600

    def test_custom_timeout(self):
        """カスタムタイムアウトが設定できることを確認。"""
        question = HumanQuestion(
            task_id="task-123",
            question="Test question",
            timeout_seconds=120,
        )
        assert question.timeout_seconds == 120

    def test_empty_options_list(self):
        """空のオプションリストが許可されることを確認。"""
        question = HumanQuestion(
            task_id="task-123",
            question="Test question",
            options=[],
        )
        assert question.options == []
