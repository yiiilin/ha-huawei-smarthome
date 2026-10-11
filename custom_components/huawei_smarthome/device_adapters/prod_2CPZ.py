"""Motorized curtain adapter for Huawei product 2CPZ."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec, HuaweiProductAdapter
from .product_helpers import (
    can_read,
    can_write,
    enum_value_for_label,
    matches_product,
    number_metadata,
    read_number,
    send_profile_value,
)


_ACTION_LABELS = {"open": "开", "close": "关", "stop": "停止"}


async def _action(context: Any, command: str) -> None:
    value = enum_value_for_label(context, "action", "action", _ACTION_LABELS[command])
    if value is None:
        raise ValueError(f"2CPZ Profile has no {command} action")
    await send_profile_value(context, "action", "action", value)


async def _open(context: Any, _data: Mapping[str, Any]) -> None:
    await _action(context, "open")


async def _close(context: Any, _data: Mapping[str, Any]) -> None:
    await _action(context, "close")


async def _stop(context: Any, _data: Mapping[str, Any]) -> None:
    await _action(context, "stop")


async def _set_position(context: Any, data: Mapping[str, Any]) -> None:
    await send_profile_value(context, "opener", "target", data.get("position"))


class TwoCPZAdapter:
    prod_id = "2CPZ"

    def entities(self, context: Any) -> tuple[EntitySpec, ...]:
        if not matches_product(context, self.prod_id) or not can_read(context, "opener", "current"):
            return ()
        actions: dict[str, Any] = {}
        if can_write(context, "action", "action"):
            actions.update(
                {
                    key: callback
                    for key, callback in (
                        ("open", _open),
                        ("close", _close),
                        ("stop", _stop),
                    )
                    if enum_value_for_label(context, "action", "action", _ACTION_LABELS[key]) is not None
                }
            )
        if can_write(context, "opener", "target"):
            actions["set_position"] = _set_position
        metadata: dict[str, Any] = {"device_class": "curtain"}
        position_meta = number_metadata(context, "opener", "target")
        if position_meta is not None:
            metadata.update(position_meta)
        return (
            EntitySpec(
                platform="cover",
                key="curtain",
                name="窗帘",
                state=lambda ctx: {
                    "current_position": read_number(ctx, "opener", "current"),
                    "is_closed": (
                        True
                        if read_number(ctx, "opener", "current") == 0
                        else False
                        if read_number(ctx, "opener", "current") is not None
                        else None
                    ),
                },
                metadata=metadata,
                actions=actions,
            ),
        )


ADAPTER: HuaweiProductAdapter = TwoCPZAdapter()
