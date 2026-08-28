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


def test_flat_opens_opposite_below_lower():
    """空仓跌破下沿开对面：较好一侧是 AB 就开多B，较好一侧是 BA 就开多A。"""
    g = make_grid()
    assert g.desired_lots(7.3 * BP, -9.3 * BP, 0) == -1    # AB 仍较好 → 开多B
    assert g.desired_lots(-9.3 * BP, 7.3 * BP, 0) == 1     # BA 仍较好 → 开多A
    # 再往下按 step 加层（距下沿 3bp → 3 层）
    assert g.desired_lots(5 * BP, -7 * BP, 0) == -3


def test_flat_open_above_upper_captures_better_leg():
    """越上沿开出来的方向，拿到的是较好那条（正）腿。"""
    g = make_grid()
    for i in range(-400, 401):
        ab = i * 0.1 * BP
        ba = -ab - 2 * BP                 # AB + BA = -来回费
        for a, b in ((ab, ba), (ba, ab)):
            t = g.desired_lots(a, b, 0)
            mag = max(a, b)
            if t and mag > g.upper:
                got = a if t > 0 else b
                assert got > 0, f"AB={a/BP:+.1f} BA={b/BP:+.1f} 开{t:+d} 却吃到 {got/BP:+.1f}bp"
                assert (t > 0) == (a >= b)


def test_flat_open_below_lower_is_opposite_of_better():
    g = make_grid()
    for i in range(-400, 401):
        ab = i * 0.1 * BP
        ba = -ab - 2 * BP
        for a, b in ((ab, ba), (ba, ab)):
            t = g.desired_lots(a, b, 0)
            mag = max(a, b)
            better = 1 if a >= b else -1
            if t and mag < g.lower:
                assert (1 if t > 0 else -1) == -better


def test_flat_swap_antisymmetric():
    g = make_grid()
    for i in range(-400, 401):
        ab = i * 0.1 * BP
        ba = -ab - 2 * BP
        if ab == ba:
            continue
        assert g.desired_lots(ab, ba, 0) == -g.desired_lots(ba, ab, 0)


# --- 持仓 -------------------------------------------------------------

def test_holding_adds_above_upper():
    g = make_grid()
    assert g.desired_lots(22.5 * BP, -24.5 * BP, 1) == 3   # 越上沿 2 个 step
    assert g.desired_lots(-24.5 * BP, 22.5 * BP, -1) == -3


def test_holding_flattens_past_center():
    """贴中枢持有；多A 现价差 < 中枢才平，下沿多B 现价差 > 中枢才平。"""
    g = make_grid()
    center = g.center
    assert g.desired_lots(center, -center - 2 * BP, 2) == 2          # 多A 贴中枢持有
    assert g.desired_lots(5 * BP, -7 * BP, 2) == 0                    # 多A 已低于中枢
    g.flatten_sign = 0
    assert g.desired_lots(-center - 2 * BP, center, -2) == -2         # 多B 富腿贴中枢持有
    g.flatten_sign = 0
    assert g.desired_lots(-center - 2 * BP, center - BP, -2) == 0     # 富腿跌破中枢
    g.flatten_sign = 0
    assert g.desired_lots(center, -center - 2 * BP, -2) == -2         # 下沿多B 贴中枢持有
    g.flatten_sign = 0
    assert g.desired_lots(center + BP, -center - 3 * BP, -2) == 0     # 溢价升破中枢


def test_flatten_by_position_vs_center():
    """带宽 85.6–99.0、中枢 92.3：多B 等 bp>中枢，多A 等 bp<中枢。"""
    g = make_grid(lower=85.6 * BP, upper=99.0 * BP, max_lots=10)
    assert abs(g.center - 92.3 * BP) < 1e-15
    # 下沿开的多B（B+ A-）：65.5 满仓持有，92.3 仍持有，92.4 才平（多A空B）
    assert g.desired_lots(65.5 * BP, -74.0 * BP, -10) == -10
    assert g.desired_lots(92.3 * BP, -94.3 * BP, -1) == -1
    assert g.desired_lots(92.4 * BP, -94.4 * BP, -1) == 0
    g.flatten_sign = 0
    # 上沿开的多A（A+ B-）：102 满仓持有，92.3 仍持有，92.2 才平（多B空A）
    assert g.desired_lots(102.0 * BP, -104.0 * BP, 10) == 10
    assert g.desired_lots(92.3 * BP, -94.3 * BP, 1) == 1
    assert g.desired_lots(92.2 * BP, -94.2 * BP, 1) == 0


def test_holding_stays_between_center_and_upper():
    g = make_grid()
    # center=14，upper=20：16 在止盈与加层之间
    assert g.desired_lots(16 * BP, -18 * BP, 2) == 2
    assert g.desired_lots(-18 * BP, 16 * BP, -2) == -2


def test_fade_short_adds_further_below_lower():
    """下沿开的多B：溢价再往下可加层，未回到中枢则不平。"""
    g = make_grid()
    assert g.desired_lots(10 * BP, -12 * BP, -2) == -2     # lower=8 < 10 < center=14
    assert g.desired_lots(5 * BP, -7 * BP, -2) == -3       # 再往下距下沿 3bp → 3 层


