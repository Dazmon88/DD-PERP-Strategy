"""带宽时间采样、资金费只平、一层未齐收尾。

跑法（仓库根目录）:
  venv/bin/python -m pytest strategys/strategy_vs/tests/test_exec_guards.py -q
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

STRATEGY_DIR = Path(__file__).resolve().parents[1]
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from hedge import layer_finish_kind  # noqa: E402
from spread import (  # noqa: E402
    SpreadWindow,
    _in_circular_range,
    flatten_block_reason,
)


def test_window_skips_ticks_inside_interval():
    w = SpreadWindow(maxlen=100, min_interval_sec=0.5)
    w.add(1.0, now=1000.0)
    w.add(2.0, now=1000.2)
    w.add(3.0, now=1000.5)
    assert [p for _, p in w._samples] == [1.0, 3.0]


def test_window_load_thins_dense_history():
    w = SpreadWindow(maxlen=100, min_interval_sec=1.0)
    rows = [[1000.0 + i * 0.1, float(i)] for i in range(50)]
    n = w.load(rows)
    assert n == 5
    assert w._samples[0][0] == 1000.0
    assert w._samples[-1][0] == 1004.0


def test_funding_window_around_utc_midnight():
    cfg = {
        "funding_hours_utc": [0, 8, 16],
        "minutes_before": 20,
        "minutes_after": 10,
    }
    in_ts = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc).timestamp()
    early = datetime(2026, 8, 26, 23, 40, tzinfo=timezone.utc).timestamp()
    late = datetime(2026, 8, 27, 0, 9, tzinfo=timezone.utc).timestamp()
    out_ts = datetime(2026, 8, 27, 0, 10, tzinfo=timezone.utc).timestamp()
    noon = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc).timestamp()
    assert "资金费00:00UTC前后只平" in flatten_block_reason(cfg, in_ts)
    assert flatten_block_reason(cfg, early)
    assert flatten_block_reason(cfg, late)
    assert flatten_block_reason(cfg, out_ts) == ""
    assert flatten_block_reason(cfg, noon) == ""


def test_circular_hour_range():
    assert _in_circular_range(23, 23, 8, 24)
    assert _in_circular_range(0, 23, 8, 24)
    assert _in_circular_range(7, 23, 8, 24)
    assert not _in_circular_range(8, 23, 8, 24)
    assert not _in_circular_range(12, 23, 8, 24)


def test_layer_finish_never_adopts_reverse():
    assert layer_finish_kind(want_n=-1, got_n=-1, hedged=True, b_moved=True) == "ok"
    # 减仓 1→-1：对锁但层数反了，必须拧平
    assert layer_finish_kind(want_n=0, got_n=-1, hedged=True, b_moved=True) == "unwind"
    assert layer_finish_kind(want_n=-1, got_n=1, hedged=True, b_moved=True) == "unwind"
    assert layer_finish_kind(want_n=-1, got_n=None, hedged=False, b_moved=True) == "unwind"
    assert layer_finish_kind(want_n=-1, got_n=None, hedged=False, b_moved=False) == "abort"
