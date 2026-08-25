"""多交易对匹配表：CSV 配置，盘口/账户按所共享、按品种拆分。"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PairSpec:
    name: str
    symbol_a: str
    symbol_b: str
    qty: float
    max_lots: int
    fee_mult: float
    enabled: bool = True
    note: str = ""

    def book_a(self) -> str:
        return book_key("a", self.symbol_a)

    def book_b(self) -> str:
        return book_key("b", self.symbol_b)


def book_key(slot: str, symbol: str) -> str:
    return f"{slot}:{symbol}"


def load_pairs(path: Path) -> List[PairSpec]:
    if not path.is_file():
        raise FileNotFoundError(f"找不到匹配表 {path}")
    rows: List[PairSpec] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(_skip_comment_rows(fh))
        if reader.fieldnames is None:
            return rows
        for raw in reader:
            if not raw:
                continue
            name = str(raw.get("name") or "").strip()
            sa = str(raw.get("symbol_a") or "").strip()
            sb = str(raw.get("symbol_b") or "").strip()
            if not name or not sa or not sb:
                continue
            enabled = str(raw.get("enabled") or "1").strip().lower() not in (
                "0",
                "false",
                "no",
                "off",
            )
            rows.append(
                PairSpec(
                    name=name,
                    symbol_a=sa,
                    symbol_b=sb,
                    qty=max(1e-12, float(raw.get("qty") or 0.001)),
                    max_lots=max(1, int(float(raw.get("max_lots") or 5))),
                    fee_mult=max(1.0, float(raw.get("fee_mult") or 1.2)),
                    enabled=enabled,
                    note=str(raw.get("note") or "").strip(),
                )
            )
    return rows


def _skip_comment_rows(fh):
    for line in fh:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        yield line


def enabled_pairs(specs: List[PairSpec]) -> List[PairSpec]:
    return [p for p in specs if p.enabled]


def symbols_for_slot(specs: List[PairSpec], slot: str) -> List[str]:
    out: List[str] = []
    seen = set()
    for spec in enabled_pairs(specs):
        sym = spec.symbol_a if slot == "a" else spec.symbol_b
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def peer_map(specs: List[PairSpec]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for spec in enabled_pairs(specs):
        ka, kb = spec.book_a(), spec.book_b()
        mapping[ka] = kb
        mapping[kb] = ka
    return mapping


def pair_venues(
    base: Dict[str, Dict[str, Any]], spec: PairSpec
) -> Dict[str, Dict[str, Any]]:
    a = dict(base["a"])
    b = dict(base["b"])
    a["symbol"] = spec.symbol_a
    b["symbol"] = spec.symbol_b
    return {"a": a, "b": b}


def resolve_pairs_path(vs_cfg: Dict[str, Any], strategy_dir: Path) -> Optional[Path]:
    raw = vs_cfg.get("pairs_csv")
    if raw in (None, "", False):
        return None
    path = Path(str(raw))
    if not path.is_absolute():
        path = (strategy_dir / path).resolve()
    return path