def test_rich_hold_swap_antisymmetric():
    """富腿持仓（盯较好那条）对调 AB/BA 后符号相反。"""
    g = make_grid()
    for i in range(0, 401):
        edge = i * 0.1 * BP
        other = -edge - 2 * BP
        if edge < other:
            continue
        for lots in (1, 2, 5):
            g.flatten_sign = 0
            long_t = g.desired_lots(edge, other, lots)
            g.flatten_sign = 0
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
    assert flat.next_add == g.upper          # 空仓：开较好一侧看上沿
    assert flat.next_reduce == g.lower       # 空仓：开对面看下沿

    held = g.peek(16 * BP, -18 * BP, 2)
    assert held.next_add == g.upper + 2 * g.step
    assert held.next_reduce == g.center      # 持仓止盈是中枢

    full = g.peek(16 * BP, -18 * BP, 3)
    assert full.next_add is None             # 满仓不再加
    assert full.next_reduce == g.center

    fade = g.peek(10 * BP, -12 * BP, 2)      # lots>0 时仍盯 AB 加层线
    assert fade.next_reduce == g.center
    g.flatten_sign = 0
    fade_s = g.peek(10 * BP, -12 * BP, -2)
    assert fade_s.next_add == g.lower - 2 * g.step
    assert fade_s.next_reduce == g.center


def test_peek_action_labels():
    g = make_grid()
    assert g.peek(14 * BP, -16 * BP, 0).action == "观望"
    assert g.peek(25 * BP, -27 * BP, 0).action == "开仓"
    assert g.peek(7.3 * BP, -9.3 * BP, 0).action == "开仓"
    assert g.peek(16 * BP, -18 * BP, 2).action == "持有"
    assert g.peek(25 * BP, -27 * BP, 1).action == "加仓"
    assert g.peek(5 * BP, -7 * BP, 2).action == "减仓"     # 回到中枢：平，不反向


def test_flatten_latch_until_empty():
    """穿越中枢后锁平：价差反弹也不留残层，空仓才解除。"""
    g = make_grid()
    assert g.desired_lots(13 * BP, -15 * BP, 2) == 0          # 多A bp<中枢
    assert g.flatten_sign == 1
    # 减一层后价差回到上沿内侧，仍必须继续平
    assert g.desired_lots(16 * BP, -18 * BP, 1) == 0
    assert g.peek(16 * BP, -18 * BP, 1).action == "减仓"
    assert g.peek(16 * BP, -18 * BP, 1).next_add is None
    assert g.rest_ok(-1, 16 * BP, -18 * BP, 1) is True
    assert g.rest_ok(1, 16 * BP, -18 * BP, 1) is False
    # 空仓解锁，之后可以重新开
    assert g.desired_lots(16 * BP, -18 * BP, 0) == 0
    assert g.flatten_sign == 0
    assert g.desired_lots(25 * BP, -27 * BP, 0) == 5

    g2 = make_grid()
    assert g2.desired_lots(15 * BP, -17 * BP, -2) == 0        # 下沿多B bp>中枢
    assert g2.flatten_sign == -1
    assert g2.desired_lots(10 * BP, -12 * BP, -1) == 0
    assert g2.desired_lots(10 * BP, -12 * BP, 0) == 0
    assert g2.flatten_sign == 0


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


# --- 有仓冻带，满仓也不上移 -------------------------------------------

def test_hold_below_max_does_not_trail():
    """未满仓：上沿冻住，价差再走也不把下沿抬上来，这样才能继续加层。"""
    g = make_grid(max_lots=5)
    g.observe([50 * BP] * 5, [-52 * BP] * 5, 2, edge=50 * BP)
    assert abs(g.lower - 8 * BP) < 1e-15
    assert abs(g.upper - 20 * BP) < 1e-15
    assert abs(g.center - 14 * BP) < 1e-15
    assert g.frozen
    assert "加层" in g.note


def test_max_lots_freezes_band_no_trail():
    """满仓也冻带：中枢保持开仓时的止盈，不随高点上移。"""
    g = make_grid(max_lots=2)
    g.observe([], [], 2, edge=40 * BP)
    assert abs(g.lower - 8 * BP) < 1e-15
    assert abs(g.upper - 20 * BP) < 1e-15
    assert abs(g.center - 14 * BP) < 1e-15
    assert g.frozen
    assert "上移" not in g.note
    # 贴上沿仍持有；跌破中枢才平，不翻面
    assert g.desired_lots(40 * BP, -42 * BP, 2) == 2
    assert g.peek(40 * BP, -42 * BP, 2).action == "持有"
    assert g.desired_lots(13 * BP, -15 * BP, 2) == 0
    assert g.peek(13 * BP, -15 * BP, 2).action == "减仓"


def test_max_lots_freeze_does_not_drop_or_lift():
    g = make_grid(max_lots=2)
    locked = g.lower
    g.observe([], [], 2, edge=40 * BP)
    assert abs(g.lower - locked) < 1e-12
    g.observe([], [], 2, edge=30 * BP)
    assert abs(g.lower - locked) < 1e-12


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
