import json
import os
import time

import pytest

from jquantsapi.rate_limiter import SharedRateLimiter


@pytest.fixture
def limiter(tmp_path):
    lock_file = str(tmp_path / "test_rate.lock")
    return SharedRateLimiter(rate=5, per=1.0, lock_file=lock_file)


class TestInit:
    def test_default_values(self):
        lim = SharedRateLimiter(rate=10)
        assert lim.rate == 10
        assert lim.per == 1.0
        assert lim.lock_file == "/tmp/jquants_rate.lock"
        assert lim.state_file == "/tmp/jquants_rate.lock.state"

    def test_custom_values(self, tmp_path):
        lock = str(tmp_path / "custom.lock")
        lim = SharedRateLimiter(rate=3, per=2.0, lock_file=lock)
        assert lim.rate == 3
        assert lim.per == 2.0
        assert lim.lock_file == lock
        assert lim.state_file == lock + ".state"


class TestLoadState:
    def test_no_state_file(self, limiter):
        state = limiter._load_state()
        assert state["tokens"] == 5
        assert "last" in state

    def test_existing_state_file(self, limiter):
        saved = {"tokens": 2.5, "last": 1000.0}
        with open(limiter.state_file, "w") as f:
            json.dump(saved, f)
        state = limiter._load_state()
        assert state["tokens"] == 2.5
        assert state["last"] == 1000.0


class TestSaveState:
    def test_state_persisted(self, limiter):
        limiter._save_state({"tokens": 3, "last": 999.0})
        with open(limiter.state_file) as f:
            state = json.load(f)
        assert state["tokens"] == 3
        assert state["last"] == 999.0


class TestAcquire:
    def test_single_acquire(self, limiter):
        limiter.acquire()

    def test_multiple_acquires_within_rate(self, limiter):
        for _ in range(5):
            limiter.acquire()

    def test_tokens_decrease(self, limiter):
        limiter.acquire()
        with open(limiter.state_file) as f:
            state = json.load(f)
        assert state["tokens"] < 5

    def test_timeout_raises(self, tmp_path):
        lock_file = str(tmp_path / "timeout.lock")
        lim = SharedRateLimiter(rate=1, per=10.0, lock_file=lock_file)
        lim.acquire()
        with pytest.raises(TimeoutError):
            lim.acquire(timeout=0.1)

    def test_tokens_replenish(self, tmp_path):
        lock_file = str(tmp_path / "replenish.lock")
        lim = SharedRateLimiter(rate=2, per=0.2, lock_file=lock_file)
        lim.acquire()
        lim.acquire()
        # トークンが回復するのを待つ
        time.sleep(0.15)
        lim.acquire()  # 回復後なので成功するはず

    def test_state_file_created(self, limiter):
        assert not os.path.exists(limiter.state_file)
        limiter.acquire()
        assert os.path.exists(limiter.state_file)

    def test_lock_file_created(self, limiter):
        assert not os.path.exists(limiter.lock_file)
        limiter.acquire()
        assert os.path.exists(limiter.lock_file)
