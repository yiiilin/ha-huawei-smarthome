"""Profile-driven one-channel wall-switch adapter for product ZG0B."""

from __future__ import annotations

from typing import Any

from .api import EntitySpec, HuaweiProductAdapter
from .product_helpers import bool_value, can_read, can_write, matches_product, send_profile_value


async def _set(context: Any, sid: str, on: bool) -> None:
    await send_profile_value(context, sid, "on", on)


def _channel_spec(sid: str) -> EntitySpec:
    async def turn_on(context: Any, _data: Any) -> None:
        await _set(context, sid, True)

    async def turn_off(context: Any, _data: Any) -> None:
        await _set(context, sid, False)

    return EntitySpec(
        platform="switch",
        key=sid,
        name=f"开关{sid.removeprefix('switch')}",
        state=lambda context: {"is_on": bool_value(context.value(sid, "on"))},
        actions={"turn_on": turn_on, "turn_off": turn_off},
    )


class ZG0BAdapter:
    prod_id = "ZG0B"

    def entities(self, context: Any) -> tuple[EntitySpec, ...]:
        if not matches_product(context, self.prod_id):
            return ()
        profile = context.profile
        services = profile.get("services", []) if isinstance(profile, dict) else []
        specs: list[EntitySpec] = []
        for service in services:
            if not isinstance(service, dict):
                continue
            sid = service.get("serviceId")
            if not isinstance(sid, str) or not sid.startswith("switch"):
                continue
            suffix = sid.removeprefix("switch")
            if not suffix.isdigit() or not can_read(context, sid, "on"):
                continue
            actions = {"turn_on", "turn_off"} if can_write(context, sid, "on") else set()
            spec = _channel_spec(sid)
            if not actions:
                spec = EntitySpec(
                    platform=spec.platform,
                    key=spec.key,
                    name=spec.name,
                    state=spec.state,
                )
            specs.append(spec)
        return tuple(specs)


ADAPTER: HuaweiProductAdapter = ZG0BAdapter()
