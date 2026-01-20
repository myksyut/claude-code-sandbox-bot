---
name: frontend/python-testing
description: FastAPI + HTMX/Jinja2のテスト設計ルール。エンドポイントテスト、テンプレートレンダリングテスト時に使用。
---

# Python Webテストルール

## テストフレームワーク

- **pytest**: テストランナー
- **httpx**: 非同期HTTPクライアント（FastAPIテスト用）
- **pytest-asyncio**: 非同期テストサポート

## FastAPIテストの基本

### テストクライアントのセットアップ
```python
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

### エンドポイントテスト
```python
@pytest.mark.asyncio
async def test_index_returns_html(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<html" in response.text
```

### HTMXパーシャルレスポンステスト
```python
@pytest.mark.asyncio
async def test_htmx_partial_response(client):
    response = await client.get(
        "/api/items",
        headers={"HX-Request": "true"}
    )
    assert response.status_code == 200
    # パーシャルHTMLのため<html>タグは含まない
    assert "<html" not in response.text
    assert "item-list" in response.text
```

## テンプレートレンダリングテスト

### テンプレートコンテキストの検証
```python
from fastapi.testclient import TestClient
from src.main import app

def test_template_context():
    client = TestClient(app)
    response = client.get("/items/1")
    assert response.status_code == 200
    # 期待するコンテンツが含まれているか
    assert "アイテム詳細" in response.text
```

### コンポーネント単体テスト
```python
from jinja2 import Environment, FileSystemLoader

def test_card_component():
    env = Environment(loader=FileSystemLoader("src/templates"))
    template = env.get_template("components/card.html")
    result = template.module.card(title="テスト", content="内容")
    assert "テスト" in result
    assert "内容" in result
```

## フォームテスト

```python
@pytest.mark.asyncio
async def test_form_submission(client):
    response = await client.post(
        "/api/items",
        data={"title": "新規アイテム"},
        headers={"HX-Request": "true"}
    )
    assert response.status_code == 200
    assert "新規アイテム" in response.text
```

## エラーハンドリングテスト

```python
@pytest.mark.asyncio
async def test_404_htmx_response(client):
    response = await client.get(
        "/items/99999",
        headers={"HX-Request": "true"}
    )
    assert response.status_code == 404
    assert "見つかりません" in response.text

@pytest.mark.asyncio
async def test_404_full_page(client):
    response = await client.get("/items/99999")
    assert response.status_code == 404
```

## テスト構造

```
tests/
├── conftest.py           # 共有フィクスチャ
├── unit/
│   └── test_templates.py # テンプレート単体テスト
└── integration/
    ├── test_pages.py     # ページエンドポイント
    └── test_api.py       # APIエンドポイント
```
