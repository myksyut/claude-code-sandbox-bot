"""
Pytest設定と共有フィクスチャ。

プロジェクト全体で共有されるフィクスチャと設定を定義します。
"""

import pytest


@pytest.fixture
def sample_data() -> dict[str, str]:
    """テスト用のサンプルデータを提供。"""
    return {"key": "value"}


@pytest.fixture
async def async_client():
    """統合テスト用の非同期クライアントを提供。"""
    # 非同期クライアントのセットアップをここに実装
    yield None
    # クリーンアップ
