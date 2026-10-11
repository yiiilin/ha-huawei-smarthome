"""Huawei air-conditioner adapter for product A002."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .api import EntitySpec, HuaweiProductAdapter
from .product_helpers import (
    can_read,
    can_write,
    bool_value,
    enum_label,
    enum_value_for_label,
    matches_product,
    read_number,
    send_profile_value,
)


_MODE_LABELS = {
    "自动": "auto",
    "制冷": "cool",
    "制热": "heat",
    "送风": "fan_only",
    "抽湿": "dry",
}
_FAN_LABELS = {"手动风": "manual", "自动风": "auto"}
_SWING_LABELS = {
    "固定": "off",
    "左右扫风": "horizontal",
    "上下扫风": "vertical",
    "左右+上下": "both",
}


def _options(context: Any, sid: str, field: str, label_map: Mapping[str, str]) -> list[str]:
    values: list[str] = []
    profile = context.profile
    services = profile.get("services", []) if isinstance(profile, Mapping) else []
    for service in services:
        if not isinstance(service, Mapping) or service.get("serviceId") != sid:
            continue
        for characteristic in service.get("characteristics", []):
            if not isinstance(characteristic, Mapping) or characteristic.get("characteristicName") != field:
                continue
            enum_list = characteristic.get("enumList", [])
            if isinstance(enum_list, list):
                values.extend(
                    label_map[item["descCh"]]
                    for item in enum_list
                    if isinstance(item, Mapping) and item.get("descCh") in label_map
                )
    return list(dict.fromkeys(values))


def _ha_value(context: Any, sid: str, field: str, value: Any, label_map: Mapping[str, str]) -> str | None:
    label = enum_label(context, sid, field, value)
    return label_map.get(label) if label is not None else None


def _profile_label(context: Any, sid: str, field: str, value: str, label_map: Mapping[str, str]) -> Any | None:
    label = next((label for label, ha_value in label_map.items() if ha_value == value), None)
    return enum_value_for_label(context, sid, field, label) if label is not None else None


def _target_temperature(context: Any) -> float | None:
    """Normalize observed A002 target reports without assuming one wire scale."""

    if not can_read(context, "temperature", "target"):
        return None
    raw = context.value("temperature", "target")
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(value):
        return None
    if 17 <= value <= 30:
        return round(value, 6)
    if 170 <= value <= 300:
        return round(value / 10, 6)
    return None


async def _set_hvac_mode(context: Any, data: Mapping[str, Any]) -> None:
    mode = data.get("hvac_mode")
    switch_writable = can_write(context, "switch", "on")
    switch_on = bool_value(context.value("switch", "on"))
    if mode == "off":
        if not switch_writable:
            raise ValueError("Profile does not permit switching the A002 off")
        await send_profile_value(context, "switch", "on", False)
        return
    profile_value = _profile_label(context, "mode", "mode", str(mode), _MODE_LABELS)
    if profile_value is None:
        raise ValueError(f"unsupported A002 HVAC mode: {mode!r}")
    if switch_on is not True and not switch_writable:
        raise ValueError("cannot power on A002: Profile does not permit writing switch.on")
    await send_profile_value(context, "mode", "mode", profile_value)
    if switch_on is not True:
        await send_profile_value(context, "switch", "on", True)


async def _set_fan_mode(context: Any, data: Mapping[str, Any]) -> None:
    mode = data.get("fan_mode")
    profile_value = _profile_label(context, "fan", "mode", str(mode), _FAN_LABELS)
    if profile_value is None:
        raise ValueError(f"unsupported A002 fan mode: {mode!r}")
    await send_profile_value(context, "fan", "mode", profile_value)


async def _set_swing_mode(context: Any, data: Mapping[str, Any]) -> None:
    mode = data.get("swing_mode")
    profile_value = _profile_label(context, "fan", "direction", str(mode), _SWING_LABELS)
    if profile_value is None:
        raise ValueError(f"unsupported A002 swing mode: {mode!r}")
    await send_profile_value(context, "fan", "direction", profile_value)


async def _turn_on(context: Any, _data: Mapping[str, Any]) -> None:
    await send_profile_value(context, "switch", "on", True)


async def _turn_off(context: Any, _data: Mapping[str, Any]) -> None:
    await send_profile_value(context, "switch", "on", False)


class A002Adapter:
    prod_id = "A002"

    def entities(self, context: Any) -> tuple[EntitySpec, ...]:
        if not matches_product(context, self.prod_id):
            return ()
        if not all(
            can_read(context, sid, field)
            for sid, field in (
                ("switch", "on"),
                ("mode", "mode"),
                ("temperature", "current"),
                ("temperature", "target"),
            )
        ):
            return ()

        switch_writable = can_write(context, "switch", "on")
        mode_options = (
            _options(context, "mode", "mode", _MODE_LABELS)
            if can_write(context, "mode", "mode")
            else []
        )
        fan_modes = (
            _options(context, "fan", "mode", _FAN_LABELS)
            if can_write(context, "fan", "mode")
            else []
        )
        swing_modes = (
            _options(context, "fan", "direction", _SWING_LABELS)
            if can_write(context, "fan", "direction")
            else []
        )
        hvac_modes = (["off"] if switch_writable else []) + mode_options
        actions: dict[str, Any] = {}
        if switch_writable or mode_options:
            actions["set_hvac_mode"] = _set_hvac_mode
        if switch_writable:
            actions["turn_on"] = _turn_on
            actions["turn_off"] = _turn_off
        if fan_modes:
            actions["set_fan_mode"] = _set_fan_mode
        if swing_modes:
            actions["set_swing_mode"] = _set_swing_mode

        specs = [
            EntitySpec(
                platform="climate",
                key="climate",
                name="空调",
                state=lambda ctx: {
                    "hvac_mode": (
                        "off"
                        if bool_value(ctx.value("switch", "on")) is False
                        else _ha_value(ctx, "mode", "mode", ctx.value("mode", "mode"), _MODE_LABELS)
                    ),
                    "current_temperature": read_number(ctx, "temperature", "current"),
                    "fan_mode": _ha_value(ctx, "fan", "mode", ctx.value("fan", "mode"), _FAN_LABELS),
                    "swing_mode": _ha_value(
                        ctx, "fan", "direction", ctx.value("fan", "direction"), _SWING_LABELS
                    ),
                },
                metadata={
                    "hvac_modes": hvac_modes,
                    "fan_modes": fan_modes,
                    "swing_modes": swing_modes,
                    "min_temp": 17,
                    "max_temp": 30,
                    "target_temperature_step": 0.5,
                    "temperature_unit": "°C",
                },
                actions=actions,
            )
        ]

        specs.append(
            EntitySpec(
                platform="sensor",
                key="target_temperature",
                name="目标温度",
                state=lambda ctx: {"native_value": _target_temperature(ctx)},
                metadata={"unit": "°C", "device_class": "temperature"},
            )
        )
        return tuple(specs)


ADAPTER: HuaweiProductAdapter = A002Adapter()
