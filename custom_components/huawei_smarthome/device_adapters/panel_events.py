"""Scene-panel key events shared by the wall-panel adapters.

面板按键不会产生独立的 ``button`` 服务写入：华为云端在按下按键时更新
``scene`` 服务的 ``num``（按键序号）/ ``LongClick`` / ``DoubleClick`` 计数器，
并刷新该服务的 reported_timestamp。因此这里用 event_decoder 监听 ``scene``
的时间戳变化，把一次物理按键翻译成 HA 的 event 实体；初始快照不会触发事件。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec

EVENT_TYPES: tuple[str, ...] = ("按键", "长按", "双击")


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def panel_key_names(context: Any, count: int = 20) -> dict[int, str]:
    """Read the per-key scene labels the app stores on ``buttonN.name``."""

    names: dict[int, str] = {}
    for index in range(1, count + 1):
        label = context.value(f"button{index}", "name")
        if not isinstance(label, str):
            continue
        label = label.strip().rstrip("|").strip()
        if label and label != "未定义":
            names[index] = label
    return names


def scene_event_spec(
    context: Any,
    *,
    key_names: Mapping[int, str] | None = None,
    key: str = "panel_event",
    name: str = "按键事件",
) -> EntitySpec | None:
    if not context.has_service("scene"):
        return None
    names = dict(key_names or {})
    seen: dict[str, Any] = {"ts": None, "data": {}}

    def state(_context: Any) -> Mapping[str, Any]:
        return {}

    def decoder(
        _context: Any,
        sid: str,
        data: Mapping[str, Any],
        timestamp: Any,
    ) -> list[tuple[str, dict[str, Any]]]:
        if str(sid) != "scene":
            return []
        ts = str(timestamp) if timestamp else None
        if ts is not None and ts == seen["ts"]:
            return []
        previous = seen["data"]
        first = seen["ts"] is None
        seen["ts"] = ts
        seen["data"] = dict(data)
        if first:
            # 首次收到的是云端快照，不是按键动作。
            return []

        long_click = _num(data.get("LongClick")) or 0.0
        double_click = _num(data.get("DoubleClick")) or 0.0
        previous_long = _num(previous.get("LongClick")) or 0.0
        previous_double = _num(previous.get("DoubleClick")) or 0.0
        if double_click != previous_double:
            event_type = "双击"
        elif long_click != previous_long:
            event_type = "长按"
        else:
            event_type = "按键"

        number = _num(data.get("num"))
        index = int(number) if number is not None else None
        return [
            (
                event_type,
                {
                    "num": index,
                    "key_name": names.get(index) if index is not None else None,
                    "long_click": data.get("LongClick"),
                    "double_click": data.get("DoubleClick"),
                },
            )
        ]

    return EntitySpec(
        platform="event",
        key=key,
        name=name,
        state=state,
        metadata={"event_types": list(EVENT_TYPES), "icon": "mdi:gesture-tap-button"},
        event_decoder=decoder,
    )
