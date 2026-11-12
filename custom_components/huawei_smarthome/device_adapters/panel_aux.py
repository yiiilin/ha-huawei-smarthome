"""Shared Profile-driven auxiliary controls for Huawei key panels.

指示灯开关 / 指示灯亮度 / 断电记忆 / 按键锁定 这几组字段在 OSLO 系面板
(ZG0B / ZG0D / ZG10 / ZG11) 上完全一致，抽出来共用，避免每个适配器复制。
所有实体都以 Profile 里是否声明对应特征为准，声明缺失即跳过。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

BACKLIGHT_SID = "backlight"
MEMORY_SID = "memorySwitch"
LOCK_SID = "childLockSwitch"
BRIGHTNESS_SID = "brightness"
FLAG_FIELD = "on"
BRIGHTNESS_FIELD = "brightness"
BRIGHTNESS_RANGE = (1.0, 100.0)


def _service(profile: Any, sid: str) -> Any:
    if not isinstance(profile, dict):
        return None
    for service in profile.get("services", ()):
        if isinstance(service, dict) and service.get("serviceId") == sid:
            return service
    return None


def has_field(profile: Any, sid: str, name: str) -> bool:
    service = _service(profile, sid)
    if service is None:
        return False
    return any(
        isinstance(c, dict) and c.get("characteristicName") == name
        for c in service.get("characteristics", ())
    )


def _flag_value(raw: Any) -> bool | None:
    """0/1 → bool，其它值保持未知，避免把异常值画成开/关。"""

    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    try:
        number = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if number == 1:
        return True
    if number == 0:
        return False
    return None


def _number(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _flag_action(sid: str, value: int):
    async def action(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(sid, {FLAG_FIELD: value})

    return action


def _flag_switch(sid: str, key: str, name: str) -> EntitySpec:
    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=lambda ctx: {"is_on": _flag_value(ctx.value(sid, FLAG_FIELD))},
        metadata={},
        actions={"turn_on": _flag_action(sid, 1), "turn_off": _flag_action(sid, 0)},
    )


def panel_aux_specs(context: Any) -> list[EntitySpec]:
    """Build the auxiliary panel controls the device Profile actually declares."""

    profile = context.profile
    specs: list[EntitySpec] = []

    if has_field(profile, BACKLIGHT_SID, FLAG_FIELD):
        specs.append(_flag_switch(BACKLIGHT_SID, "indicator_light", "指示灯"))

    if has_field(profile, BRIGHTNESS_SID, BRIGHTNESS_FIELD):
        async def _brightness_action(
            ctx: DeviceContext, data: Mapping[str, Any]
        ) -> None:
            value = _number(data.get("value"))
            if value is None:
                raise ValueError("brightness value is required")
            clamped = int(max(BRIGHTNESS_RANGE[0], min(BRIGHTNESS_RANGE[1], value)))
            await ctx.async_send_service(
                BRIGHTNESS_SID, {BRIGHTNESS_FIELD: clamped}
            )

        specs.append(
            EntitySpec(
                platform="number",
                key="indicator_brightness",
                name="指示灯亮度",
                state=lambda ctx: {
                    "native_value": _number(
                        ctx.value(BRIGHTNESS_SID, BRIGHTNESS_FIELD)
                    )
                },
                metadata={
                    "min": BRIGHTNESS_RANGE[0],
                    "max": BRIGHTNESS_RANGE[1],
                    "step": 1.0,
                    "unit": "%",
                },
                actions={"set_value": _brightness_action},
            )
        )

    if has_field(profile, MEMORY_SID, FLAG_FIELD):
        specs.append(_flag_switch(MEMORY_SID, "power_loss_memory", "断电记忆"))

    if has_field(profile, LOCK_SID, FLAG_FIELD):
        specs.append(_flag_switch(LOCK_SID, "key_lock", "按键锁定"))

    return specs
