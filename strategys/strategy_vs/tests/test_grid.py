"""SpreadGrid 网格判定的回归测试。

跑法（仓库根目录）:
  venv/bin/python -m pytest strategys/strategy_vs/tests/test_grid.py -q
  venv/bin/python strategys/strategy_vs/tests/test_grid.py
"""
import sys
from pathlib import Path

STRATEGY_DIR = Path(__file__).resolve().parents[1]
if str(STRATEGY_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_DIR))

from spread import SpreadGrid  # noqa: E402

BP = 1e-4


def make_grid(lower=8 * BP, upper=20 * BP, max_lots=5, step=1 * BP):
    g = SpreadGrid(fee_a=0.0, fee_b=0.0, fee_mult=1.2, min_samples=1,
                   max_lots=max_lots, step=step)
    g.ready = True
    g.lower, g.upper = lower, upper
    g.center, g.width, g.cost = (lower + upper) / 2, upper - lower, 2 * BP
    return g


# --- 空仓 -------------------------------------------------------------

def test_flat_opens_better_leg_above_upper():
    g = make_grid()
    # 刚越上沿 0.5 个 step → 1 层
    assert g.desired_lots(20.5 * BP, -22.5 * BP, 0) == 1     # AB 好 → 多A
    assert g.desired_lots(-22.5 * BP, 20.5 * BP, 0) == -1    # BA 好 → 多B
    # 高出 5 个 step → 5 层（按 step 数层）
    assert g.desired_lots(25 * BP, -27 * BP, 0) == 5


def test_flat_holds_when_inside_band():
    g = make_grid()
    assert g.desired_lots(14 * BP, -16 * BP, 0) == 0


def test_flat_never_opens_worse_leg_below_lower():
    """回归：空仓时 edge=max(AB,BA)，跌破下沿是"两边都差"，必须观望。

    修复前这里会返回 +1，即买 AB 这条 -9.3bp 的差腿。
    """
    g = make_grid()
    assert g.desired_lots(-9.3 * BP, 7.3 * BP, 0) == 0
    assert g.desired_lots(7.3 * BP, -9.3 * BP, 0) == 0


def test_flat_open_never_captures_negative_edge():
    """扫一遍：空仓开出来的方向，拿到的净价差不可能是负的。"""
    g = make_grid()
    for i in range(-400, 401):
        ab = i * 0.1 * BP
        ba = -ab - 2 * BP                 # AB + BA = -来回费
        for a, b in ((ab, ba), (ba, ab)):
            t = g.desired_lots(a, b, 0)
            if t:
                got = a if t > 0 else b
                assert got > 0, f"AB={a/BP:+.1f} BA={b/BP:+.1f} 开{t:+d} 却吃到 {got/BP:+.1f}bp"


# --- 持仓 -------------------------------------------------------------

def test_holding_adds_above_upper():
    g = make_grid()
    assert g.desired_lots(22.5 * BP, -24.5 * BP, 1) == 3   # 越上沿 2 个 step
    assert g.desired_lots(-24.5 * BP, 22.5 * BP, -1) == -3


def test_holding_reverses_below_lower():
    g = make_grid()
    assert g.desired_lots(5 * BP, -7 * BP, 2) == -3        # 多A 跌破下沿 → 反手
    assert g.desired_lots(-7 * BP, 5 * BP, -2) == 3


def test_holding_stays_inside_band():
    g = make_grid()
    assert g.desired_lots(14 * BP, -16 * BP, 2) == 2      # 多A 看 AB=14，带内
    assert g.desired_lots(-16 * BP, 14 * BP, -2) == -2    # 多B 看 BA=14，带内


def test_long_short_symmetric():
    g = make_grid()
    for i in range(-400, 401):
        edge = i * 0.1 * BP
        other = -edge - 2 * BP
        for lots in (1, 2, 5):
            long_t = g.desired_lots(edge, other, lots)
            short_t = g.desired_lots(other, edge, -lots)
            assert long_t == -short_t, f"edge={edge/BP:+.1f} lots={lots} 多空不对称"


