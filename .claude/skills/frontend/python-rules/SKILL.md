---
name: frontend/python-rules
description: FastAPI + HTMX/Jinja2を使用したPython Web開発ルール。フロントエンド実装、テンプレート設計時に使用。
---

# Python Web開発ルール（FastAPI + HTMX/Jinja2）

## 技術スタック

- **バックエンド**: FastAPI
- **テンプレートエンジン**: Jinja2
- **フロントエンドインタラクション**: HTMX
- **スタイリング**: Tailwind CSS（推奨）

## プロジェクト構造

```
src/
├── main.py              # FastAPIアプリケーション
├── routers/             # APIルーター
│   └── pages.py
├── templates/           # Jinja2テンプレート
│   ├── base.html
│   ├── components/      # 再利用可能なコンポーネント
│   └── pages/           # ページテンプレート
├── static/              # 静的ファイル
│   ├── css/
│   └── js/
└── schemas/             # Pydanticスキーマ
```

## FastAPIルーター設計

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "pages/index.html",
        {"request": request, "title": "ホーム"}
    )
```

## HTMXパターン

### 部分更新
```html
<!-- トリガー要素 -->
<button hx-get="/api/items" hx-target="#item-list" hx-swap="innerHTML">
    読み込み
</button>

<!-- 更新対象 -->
<div id="item-list">
    <!-- ここにコンテンツが挿入される -->
</div>
```

### フォーム送信
```html
<form hx-post="/api/items" hx-target="#result" hx-swap="outerHTML">
    <input type="text" name="title" required>
    <button type="submit">作成</button>
</form>
```

### インジケーター
```html
<button hx-get="/api/slow-endpoint" hx-indicator="#spinner">
    読み込み
</button>
<span id="spinner" class="htmx-indicator">処理中...</span>
```

## Jinja2テンプレート規約

### ベーステンプレート
```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}{% endblock %}</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    {% block head %}{% endblock %}
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
```

### コンポーネント化
```html
<!-- templates/components/card.html -->
{% macro card(title, content) %}
<div class="card">
    <h3>{{ title }}</h3>
    <p>{{ content }}</p>
</div>
{% endmacro %}
```

## エラーハンドリング

```python
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

@router.get("/items/{item_id}")
async def get_item(request: Request, item_id: int):
    item = await fetch_item(item_id)
    if not item:
        # HTMX リクエストの場合はパーシャルHTMLを返す
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                "<div class='error'>アイテムが見つかりません</div>",
                status_code=404
            )
        raise HTTPException(status_code=404, detail="Item not found")
    return templates.TemplateResponse(...)
```

## セキュリティ

- **CSRF対策**: FastAPIのCSRF保護を使用
- **XSS対策**: Jinja2の自動エスケープを有効化（デフォルト）
- **入力検証**: Pydanticモデルで全ての入力を検証
