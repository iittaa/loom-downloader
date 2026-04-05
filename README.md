# Loom Downloader

Loom動画をMP4形式でダウンロードできるWebアプリケーション。

## 機能

- LoomのURLを貼り付けるだけで動画情報（タイトル・解像度・再生時間）を取得
- ワンクリックでMP4ファイルとしてダウンロード
- ストリーミングダウンロードによりメモリ効率が良い

## 技術スタック

- **Python 3.12+**
- **FastAPI** - Webフレームワーク
- **httpx** - 非同期HTTPクライアント
- **uvicorn** - ASGIサーバー

## セットアップ

### 前提条件

- Python 3.12以上
- [uv](https://docs.astral.sh/uv/)（推奨）

### 起動

```bash
uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

ブラウザで http://localhost:8000 にアクセスしてください。

## 使い方

1. Loomの共有URL（`https://www.loom.com/share/...`）をテキストボックスに貼り付け
2. 「取得」ボタンをクリック（またはEnterキー）
3. 動画情報が表示されたら「ダウンロード」ボタンをクリック
