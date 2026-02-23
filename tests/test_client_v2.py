from contextlib import nullcontext as does_not_raise
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from dateutil import tz

import jquantsapi
from jquantsapi import client_v2
from jquantsapi.rate_limiter import SharedRateLimiter


@pytest.mark.parametrize(
    "api_key," "env, isfile, load," "exp_api_key," "exp_raise",
    (
        # Case 1: api_key未指定、設定ファイルなし、環境変数なし → エラー
        (
            None,
            {},
            [False, False, False, False],
            [],
            "",
            pytest.raises(ValueError),
        ),
        # Case 2: 設定ファイルからapi_key取得
        (
            None,
            {},
            [True, False, False, False],
            [
                {
                    "jquants-api-client": {
                        "api_key": "api_key_from_colab",
                    }
                },
            ],
            "api_key_from_colab",
            does_not_raise(),
        ),
        # Case 3: 複数の設定ファイルがある場合、後のものが優先
        (
            None,
            {"JQUANTS_API_CLIENT_CONFIG_FILE": "custom.toml"},
            [True, True, True, True],
            [
                {
                    "jquants-api-client": {
                        "api_key": "api_key_colab",
                    }
                },
                {
                    "jquants-api-client": {
                        "api_key": "api_key_user",
                    }
                },
                {
                    "jquants-api-client": {
                        "api_key": "api_key_current",
                    }
                },
                {
                    "jquants-api-client": {
                        "api_key": "api_key_env_file",
                    }
                },
            ],
            "api_key_env_file",
            does_not_raise(),
        ),
        # Case 4: 環境変数JQUANTS_API_KEYが最優先
        (
            None,
            {"JQUANTS_API_KEY": "api_key_from_env"},
            [True, False, False, False],
            [
                {
                    "jquants-api-client": {
                        "api_key": "api_key_from_file",
                    }
                },
            ],
            "api_key_from_env",
            does_not_raise(),
        ),
        # Case 5: 引数で直接指定（最優先）
        (
            "api_key_from_arg",
            {"JQUANTS_API_KEY": "api_key_from_env"},
            [True, False, False, False],
            [
                {
                    "jquants-api-client": {
                        "api_key": "api_key_from_file",
                    }
                },
            ],
            "api_key_from_arg",
            does_not_raise(),
        ),
        # Case 6: 引数のみで指定（設定ファイルなし、環境変数なし）
        (
            "api_key_only_arg",
            {},
            [False, False, False, False],
            [],
            "api_key_only_arg",
            does_not_raise(),
        ),
        # Case 7: 設定ファイルにjquants-api-clientセクションがない場合
        (
            None,
            {},
            [True, False, False, False],
            [
                {
                    "other-section": {
                        "api_key": "api_key_wrong_section",
                    }
                },
            ],
            "",
            pytest.raises(ValueError),
        ),
    ),
)
def test_client_v2_config(
    api_key,
    env,
    isfile,
    load,
    exp_api_key,
    exp_raise,
):
    """ClientV2の設定ファイルと環境変数からのapi_key読み込みテスト"""
    with exp_raise, patch.object(
        jquantsapi.ClientV2, "_is_colab", return_value=True
    ), patch.object(client_v2.os.path, "isfile", side_effect=isfile), patch(
        "builtins.open"
    ), patch.dict(
        client_v2.os.environ, env, clear=True
    ), patch.object(
        client_v2.tomllib, "load", side_effect=load
    ):
        cli = jquantsapi.ClientV2(api_key=api_key)
        assert cli._api_key == exp_api_key


@pytest.mark.parametrize(
    "code, date_yyyymmdd, exp_params",
    (
        ("", "", {}),
        ("86970", "", {"code": "86970"}),
        ("", "20220101", {"date": "20220101"}),
        ("86970", "20220101", {"code": "86970", "date": "20220101"}),
    ),
)
def test_get_eq_master(code, date_yyyymmdd, exp_params):
    """get_eq_masterのパラメータテスト"""
    ret_value = []  # _get_paginatedは配列を返す
    exp_ret_len = 0
    exp_raise = does_not_raise()

    with exp_raise, patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ), patch.object(jquantsapi.ClientV2, "_get_paginated") as mock_get_paginated:
        mock_get_paginated.return_value = ret_value

        cli = jquantsapi.ClientV2()
        ret = cli.get_eq_master(code=code, date=date_yyyymmdd)
        args, kwargs = mock_get_paginated.call_args
        assert kwargs.get("params", {}) == exp_params
        assert len(ret) == exp_ret_len


