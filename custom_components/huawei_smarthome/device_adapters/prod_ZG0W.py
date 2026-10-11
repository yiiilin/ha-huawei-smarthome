"""On/off spot-light adapter for Huawei product ZG0W."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec, HuaweiProductAdapter
from .product_helpers import bool_value, can_read, can_write, matches_product, send_profile_value


async def _turn_on(context: Any, data: Mapping[str, Any]) -> None:
    if any(data.get(key) is not None for key in ("brightness", "rgb_color", "color_temp_kelvin")):
        raise ValueError("ZG0W Profile exposes on/off only")
    await send_profile_value(context, "switch", "on", True)


async def _turn_off(context: Any, _data: Mapping[str, Any]) -> None:
    await send_profile_value(context, "switch", "on", False)


class ZG0WAdapter:
    prod_id = "ZG0W"

    def entities(self, context: Any) -> tuple[EntitySpec, ...]:
        if not matches_product(context, self.prod_id) or not can_read(context, "switch", "on"):
            return ()
        actions = {}
        if can_write(context, "switch", "on"):
            actions = {"turn_on": _turn_on, "turn_off": _turn_off}
        return (
            EntitySpec(
                platform="light",
                key="light",
                name="射灯",
                state=lambda ctx: {"is_on": bool_value(ctx.value("switch", "on"))},
                metadata={"supported_color_modes": {"onoff"}},
                actions=actions,
            ),
        )


ADAPTER: HuaweiProductAdapter = ZG0WAdapter()
