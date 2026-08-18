"""模拟盘开平记录，追加写入 CSV 方便审核。"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

HEADERS = [
    "时间",
    "动作",
    "方向",
    "层前",
    "层后",
    "数量",
    "现净bp",
    "下沿bp",
    "上沿bp",
    "中枢bp",
    "来回bp",
    "AB净bp",
    "BA净bp",
    "A价",
    "B价",
    "开仓次数",
    "平仓次数",
    "备注",
]


def _bp(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{float(value) * 1e4:.4f}"


def _num(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{float(value):.8g}"


class PaperJournal:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.opens = 0
        self.closes = 0
        self.last = ""
        self._load_counts()

    def _load_counts(self) -> None:
        if not self.path.is_file():
            return
        try:
            with open(self.path, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    action = str(row.get("动作") or "")
                    if action == "开仓":
                        self.opens += 1
                    elif action == "平仓":
                        self.closes += 1
        except OSError:
            return

    def _ensure_header(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_file() and self.path.stat().st_size > 0:
            return
        with open(self.path, "w", encoding="utf-8-sig", newline="") as fh:
            csv.DictWriter(fh, fieldnames=HEADERS).writeheader()

    def record(
        self,
        *,
        action: str,
        delta: int,
        lots_before: int,
        lots_after: int,
        qty: float,
        mag: Optional[float] = None,
        lower: Optional[float] = None,
        upper: Optional[float] = None,
        center: Optional[float] = None,
        cost: Optional[float] = None,
        ab_pct: Optional[float] = None,
        ba_pct: Optional[float] = None,
        px_a: Optional[float] = None,
        px_b: Optional[float] = None,
        note: str = "",
    ) -> None:
        if action == "开仓":
            self.opens += 1
        elif action == "平仓":
            self.closes += 1
        if delta > 0:
            side = "买A卖B"
        else:
            side = "买B卖A"
        row: Dict[str, Any] = {
            "时间": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "动作": action,
            "方向": side,
            "层前": lots_before,
            "层后": lots_after,
            "数量": _num(qty),
            "现净bp": _bp(mag),
            "下沿bp": _bp(lower),
            "上沿bp": _bp(upper),
            "中枢bp": _bp(center),
            "来回bp": _bp(cost),
            "AB净bp": _bp(ab_pct),
            "BA净bp": _bp(ba_pct),
            "A价": _num(px_a),
            "B价": _num(px_b),
            "开仓次数": self.opens,
            "平仓次数": self.closes,
            "备注": note,
        }
        self._ensure_header()
        with open(self.path, "a", encoding="utf-8-sig", newline="") as fh:
            csv.DictWriter(fh, fieldnames=HEADERS).writerow(row)
        self.last = f"{action} {side} 开{self.opens}平{self.closes}"
