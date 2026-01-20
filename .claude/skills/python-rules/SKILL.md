---
name: python-rules
description: 型安全性とエラーハンドリングルールを適用。型ヒント必須、例外処理のベストプラクティス。Python実装、型定義レビュー時に使用。
---

# Python 開発ルール

## Backend実装における型安全性

**データフローでの型安全性**
入力層（`Any`回避） → 型ガード/バリデーション → ビジネス層（型保証） → 出力層（シリアライズ）

**Backend固有の型シナリオ**:
- **API通信**: レスポンスは必ずPydanticモデルやTypeGuardで検証
- **外部入力**: `Any`を避け、明示的な型変換とバリデーション
- **レガシー統合**: Protocol型やABC（抽象基底クラス）で型安全な統合
- **テストコード**: モックも必ず型定義、`unittest.mock.MagicMock`のspec活用

## コーディング規約

**クラス使用の判断基準**
- **推奨：関数とProtocol/TypedDictでの実装**
  - 背景: テスタビリティと関数合成の柔軟性が向上
- **クラス使用を許可**:
  - フレームワーク要求時（Django Model、FastAPI依存性等）
  - カスタム例外クラス定義時
  - 状態とビジネスロジックが密結合している場合
- **判断基準**: 「このデータは振る舞いを持つか？」がYesならクラス検討

**関数設計**
- **引数は0-3個まで**: 4個以上はdataclass/TypedDictでオブジェクト化
- **キーワード引数を活用**: 可読性と明示性の向上

**依存性注入**
- **外部依存は引数で注入**: テスト可能性とモジュール性確保
- **Protocol型で抽象化**: 具象クラスへの依存を避ける

**非同期処理**
- async/await: 必ず型ヒントを付与
- エラーハンドリング: 必ず`try-except`でハンドリング
- 型定義: 戻り値の型は明示的に定義（例: `Coroutine[Any, Any, Result]`）

**フォーマット規則**
- ダブルクォート使用（ruffの設定に従う）
- 型は`PascalCase`、変数・関数は`snake_case`
- インポートは絶対パス優先

**クリーンコード原則**
- 使用されていないコードは即座に削除
- デバッグ用`print()`は削除（loggingモジュール使用）
- コメントアウトされたコード禁止（バージョン管理で履歴管理）
- コメントは「なぜ」を説明（「何」ではなく）
- docstringはGoogle形式を使用

## エラーハンドリング

**絶対ルール**: 例外の握りつぶし禁止。すべての例外は必ずログ出力と適切な処理を行う。

**Fail-Fast原則**: エラー時は速やかに失敗させ、不正な状態での処理継続を防ぐ
```python
# 禁止: 無条件フォールバック
except Exception:
    return default_value  # エラーを隠蔽

# 必須: 明示的な失敗
except Exception as e:
    logger.error("処理失敗: %s", e)
    raise  # 上位層で適切に処理
```

**Result型パターン**: エラーを型で表現し、明示的に処理
```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")

@dataclass
class Ok(Generic[T]):
    value: T

@dataclass
class Err(Generic[E]):
    error: E

Result = Ok[T] | Err[E]
```

**カスタム例外クラス**
```python
class AppError(Exception):
    def __init__(self, message: str, code: str, status_code: int = 500):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
```

## パフォーマンス最適化

- ジェネレータ活用: 大きなデータセットはイテレータで処理
- メモリ効率: 不要なオブジェクトは明示的に解放（`del`または参照削除）
- asyncio活用: I/Oバウンドな処理は非同期で実装