@pytest.mark.parametrize(
    "code, from_yyyymmdd, to_yyyymmdd, date_yyyymmdd, exp_params",
    (
        ("", "", "", "", {}),
        ("86970", "", "", "", {"code": "86970"}),
        ("86970", "20220101", "", "", {"code": "86970", "from": "20220101"}),
        ("86970", "", "20220131", "", {"code": "86970", "to": "20220131"}),
        (
            "86970",
            "20220101",
            "20220131",
            "",
            {"code": "86970", "from": "20220101", "to": "20220131"},
        ),
        ("", "", "", "20220115", {"date": "20220115"}),
        ("86970", "", "", "20220115", {"code": "86970", "date": "20220115"}),
    ),
)
def test_get_eq_bars_daily(code, from_yyyymmdd, to_yyyymmdd, date_yyyymmdd, exp_params):
    """get_eq_bars_dailyのパラメータテスト"""
    ret_value = {"data": []}  # resp.json()で返される辞書
    exp_ret_len = 0
    exp_raise = does_not_raise()

    with exp_raise, patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ), patch.object(jquantsapi.ClientV2, "_get") as mock_get:
        mock_get.return_value.json.return_value = ret_value

        cli = jquantsapi.ClientV2()
        ret = cli.get_eq_bars_daily(
            code=code,
            from_yyyymmdd=from_yyyymmdd,
            to_yyyymmdd=to_yyyymmdd,
            date_yyyymmdd=date_yyyymmdd,
        )
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == exp_params
        assert len(ret) == exp_ret_len


def test_get_eq_bars_daily_range():
    """
    get_eq_bars_daily_range()を呼ぶ際、引数に様々な型が入っていても問題なく
    get_eq_bars_daily()に単一の年月日が渡される事を確認する。
    """
    mock = MagicMock(return_value=pd.DataFrame(columns=["Code", "Date"]))

    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ):
        cli = jquantsapi.ClientV2()
        cli.get_eq_bars_daily = mock

    formats = {
        "str_8digits": ("20200227", "20200302"),
        "str_split_by_hyphen": ("2020-02-27", "2020-03-02"),
        "datetime_without_tz": (datetime(2020, 2, 27), datetime(2020, 3, 2)),
        "datetime_with_tz": (
            datetime(2020, 2, 27, tzinfo=tz.gettz("Asia/Tokyo")),
            datetime(2020, 3, 2, tzinfo=tz.gettz("Asia/Tokyo")),
        ),
        "pd.Timestamp": (pd.Timestamp("2020-02-27"), pd.Timestamp("2020-03-02")),
    }

    for _fmt, (start, end) in formats.items():
        cli.get_eq_bars_daily_range(start, end)

        # 並列実行のため順序は保証されないので、セットとして比較
        expected_dates = {
            "2020-02-27",
            "2020-02-28",
            "2020-02-29",
            "2020-03-01",
            "2020-03-02",
        }
        actual_dates = {
            call_obj.kwargs["date_yyyymmdd"] for call_obj in mock.mock_calls
        }
        assert actual_dates == expected_dates
        assert len(mock.mock_calls) == 5
        mock.reset_mock()


def test_aggregate_bars_n_minute():
    """_aggregate_bars_n_minute()のテスト: 1分足から5分足への集計"""
    # テスト用の1分足データ
    data = {
        "Date": ["2024-01-01"] * 10,
        "Time": [
            "09:00:00",
            "09:01:00",
            "09:02:00",
            "09:03:00",
            "09:04:00",
            "09:05:00",
            "09:06:00",
            "09:07:00",
            "09:08:00",
            "09:09:00",
        ],
        "Code": ["86970"] * 10,
        "O": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        "H": [110, 111, 112, 113, 114, 115, 116, 117, 118, 119],
        "L": [90, 91, 92, 93, 94, 95, 96, 97, 98, 99],
        "C": [105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
        "Vo": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900],
        "Va": [
            100000,
            110000,
            120000,
            130000,
            140000,
            150000,
            160000,
            170000,
            180000,
            190000,
        ],
    }
    df_1min = pd.DataFrame(data)

    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ):
        cli = jquantsapi.ClientV2()
        result = cli._aggregate_bars_n_minute(df_1min, 5)

    # 5分足に集計されることを確認
    assert len(result) == 2

    # 最初の5分足（09:00-09:04）
    row1 = result.iloc[0]
    assert row1["Time"] == "09:00:00"
    assert row1["O"] == 100  # 最初の始値
    assert row1["H"] == 114  # 最高値
    assert row1["L"] == 90  # 最安値
    assert row1["C"] == 109  # 最後の終値
    assert row1["Vo"] == 6000  # 出来高合計
    assert row1["Va"] == 600000  # 売買代金合計

    # 2番目の5分足（09:05-09:09）
    row2 = result.iloc[1]
    assert row2["Time"] == "09:05:00"
    assert row2["O"] == 105
    assert row2["H"] == 119
    assert row2["L"] == 95
    assert row2["C"] == 114
    assert row2["Vo"] == 8500
    assert row2["Va"] == 850000


