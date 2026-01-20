"""
設定管理モジュール。

pydantic-settings を使用して環境変数を型安全に管理する。
os.environ の直接参照は禁止し、このモジュール経由で取得する。
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """アプリケーション設定。

    環境変数から設定を読み込み、型安全に管理する。
    必須環境変数が欠けている場合や形式が不正な場合は ValidationError を発生させる。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    slack_bot_token: str = Field(
        ...,
        pattern=r"^xoxb-.+$",
        description="Slack Bot token (must start with xoxb-)",
    )
    slack_app_token: str = Field(
        ...,
        pattern=r"^xapp-.+$",
        description="Slack App token (must start with xapp-)",
    )
    redis_url: str = Field(
        ...,
        description="Redis connection URL",
    )
    azure_subscription_id: str = Field(
        ...,
        description="Azure subscription ID",
    )
    azure_resource_group: str = Field(
        ...,
        description="Azure resource group name",
    )
    max_concurrent_tasks: int = Field(
        default=3,
        ge=1,
        description="Maximum concurrent tasks",
    )
    github_pat: str | None = Field(
        default=None,
        description="GitHub Personal Access Token (for private repositories)",
    )


@lru_cache
def get_settings() -> Settings:
    """Settingsインスタンスをキャッシュして返す。

    アプリケーション全体で同一のSettingsインスタンスを共有するために使用する。

    Returns:
        Settings: キャッシュされた設定インスタンス
    """
    return Settings()
