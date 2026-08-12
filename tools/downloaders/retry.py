"""HTTP 下载重试（429 / rate limit）。"""
from __future__ import annotations

import time
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


def is_rate_limit_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "429" in msg:
        return True
    needles = (
        "rate limit",
        "rate limited",
        "too many requests",
        "ratelimit",
        "throttle",
    )
    return any(n in msg for n in needles)


def call_with_retry(
    fn: Callable[[], T],
    *,
    retries: int = 5,
    base_sleep: float = 1.0,
    label: str = "",
    on_retry: Optional[Callable[[int, float, BaseException], None]] = None,
) -> T:
    """
    执行 fn；遇限流错误则指数退避重试。

    retries: 额外重试次数（总尝试 = retries + 1）
    base_sleep: 首次退避秒数，之后 *2
    """
    last: Optional[BaseException] = None
    attempts = max(0, int(retries)) + 1
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            if not is_rate_limit_error(e) or attempt >= attempts - 1:
                raise
            wait = float(base_sleep) * (2**attempt)
            if on_retry:
                on_retry(attempt + 1, wait, e)
            else:
                tag = f" {label}" if label else ""
                print(
                    f"[429]{tag} 第 {attempt + 1}/{retries} 次重试，"
                    f"休眠 {wait:.1f}s — {e}"
                )
            time.sleep(wait)
    assert last is not None
    raise last
