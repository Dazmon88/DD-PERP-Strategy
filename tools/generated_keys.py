"""
从仓库根目录 .generated/{name}.json 加载密钥 / 凭据。

优先级（后者覆盖前者）由调用方决定；本模块只负责读文件。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = PROJECT_ROOT / ".generated"


def generated_path(name: str) -> Path:
    """返回 .generated/{name}.json 路径（不含扩展名也可）。"""
    n = (name or "").strip().lower()
    if n.endswith(".json"):
        n = n[: -len(".json")]
    return GENERATED_DIR / f"{n}.json"


def load_generated(name: str, *, required: bool = False) -> Dict[str, Any]:
    """
    加载 .generated/{name}.json。

    Args:
        name: 文件名（如 popdex / arcus / telegram）
        required: True 时文件不存在则报错
    """
    path = generated_path(name)
    if not path.exists():
        if required:
            raise FileNotFoundError(
                f"缺少密钥文件: {path}。可复制 {path.name}.example 为 {path.name} 后填写。"
            )
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} 必须是 JSON object")
    return data


def merge_generated(
    base: Dict[str, Any],
    name: str,
    *,
    only_empty: bool = False,
) -> Dict[str, Any]:
    """
    将 .generated/{name}.json 合并进 base。

    only_empty=True 时：仅当 base 中该键缺失或为空字符串时才写入。
    """
    extra = load_generated(name)
    if not extra:
        return base
    out = dict(base)
    for k, v in extra.items():
        if only_empty:
            cur = out.get(k)
            if cur is None or (isinstance(cur, str) and not cur.strip()):
                out[k] = v
        else:
            # generated 覆盖；但跳过 None，避免抹掉 yaml 有效值
            if v is not None:
                out[k] = v
    return out
