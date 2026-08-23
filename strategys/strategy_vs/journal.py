"""模拟盘开平记录，追加写入 CSV 方便审核。"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HEADERS = [
    "时间",
    "动作",
    "方向",
    "层前",
    "层后",
    "数量",
    "价差bp",
    "价差%",
    "现净bp",
    "下沿bp",
    "上沿bp",
    "中枢bp",
    "来回bp",
    "AB净bp",
    "BA净bp",
    "A价",
    "B价",
    "A仓前",
    "A仓后",
    "B仓前",
    "B仓后",
    "A侧",
    "B侧",
    "A下单次数",
    "A下单量",
    "A订单号",
    "B订单号",
    "A下单日志",
    "B挂单日志",
    "执行日志",
    "开仓次数",
    "平仓次数",
    "备注",
]


def _bp(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{float(value) * 1e4:.4f}"


def _pct(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{float(value) * 100:.4f}"


def _num(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{float(value):.8g}"


def _txt(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


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

    def _read_header(self) -> Optional[List[str]]:
        if not self.path.is_file() or self.path.stat().st_size <= 0:
            return None
        try:
            with open(self.path, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.reader(fh)
                row = next(reader, None)
                return list(row) if row else None
        except OSError:
            return None

    def _migrate_header(self) -> None:
        """旧 CSV 缺新列时补齐表头与空值，避免后续行错位。"""
        old = self._read_header()
        if old is None:
            return
        if old == HEADERS:
            return
        rows: List[Dict[str, str]] = []
        try:
            with open(self.path, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    rows.append({h: str(row.get(h) or "") for h in HEADERS})
        except OSError:
            return
        with open(self.path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=HEADERS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _ensure_header(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_file() and self.path.stat().st_size > 0:
            self._migrate_header()
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
        edge_pct: Optional[float] = None,
        px_a: Optional[float] = None,
        px_b: Optional[float] = None,
        pos_a_before: Optional[float] = None,
        pos_a_after: Optional[float] = None,
        pos_b_before: Optional[float] = None,
        pos_b_after: Optional[float] = None,
        a_side: str = "",
        b_side: str = "",
        a_order_count: Optional[int] = None,
        a_order_qty: Optional[float] = None,
        a_order_id: str = "",
        b_order_id: str = "",
        a_order_log: str = "",
        b_order_log: str = "",
        exec_log: str = "",
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
        # 本次下单方向对应的净价差：显式传入优先，否则按方向取 AB/BA
        if edge_pct is not None:
            trade_edge = float(edge_pct)
        elif delta > 0 and ab_pct is not None:
            trade_edge = float(ab_pct)
        elif delta < 0 and ba_pct is not None:
            trade_edge = float(ba_pct)
        else:
            trade_edge = mag
        row: Dict[str, Any] = {
            "时间": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "动作": action,
            "方向": side,
            "层前": lots_before,
            "层后": lots_after,
            "数量": _num(qty),
            "价差bp": _bp(trade_edge),
            "价差%": _pct(trade_edge),
            "现净bp": _bp(mag),
            "下沿bp": _bp(lower),
            "上沿bp": _bp(upper),
            "中枢bp": _bp(center),
            "来回bp": _bp(cost),
            "AB净bp": _bp(ab_pct),
            "BA净bp": _bp(ba_pct),
            "A价": _num(px_a),
            "B价": _num(px_b),
            "A仓前": _num(pos_a_before),
            "A仓后": _num(pos_a_after),
            "B仓前": _num(pos_b_before),
            "B仓后": _num(pos_b_after),
            "A侧": _txt(a_side),
            "B侧": _txt(b_side),
            "A下单次数": "" if a_order_count is None else str(int(a_order_count)),
            "A下单量": _num(a_order_qty),
            "A订单号": _txt(a_order_id),
            "B订单号": _txt(b_order_id),
            "A下单日志": _txt(a_order_log),
            "B挂单日志": _txt(b_order_log),
            "执行日志": _txt(exec_log),
            "开仓次数": self.opens,
            "平仓次数": self.closes,
            "备注": note,
        }
        self._ensure_header()
        with open(self.path, "a", encoding="utf-8-sig", newline="") as fh:
            csv.DictWriter(fh, fieldnames=HEADERS).writerow(row)
        edge_txt = _pct(trade_edge)
        a_n = int(a_order_count or 0)
        self.last = (
            f"{action} {side} 价差{edge_txt}% A×{a_n} "
            f"B仓{_num(pos_b_before)}→{_num(pos_b_after)} "
            f"开{self.opens}平{self.closes}"
            if edge_txt
            else f"{action} {side} A×{a_n} 开{self.opens}平{self.closes}"
        )
