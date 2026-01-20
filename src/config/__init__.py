"""
設定管理モジュール。

環境変数を型安全に管理し、アプリケーション全体で使用する設定を提供する。
"""

from src.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
