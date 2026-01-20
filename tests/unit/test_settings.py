"""
設定管理モジュールのテスト。

Settings クラスの環境変数読み込みとバリデーションをテストする。
"""

import pytest
from pydantic import ValidationError


class TestSettings:
    """Settings クラスのテスト。"""

    def test_valid_settings_with_all_required_env_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """必須環境変数がすべて設定されている場合、Settingsが正常に作成される。"""
        # Arrange
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")

        # Act
        from src.config.settings import Settings

        settings = Settings()

        # Assert
        assert settings.slack_bot_token == "xoxb-test-token"
        assert settings.slack_app_token == "xapp-test-token"
        assert settings.redis_url == "redis://localhost:6379"
        assert settings.azure_subscription_id == "test-subscription-id"
        assert settings.azure_resource_group == "test-resource-group"

    def test_default_max_concurrent_tasks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MAX_CONCURRENT_TASKS が未設定の場合、デフォルト値3が使用される。"""
        # Arrange
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")

        # Act
        from src.config.settings import Settings

        settings = Settings()

        # Assert
        assert settings.max_concurrent_tasks == 3

    def test_custom_max_concurrent_tasks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MAX_CONCURRENT_TASKS が設定されている場合、その値が使用される。"""
        # Arrange
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")
        monkeypatch.setenv("MAX_CONCURRENT_TASKS", "5")

        # Act
        from src.config.settings import Settings

        settings = Settings()

        # Assert
        assert settings.max_concurrent_tasks == 5

    def test_github_pat_is_optional(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GITHUB_PAT が未設定の場合、None が返される。"""
        # Arrange
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")

        # Act
        from src.config.settings import Settings

        settings = Settings()

        # Assert
        assert settings.github_pat is None

    def test_github_pat_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GITHUB_PAT が設定されている場合、その値が使用される。"""
        # Arrange
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")
        monkeypatch.setenv("GITHUB_PAT", "ghp_test_token")

        # Act
        from src.config.settings import Settings

        settings = Settings()

        # Assert
        assert settings.github_pat == "ghp_test_token"

    def test_missing_slack_bot_token_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SLACK_BOT_TOKEN が未設定の場合、ValidationError が発生する。"""
        # Arrange
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)

        # Act & Assert
        from src.config.settings import Settings

        with pytest.raises(ValidationError):
            Settings()

    def test_invalid_slack_bot_token_format_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SLACK_BOT_TOKEN が 'xoxb-' で始まらない場合、ValidationError が発生する。"""
        # Arrange
        monkeypatch.setenv("SLACK_BOT_TOKEN", "invalid-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")

        # Act & Assert
        from src.config.settings import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "slack_bot_token" in str(exc_info.value)

    def test_invalid_slack_app_token_format_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SLACK_APP_TOKEN が 'xapp-' で始まらない場合、ValidationError が発生する。"""
        # Arrange
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "invalid-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")

        # Act & Assert
        from src.config.settings import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        assert "slack_app_token" in str(exc_info.value)


class TestGetSettings:
    """get_settings 関数のテスト。"""

    def test_get_settings_returns_settings_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_settings は Settings インスタンスを返す。"""
        # Arrange
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")

        # Act
        from src.config.settings import Settings, get_settings

        settings = get_settings()

        # Assert
        assert isinstance(settings, Settings)

    def test_get_settings_returns_cached_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_settings は同じインスタンスをキャッシュして返す。"""
        # Arrange
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "test-subscription-id")
        monkeypatch.setenv("AZURE_RESOURCE_GROUP", "test-resource-group")

        # Act
        from src.config.settings import get_settings

        # キャッシュをクリア
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        # Assert
        assert settings1 is settings2
