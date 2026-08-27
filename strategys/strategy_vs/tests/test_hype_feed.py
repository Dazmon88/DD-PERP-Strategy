"""Hype / HIP-3 接入：成交解析、dex 推断、盘口键、Maker TIF。

跑法（仓库根目录）:
  venv/bin/python -m pytest strategys/strategy_vs/tests/test_hype_feed.py -q
  venv/bin/python strategys/strategy_vs/tests/test_hype_feed.py
"""
import asyncio
import sys
import time
from decimal import Decimal
from pathlib import Path

STRATEGY_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(STRATEGY_DIR), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.hype_adapter import (  # noqa: E402
    hype_dex_of,
    is_hype_unified,
    normalize_hype_symbol,
    resolve_hype_tif,
    spot_equity_from_state,
    spot_marks_from_ctxs,
)
from adapters.hype_stream import bbo_from_l2, msg_key, sub_key  # noqa: E402
from accounts import hype_fills_snapshot, parse_hype_fill_coins  # noqa: E402
from feeds import (  # noqa: E402
    Quote,
    QuoteBook,
    _hype_inject_dexs,
    _same_symbol,
    slot_book_key,
)
from pairs import PairSpec, book_key, load_pairs, peer_map  # noqa: E402


def test_normalize_keeps_builder_prefix():
    assert normalize_hype_symbol("io:ANTH") == "io:ANTH"
    assert normalize_hype_symbol(" io:SNDK ") == "io:SNDK"
    assert hype_dex_of("io:ANTH") == "io"
    assert hype_dex_of("BTC") == ""


def test_inject_perp_dexs_from_symbol():
    cfg = _hype_inject_dexs({"exchange": "hype", "symbol": "io:ANTH"})
    assert cfg["perp_dexs"] == ["io"]
    kept = _hype_inject_dexs({"symbol": "io:SNDK", "perp_dexs": ["xyz"]})
    assert kept["perp_dexs"] == ["xyz"]


def test_tif_post_only_is_alo():
    assert resolve_hype_tif("gtc", post_only=True) == "Alo"
    assert resolve_hype_tif("alo") == "Alo"
    assert resolve_hype_tif("gtc") == "Gtc"
    assert resolve_hype_tif("ioc") == "Ioc"


def test_pairs_csv_and_book_keys():
    specs = load_pairs(STRATEGY_DIR / "pairs_hype.csv")
    by_name = {s.name: s for s in specs}
    assert set(by_name) == {"ANTH", "SNDK"}
    anth, sndk = by_name["ANTH"], by_name["SNDK"]
    assert anth.symbol_a == "ANTHROPIC"
    assert anth.symbol_b == "io:ANTH"
    assert anth.book_a() == "a:ANTHROPIC"
    assert anth.book_b() == "b:io:ANTH"
    assert sndk.symbol_a == "SNDK"
    assert sndk.symbol_b == "io:SNDK"
    peers = peer_map(specs)
    assert peers["a:ANTHROPIC"] == "b:io:ANTH"
    assert peers["b:io:SNDK"] == "a:SNDK"


def test_symbol_match_does_not_cross_anth_sndk():
    assert _same_symbol("io:ANTH", "io:ANTH")
    assert not _same_symbol("io:ANTH", "io:SNDK")


def test_parse_user_fills():
    msg = {
        "channel": "userFills",
        "data": {
            "user": "0xabc",
            "isSnapshot": False,
            "fills": [
                {"coin": "io:ANTH", "sz": "0.01", "side": "B"},
                {"coin": "io:SNDK", "sz": "0.01", "side": "A"},
                {"coin": "io:ANTH", "sz": "0.02", "side": "A"},
            ],
        },
    }
    assert parse_hype_fill_coins(msg) == ["io:ANTH", "io:SNDK"]
    assert hype_fills_snapshot(msg) is False
    snap = {"data": {"isSnapshot": True, "fills": []}}
    assert hype_fills_snapshot(snap) is True
    assert parse_hype_fill_coins(snap) == []


