import fcntl
import json
import os
import time


class SharedRateLimiter:
    """
    トークンバケット方式のレートリミッター。

    fcntl.flock によるファイルロックで複数プロセス間の排他制御を行い、
    JSON ファイルでトークン状態を共有する。
    """

    def __init__(
        self, rate: float, per: float = 1.0, lock_file: str = "/tmp/jquants_rate.lock"
    ):
        self.rate = rate  # 最大リクエスト数
        self.per = per  # 時間窓（秒）
        self.lock_file = lock_file
        self.state_file = lock_file + ".state"

    def _load_state(self) -> dict:
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                return json.load(f)
        return {"tokens": self.rate, "last": time.time()}

    def _save_state(self, state: dict) -> None:
        with open(self.state_file, "w") as f:
            json.dump(state, f)

    def acquire(self, timeout: float = 60.0) -> None:
        """
        トークンを1つ取得する。トークンが利用可能になるまでブロックする。

        Args:
            timeout: 最大待機時間（秒）。超過すると TimeoutError を送出。
        """
        deadline = time.time() + timeout
        with open(self.lock_file, "w") as lock:
            while True:
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    state = self._load_state()
                    now = time.time()
                    elapsed = now - state["last"]
                    state["tokens"] = min(
                        self.rate, state["tokens"] + elapsed * (self.rate / self.per)
                    )
                    state["last"] = now

                    if state["tokens"] >= 1:
                        state["tokens"] -= 1
                        self._save_state(state)
                        return  # OK
                    else:
                        wait = (1 - state["tokens"]) / (self.rate / self.per)
                        self._save_state(state)
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)

                if time.time() + wait > deadline:
                    raise TimeoutError("Rate limit acquire timeout")
                time.sleep(wait)
