"""
Redis接続モジュール。

非同期Redis接続とpub/sub、状態管理機能を提供する。

主要なエクスポート:
- RedisClient: Redisクライアントのプロトコル型
- AsyncRedisClientImpl: RedisClientの非同期実装
- LOCAL_QUEUE_MAX_SIZE: ローカルキューの最大サイズ
"""

from src.redis.client import (
    LOCAL_QUEUE_MAX_SIZE,
    AsyncRedisClientImpl,
    RedisClient,
)

__all__ = [
    "LOCAL_QUEUE_MAX_SIZE",
    "AsyncRedisClientImpl",
    "RedisClient",
]