def test_l2_bbo_and_subscription_keys():
    data = {
        "coin": "io:ANTH",
        "levels": [
            [{"px": "2005.0", "sz": "1.2", "n": 1}],
            [{"px": "2005.5", "sz": "0.8", "n": 1}],
        ],
    }
    bid, ask, bid_sz, ask_sz = bbo_from_l2(data)
    assert bid == 2005.0 and ask == 2005.5
    assert bid_sz == 1.2 and ask_sz == 0.8
    assert sub_key({"type": "l2Book", "coin": "io:ANTH"}) == "l2Book:io:anth"
    assert msg_key({"channel": "l2Book", "data": data}) == "l2Book:io:anth"


def test_quote_book_key_with_colon_symbol():
    async def main():
        book = QuoteBook()
        key = slot_book_key("a", "io:ANTH")
        await book.update(
            Quote(
                venue=key,
                exchange="hype",
                symbol="io:ANTH",
                bid=2005.0,
                ask=2005.5,
                ts=time.time(),
                source="wss",
            )
        )
        snap = await book.snapshot()
        return key, snap[key].bid

    key, bid = asyncio.run(main())
    assert key == "a:io:ANTH"
    assert bid == 2005.0


def test_pairspec_colon_survives_book_key():
    spec = PairSpec(
        name="ANTH-SNDK",
        symbol_a="io:ANTH",
        symbol_b="io:SNDK",
        qty=0.01,
        max_lots=2,
        fee_mult=1.2,
    )
    assert book_key("a", spec.symbol_a) == spec.book_a()


def test_info_survives_sparse_spot_token_index():
    """HL 现货 token.index 有空洞；按列表下标取会 IndexError。"""
    from hyperliquid.info import Info

    meta = {"universe": [{"name": "BTC", "szDecimals": 5}]}
    spot_meta = {
        "tokens": [
            {"name": "USDC", "szDecimals": 8, "weiDecimals": 8, "index": 0},
            {"name": "FOO", "szDecimals": 2, "weiDecimals": 8, "index": 610},
        ],
        "universe": [
            {"name": "@465", "index": 0, "tokens": [610, 0]},
        ],
    }
    info = Info(skip_ws=True, meta=meta, spot_meta=spot_meta)
    assert info.name_to_coin["FOO/USDC"] == "@465"
    assert info.asset_to_sz_decimals[10000] == 2


def test_lighter_authed_rejects_protocol_account():
    from feeds import _lighter_authed

    class A:
        def __init__(self, idx):
            self.account_index = idx

    assert not _lighter_authed(A(None))
    assert not _lighter_authed(A(0))
    assert not _lighter_authed(A("0"))
    assert _lighter_authed(A(281474976710463))
    assert is_hype_unified("unifiedAccount")
    assert is_hype_unified('"portfolioMargin"')
    assert not is_hype_unified("disabled")
    assert not is_hype_unified("")


def test_spot_marks_and_unified_equity():
    meta = {
        "tokens": [
            {"name": "USDC", "index": 0},
            {"name": "MAX", "index": 734},
        ],
        "universe": [{"name": "@591", "tokens": [734, 0]}],
    }
    ctxs = [{"markPx": "7.5"}]
    marks = spot_marks_from_ctxs([meta, ctxs])
    assert marks["USDC"] == Decimal("1")
    assert marks["MAX"] == Decimal("7.5")
    eq, av = spot_equity_from_state(
        {
            "balances": [
                {"coin": "USDC", "token": 0, "total": "1.5", "hold": "0.5"},
                {"coin": "MAX", "token": 734, "total": "10", "hold": "0"},
            ],
            "tokenToAvailableAfterMaintenance": [[0, "0.8"]],
        },
        marks,
    )
    assert eq == Decimal("1.5") + Decimal("75")
    assert av == Decimal("0.8")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} 项全部通过")