def test_aggregate_bars_n_minute_15min():
    """_aggregate_bars_n_minute()のテスト: 1分足から15分足への集計"""
    # テスト用の1分足データ（15分分）
    times = [f"09:{str(i).zfill(2)}:00" for i in range(15)]
    data = {
        "Date": ["2024-01-01"] * 15,
        "Time": times,
        "Code": ["86970"] * 15,
        "O": list(range(100, 115)),
        "H": list(range(120, 135)),
        "L": list(range(80, 95)),
        "C": list(range(110, 125)),
        "Vo": [1000] * 15,
        "Va": [100000] * 15,
    }
    df_1min = pd.DataFrame(data)

    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ):
        cli = jquantsapi.ClientV2()
        result = cli._aggregate_bars_n_minute(df_1min, 15)

    # 15分足に集計されることを確認
    assert len(result) == 1

    row = result.iloc[0]
    assert row["Time"] == "09:00:00"
    assert row["O"] == 100  # 最初の始値
    assert row["H"] == 134  # 最高値
    assert row["L"] == 80  # 最安値
    assert row["C"] == 124  # 最後の終値
    assert row["Vo"] == 15000  # 出来高合計
    assert row["Va"] == 1500000  # 売買代金合計


@pytest.mark.parametrize(
    "endpoint, exp_params",
    (
        ("/equities/master", {"endpoint": "/equities/master"}),
        ("/equities/bars/daily", {"endpoint": "/equities/bars/daily"}),
        ("/fins/summary", {"endpoint": "/fins/summary"}),
    ),
)
def test_get_bulk_list(endpoint, exp_params):
    """get_bulk_listのパラメータテスト"""
    ret_value = {"data": []}  # resp.json()で返される辞書
    exp_ret_len = 0
    exp_raise = does_not_raise()

    with exp_raise, patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ), patch.object(jquantsapi.ClientV2, "_get") as mock_get:
        mock_get.return_value.json.return_value = ret_value

        cli = jquantsapi.ClientV2()
        ret = cli.get_bulk_list(endpoint=endpoint)
        args, _ = mock_get.call_args
        assert args[1] == exp_params
        assert len(ret) == exp_ret_len


def test_get_bulk():
    """get_bulkのテスト"""
    ret_value = {"url": "https://example.com/data.csv"}  # resp.json()で返される辞書
    exp_raise = does_not_raise()

    with exp_raise, patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ), patch.object(jquantsapi.ClientV2, "_get") as mock_get:
        mock_get.return_value.json.return_value = ret_value

        cli = jquantsapi.ClientV2()
        ret = cli.get_bulk(key="2024/01/01/eq_master.csv")
        args, _ = mock_get.call_args
        assert args[1] == {"key": "2024/01/01/eq_master.csv"}
        assert ret == "https://example.com/data.csv"


# ------------------------------------------------------------------
# レートリミッター統合テスト
# ------------------------------------------------------------------


def test_default_rate_limiter():
    """デフォルトでレートリミッターが有効であることの確認"""
    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ):
        cli = jquantsapi.ClientV2()
        assert cli._rate_limiter is not None
        assert isinstance(cli._rate_limiter, SharedRateLimiter)
        assert cli._rate_limiter.rate == 5
        assert cli._rate_limiter.per == 60.0


def test_rate_limiter_disabled():
    """rate_limiter=Noneで無効化できることの確認"""
    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ):
        cli = jquantsapi.ClientV2(rate_limiter=None)
        assert cli._rate_limiter is None