def test_over_limit_trims_to_max():
    g = make_grid(max_lots=2)
    assert g.desired_lots(25 * BP, -27 * BP, 5) == 2
    assert g.desired_lots(-27 * BP, 25 * BP, -5) == -2


def test_not_ready_returns_flat():
    g = make_grid()
    g.ready = False
    assert g.desired_lots(25 * BP, -27 * BP, 0) == 0


# --- peek 的门槛要和 desired_lots 一致 --------------------------------

def test_next_levels_match_desired_lots():
    g = make_grid(max_lots=3)
    flat = g.peek(14 * BP, -16 * BP, 0)
    assert flat.next_add == g.upper          # 空仓：开仓线就是上沿
    assert flat.next_reduce is None          # 空仓没有反手线

    held = g.peek(14 * BP, -16 * BP, 2)
    assert held.next_add == g.upper + 2 * g.step
    assert held.next_reduce == g.lower       # 反手线固定是下沿，不含 step

    full = g.peek(14 * BP, -16 * BP, 3)
    assert full.next_add is None             # 满仓不再加
    assert full.next_reduce == g.lower


def test_peek_action_labels():
    g = make_grid()
    assert g.peek(14 * BP, -16 * BP, 0).action == "观望"
    assert g.peek(25 * BP, -27 * BP, 0).action == "开仓"
    assert g.peek(14 * BP, -16 * BP, 2).action == "持有"
    assert g.peek(25 * BP, -27 * BP, 1).action == "加仓"
    assert g.peek(5 * BP, -7 * BP, 2).action == "反向"


def test_rest_ok_agrees_with_desired_lots():
    g = make_grid()
    for i in range(-300, 301):
        ab = i * 0.1 * BP
        ba = -ab - 2 * BP
        for lots in (-2, -1, 0, 1, 2):
            target = g.desired_lots(ab, ba, lots)
            for d in (-1, 1):
                want = target > lots if d > 0 else target < lots
                assert g.rest_ok(d, ab, ba, lots) is want


# --- 满仓后带宽上移 -----------------------------------------------------

def test_hold_below_max_does_not_trail():
    """未满仓：上沿冻住，价差再走也不把下沿抬上来，这样才能继续加层。"""
    g = make_grid(max_lots=5)
    g.observe([50 * BP] * 5, [-52 * BP] * 5, 2, edge=50 * BP)
    assert abs(g.lower - 8 * BP) < 1e-15
    assert abs(g.upper - 20 * BP) < 1e-15
    assert g.frozen
    assert "加层" in g.note


def test_max_lots_trails_band_up():
    """满仓后下沿跟到 现价-带宽，反向不再要求回到入场时的下沿。"""
    g = make_grid(max_lots=2)
    width = g.width
    g.observe([], [], 2, edge=40 * BP)
    assert abs(g.lower - (40 * BP - width)) < 1e-12
    assert abs(g.upper - 40 * BP) < 1e-12
    assert "上移" in g.note
    # 现价贴上沿 → 持有；跌破新下沿才反向
    assert g.desired_lots(40 * BP, -42 * BP, 2) == 2
    assert g.peek(40 * BP, -42 * BP, 2).action == "持有"
    below = g.lower - 0.1 * BP
    assert g.desired_lots(below, -below - 2 * BP, 2) < 0
    assert g.peek(below, -below - 2 * BP, 2).action == "反向"


def test_max_lots_trail_does_not_drop():
    """跟踪只上移：价差回落时下沿不跟着掉，否则反向门槛又被推远。"""
    g = make_grid(max_lots=2)
    width = g.width
    g.observe([], [], 2, edge=40 * BP)
    locked = g.lower
    g.observe([], [], 2, edge=30 * BP)
    assert abs(g.lower - locked) < 1e-12
    assert g.lower > 30 * BP - width


def test_flat_observe_unfreezes():
    g = make_grid()
    g.observe([], [], 5, edge=40 * BP)
    assert g.frozen
    g.observe([14 * BP] * 8, [-16 * BP] * 8, 0)
    assert not g.frozen
    assert g.lower is not None
    assert g.upper > g.lower


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} 项全部通过")
