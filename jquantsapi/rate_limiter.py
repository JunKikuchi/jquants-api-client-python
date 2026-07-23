import json
import os
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover
    # Windows には fcntl がないため、プロセス内ロックにフォールバックする
    fcntl = None  # type: ignore[assignment]

# fcntl が使えない環境でロックファイルパスごとに共有するプロセス内ロック
_local_locks: dict[str, threading.Lock] = {}
_local_locks_guard = threading.Lock()


def _get_local_lock(lock_file: str) -> threading.Lock:
    with _local_locks_guard:
        if lock_file not in _local_locks:
            _local_locks[lock_file] = threading.Lock()
        return _local_locks[lock_file]


class SharedRateLimiter:
    """
    トークンバケット方式のレートリミッター。

    fcntl.flock によるファイルロックで複数プロセス間の排他制御を行い、
    JSON ファイルでトークン状態を共有する。
    fcntl が利用できない環境 (Windows) ではプロセス内ロックにフォールバックし、
    レートリミットは同一プロセス内でのみ共有される。
    """

    def __init__(
        self, rate: float, per: float = 1.0, lock_file: str = "/tmp/jquants_rate.lock"
    ):
        self.rate = rate  # 最大リクエスト数
        self.per = per  # 時間窓（秒）
        self.lock_file = lock_file
        self.state_file = lock_file + ".state"

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        if fcntl is None:
            with _get_local_lock(self.lock_file):
                yield
        else:
            with open(self.lock_file, "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def _load_state(self) -> dict:
        try:
            with open(self.state_file) as f:
                state = json.load(f)
            tokens = state["tokens"]
            last = state["last"]
            if isinstance(tokens, (int, float)) and isinstance(last, (int, float)):
                return {"tokens": float(tokens), "last": float(last)}
        except (OSError, ValueError, KeyError, TypeError):
            # 状態ファイルが存在しない・破損している場合は初期状態から再開する
            pass
        return {"tokens": self.rate, "last": time.time()}

    def _save_state(self, state: dict) -> None:
        # 書き込み途中でプロセスが落ちても状態ファイルが破損しないようにする
        tmp_file = self.state_file + ".tmp"
        with open(tmp_file, "w") as f:
            json.dump(state, f)
        os.replace(tmp_file, self.state_file)

    def _try_acquire(self) -> Optional[float]:
        """
        トークン取得を1回試行する。

        Returns:
            None: トークンを取得できた場合
            float: 取得できなかった場合の推奨待機時間（秒）
        """
        with self._exclusive_lock():
            state = self._load_state()
            now = time.time()
            # 時計が巻き戻った場合にトークンが減らないよう 0 でクランプする
            elapsed = max(0.0, now - state["last"])
            state["tokens"] = min(
                self.rate, state["tokens"] + elapsed * (self.rate / self.per)
            )
            state["last"] = now

            if state["tokens"] >= 1:
                state["tokens"] -= 1
                self._save_state(state)
                return None
            wait = (1 - state["tokens"]) / (self.rate / self.per)
            self._save_state(state)
            return wait

    def acquire(self, timeout: Optional[float] = None) -> None:
        """
        トークンを1つ取得する。トークンが利用可能になるまでブロックする。

        Args:
            timeout: 最大待機時間（秒）。超過すると TimeoutError を送出。
                     省略時は時間窓 (per) の3倍と60秒の大きい方を使用。
        """
        if timeout is None:
            timeout = max(60.0, self.per * 3)
        deadline = time.time() + timeout
        while True:
            wait = self._try_acquire()
            if wait is None:
                return  # OK
            if time.time() + wait > deadline:
                raise TimeoutError("Rate limit acquire timeout")
            time.sleep(wait)
