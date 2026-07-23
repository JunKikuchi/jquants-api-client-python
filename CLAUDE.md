# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

J-Quants API（JPX提供の個人投資家向け株式データAPI）のPythonクライアントライブラリ。全APIレスポンスをpandas DataFrameとして返す。

## よく使うコマンド

```bash
# 依存関係のインストール
poetry install

# テスト実行（カバレッジ付き）
make test
# または: poetry run pytest --cov=./jquantsapi tests/

# 特定のテストファイルを実行
poetry run pytest tests/test_client_v2.py

# 特定のテスト関数を実行
poetry run pytest tests/test_client_v2.py::test_関数名 -v

# リント（チェックのみ）
make lint

# リント（自動修正あり）
make lint-fix
```

## リント・フォーマット設定

- **black**: コードフォーマッター
- **isort**: import文の並び替え（blackプロファイル）
- **flake8**: 最大行長120文字、最大複雑度18、`tests/`は除外
- **mypy**: 型チェック（pandasのmissing importは無視設定）

## アーキテクチャ

### APIバージョン体系

- **V1 (`Client`)**: 非推奨。refresh_token/email/password認証。`client.py`に実装。
- **V2 (`ClientV2`)**: 現行版。APIキー認証（x-api-keyヘッダー）。`client_v2.py`に実装。

新規開発はV2が対象。V1コードは互換性のために残されている。

### パッケージ構造

```
jquantsapi/
├── __init__.py        # 公開API: Client, ClientV2, SharedRateLimiter, MARKET_API_SECTIONS, BulkEndpoint
├── client.py          # V1クライアント（非推奨）
├── client_v2.py       # V2クライアント（現行）
├── rate_limiter.py    # SharedRateLimiter（トークンバケット方式、fcntl.flockによるプロセス間共有）
├── constants.py       # カラム定義、セクター分類データ（17業種・33業種）
├── enums.py           # MARKET_API_SECTIONS, BulkEndpoint
└── apis/
    ├── base.py        # SupportsRequest Protocol + BaseApi ABC
    ├── v1/            # V1用API実装（6モジュール）
    └── v2/            # V2用API実装（6モジュール）
```

### 設計パターン

- **クライアント層**（`client.py`, `client_v2.py`）: HTTP通信、設定読み込み、セッション管理、リトライ制御（V1: tenacity、V2: urllib3 Retry + 指数バックオフ）、スレッドプール（MAX_WORKERS=5）、レートリミット（`SharedRateLimiter`）
- **API層**（`apis/`）: 各エンドポイントごとに`BaseApi`を継承したクラスを実装。`execute()`メソッドでDataFrameを返す
- **`SupportsRequest` Protocol**: クライアントが満たすべき最小インターフェース（`JQUANTS_API_BASE`, `RAW_ENCODING`, `_get()`）

クライアントクラスが各APIクラスのインスタンスを保持し、公開メソッド（例: `get_eq_master()`）からAPIクラスの`execute()`を呼び出す構造。

### V2 API カテゴリ（`apis/v2/`）

| モジュール | 内容 |
|-----------|------|
| `equities.py` | 銘柄マスター、日足・分足、決算発表日、投資部門別 |
| `fins.py` | 財務サマリー、財務詳細、配当 |
| `indices.py` | 指数日足、TOPIX日足 |
| `markets.py` | 空売り比率、信用取引残高、信用売買残、売買内訳、営業日カレンダー |
| `derivatives.py` | 先物・オプション日足 |
| `bulk.py` | バルクデータ一覧・取得 |

### ClientV2の設定読み込み優先順位（後が優先）

1. Google Colabパス
2. `~/.jquants-api/jquants-api.toml`
3. `./jquants-api.toml`
4. 環境変数 `JQUANTS_API_CLIENT_CONFIG_FILE` で指定したファイル
5. 環境変数 `JQUANTS_API_KEY`

### レートリミット設定

設定ファイル（`jquants-api.toml`）と環境変数の両方で設定可能。環境変数が優先される。

| 設定ファイルキー | 環境変数 | 説明 | デフォルト値 |
|----------------|---------|------|------------|
| `rate_limit` | `JQUANTS_API_RATE_LIMIT` | 時間窓あたりの最大リクエスト数 | `5` |
| `rate_limit_per` | `JQUANTS_API_RATE_LIMIT_PER` | 時間窓の秒数 | `60.0` |
| `rate_limit_lock_file` | `JQUANTS_API_RATE_LIMIT_LOCK_FILE` | ロックファイルのパス | `/tmp/jquants_rate.lock` |

デフォルトは Free プラン（5リクエスト/分）。`ClientV2(rate_limiter=None)` で無効化可能。

### リトライ設定

429/5xx エラー時に指数バックオフ付きでリトライ。設定ファイルと環境変数の両方で設定可能。環境変数が優先される。

| 設定ファイルキー | 環境変数 | 説明 | デフォルト値 |
|----------------|---------|------|------------|
| `retry_total` | `JQUANTS_API_RETRY_TOTAL` | 最大リトライ回数 | `10` |
| `retry_backoff_factor` | `JQUANTS_API_RETRY_BACKOFF_FACTOR` | 指数バックオフの係数 | `1` |

### 並列実行数設定

`_range` 系メソッドのスレッドプール並列数。設定ファイルと環境変数の両方で設定可能。環境変数が優先される。

| 設定ファイルキー | 環境変数 | 説明 | デフォルト値 |
|----------------|---------|------|------------|
| `max_workers` | `JQUANTS_API_MAX_WORKERS` | 並列実行するスレッド数 | `5` |

## ビルド・リリース

- **パッケージ管理**: Poetry
- **バージョニング**: poetry-dynamic-versioning（gitタグから自動生成）
- **Python対応バージョン**: 3.10, 3.11, 3.12, 3.13
- **PyPI公開**: GitHubリリース作成時に自動パブリッシュ（`.github/workflows/publish.yml`）