def test_custom_rate_limiter(tmp_path):
    """カスタムSharedRateLimiterインスタンスの受け渡し確認"""
    lock_file = str(tmp_path / "custom.lock")
    custom_limiter = SharedRateLimiter(rate=5, per=2.0, lock_file=lock_file)
    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ):
        cli = jquantsapi.ClientV2(rate_limiter=custom_limiter)
        assert cli._rate_limiter is custom_limiter
        assert cli._rate_limiter.rate == 5
        assert cli._rate_limiter.per == 2.0


def test_get_calls_acquire():
    """_get()呼び出し時にacquire()が呼ばれることの確認"""
    mock_limiter = MagicMock(spec=SharedRateLimiter)
    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ), patch.object(jquantsapi.ClientV2, "_request_session") as mock_session:
        mock_session.return_value.get.return_value.raise_for_status = MagicMock()
        cli = jquantsapi.ClientV2(rate_limiter=mock_limiter)
        cli._get("https://example.com/test")
        mock_limiter.acquire.assert_called_once()


def test_get_without_rate_limiter():
    """rate_limiter=Noneの場合、acquire()が呼ばれないことの確認"""
    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ), patch.object(jquantsapi.ClientV2, "_request_session") as mock_session:
        mock_session.return_value.get.return_value.raise_for_status = MagicMock()
        cli = jquantsapi.ClientV2(rate_limiter=None)
        cli._get("https://example.com/test")
        # rate_limiter が None なので acquire は呼ばれない（エラーにならない）


@pytest.mark.parametrize(
    "env, exp_rate, exp_per",
    (
        # JQUANTS_API_RATE_LIMIT のみ設定
        ({"JQUANTS_API_RATE_LIMIT": "120"}, 120.0, 60.0),
        # JQUANTS_API_RATE_LIMIT_PER のみ設定
        ({"JQUANTS_API_RATE_LIMIT_PER": "1.0"}, 5.0, 1.0),
        # 両方設定
        (
            {"JQUANTS_API_RATE_LIMIT": "20", "JQUANTS_API_RATE_LIMIT_PER": "5.0"},
            20.0,
            5.0,
        ),
    ),
)
def test_rate_limiter_env_vars(env, exp_rate, exp_per):
    """環境変数でデフォルトレートリミット設定を変更できることの確認"""
    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ), patch.dict(client_v2.os.environ, env, clear=False):
        cli = jquantsapi.ClientV2()
        assert cli._rate_limiter is not None
        assert cli._rate_limiter.rate == exp_rate
        assert cli._rate_limiter.per == exp_per


def test_rate_limiter_lock_file_env_var():
    """環境変数でlock_fileを変更できることの確認"""
    env = {"JQUANTS_API_RATE_LIMIT_LOCK_FILE": "/tmp/custom_rate.lock"}
    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value={"api_key": "dummy_key"}
    ), patch.dict(client_v2.os.environ, env, clear=False):
        cli = jquantsapi.ClientV2()
        assert cli._rate_limiter is not None
        assert cli._rate_limiter.lock_file == "/tmp/custom_rate.lock"


def test_rate_limiter_from_config():
    """設定ファイルからレートリミット設定を読み込めることの確認"""
    config = {
        "api_key": "dummy_key",
        "rate_limit": 120,
        "rate_limit_per": 60.0,
        "rate_limit_lock_file": "/tmp/config_rate.lock",
    }
    with patch.object(jquantsapi.ClientV2, "_load_config", return_value=config):
        cli = jquantsapi.ClientV2()
        assert cli._rate_limiter is not None
        assert cli._rate_limiter.rate == 120.0
        assert cli._rate_limiter.per == 60.0
        assert cli._rate_limiter.lock_file == "/tmp/config_rate.lock"


def test_rate_limiter_env_overrides_config():
    """環境変数が設定ファイルの値を上書きすることの確認"""
    config = {
        "api_key": "dummy_key",
        "rate_limit": 120,
        "rate_limit_per": 60.0,
    }
    env = {"JQUANTS_API_RATE_LIMIT": "500"}
    with patch.object(
        jquantsapi.ClientV2, "_load_config", return_value=config
    ), patch.dict(client_v2.os.environ, env, clear=False):
        cli = jquantsapi.ClientV2()
        assert cli._rate_limiter is not None
        assert cli._rate_limiter.rate == 500.0  # 環境変数で上書き
        assert cli._rate_limiter.per == 60.0  # 設定ファイルの値
