"""Profile-driven multi-channel wall-switch adapter for product ZG0D."""

from __future__ import annotations

from typing import Any

from .api import EntitySpec, HuaweiProductAdapter
from .product_helpers import bool_value, can_read, can_write, matches_product, send_profile_value


class ZG0DAdapter:
    prod_id = "ZG0D"

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
            actions = {}
            if can_write(context, sid, "on"):
                async def turn_on(ctx: Any, _data: Any, service_id: str = sid) -> None:
                    await send_profile_value(ctx, service_id, "on", True)

                async def turn_off(ctx: Any, _data: Any, service_id: str = sid) -> None:
                    await send_profile_value(ctx, service_id, "on", False)

                actions = {"turn_on": turn_on, "turn_off": turn_off}
            specs.append(
                EntitySpec(
                    platform="switch",
                    key=sid,
                    name=f"开关{suffix}",
                    state=lambda ctx, service_id=sid: {
                        "is_on": bool_value(ctx.value(service_id, "on"))
                    },
                    actions=actions,
                )
            )
        return tuple(specs)


ADAPTER: HuaweiProductAdapter = ZG0DAdapter()
