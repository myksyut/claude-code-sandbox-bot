---
name: python-testing
description: pytestテスト設計と品質基準を適用。カバレッジ要件とモック使用ガイドを提供。ユニットテスト作成時に使用。
---

# Python テストルール

## テストフレームワーク

- **pytest**: このプロジェクトではpytestを使用
- テストのインポート: `import pytest`
- フィクスチャの使用: `@pytest.fixture`
- モックの作成: `unittest.mock.MagicMock` または `pytest-mock`

## テストの基本方針

### 品質要件
- **カバレッジ**: 単体テストのカバレッジは70%以上を必須
- **独立性**: 各テストは他のテストに依存せず実行可能
- **再現性**: テストは環境に依存せず、常に同じ結果を返す
- **可読性**: テストコードも製品コードと同様の品質を維持

### テストの種類と範囲
1. **単体テスト（Unit Tests）**
   - 個々の関数やクラスの動作を検証
   - 外部依存はすべてモック化
   - 最も数が多く、細かい粒度で実施

2. **統合テスト（Integration Tests）**
   - 複数のコンポーネントの連携を検証
   - 実際の依存関係を使用（DBやAPI等）
   - 主要な機能フローの検証

## テストの実装規約

### ディレクトリ構造
```
tests/
├── conftest.py           # 共有フィクスチャ
├── unit/                 # 単体テスト
│   └── test_service.py
└── integration/          # 統合テスト
    └── test_api.py
```

### 命名規則
- テストファイル: `test_{対象モジュール名}.py`
- テスト関数: `test_{テスト対象}_{期待される動作}`
- テストクラス: `Test{対象クラス名}`

## テスト品質基準

### 境界値・異常系の網羅
```python
def test_returns_zero_for_empty_list():
    assert calc([]) == 0

def test_raises_on_negative_price():
    with pytest.raises(ValueError):
        calc([{"price": -1}])
```

### 期待値の直接記述
```python
# Good: リテラルで期待値を記述
assert calc_tax(100) == 10

# Bad: 実装ロジックを再現
assert calc_tax(100) == 100 * TAX_RATE
```

### Property-based Testing（hypothesis）
```python
from hypothesis import given
import hypothesis.strategies as st

@given(st.lists(st.integers()))
def test_reverse_twice_equals_original(arr):
    assert list(reversed(list(reversed(arr)))) == arr
```

## モックの型安全性

### 必要最小限の型定義
```python
from unittest.mock import MagicMock

# specを使用して型安全性を確保
mock_repo = MagicMock(spec=Repository)
mock_repo.find.return_value = [user]
```

## pytestの基本例

```python
import pytest
from unittest.mock import MagicMock, patch

class TestUserService:
    @pytest.fixture
    def mock_repository(self):
        return MagicMock(spec=UserRepository)

    def test_should_create_user(self, mock_repository):
        # Arrange
        service = UserService(mock_repository)
        user_data = {"name": "test"}

        # Act
        result = service.create(user_data)

        # Assert
        assert result.id is not None
        mock_repository.save.assert_called_once()
```
