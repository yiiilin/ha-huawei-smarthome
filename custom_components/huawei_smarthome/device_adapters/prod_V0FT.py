"""User-contributed protocol for Huawei product V0FT (华为智慧屏 MateTV).

产品: 华为智慧屏 MateTV
厂商: 华为
型号: EDIS-760B / deviceTypeName 智慧屏 / protocol WiFi
Profile: https://smarthome-drcn.dbankcdn.com/device/guide/V0FT/V0FT.json

═══════════════════════════════════════════════════════════════════
数据与验证状态
═══════════════════════════════════════════════════════════════════

这个产品的物模型极薄：只有 ``remotecontrol``（远程控制开关与地址）、
``devicestate.screenState``（熄屏/在线/离线）和 ``logreport``（日志上报）。
华为把智慧屏的实际控制能力放在 DLNA / Cast 里，而不是 SmartHome 物模型，
所以**这里只能做到"看屏幕状态 + 开关远程控制"**，做不出音量/输入源/遥控键
那类实体。

想控制电视请看 HA 里已有的 ``dlna_dmr`` 集成（MCh的智慧屏 MateTV）；
本适配器只补上"屏状态"这一条信息。

核心服务（取自该产品物模型）:

    devicestate     screenState 0已熄屏/1在线/2离线
    remotecontrol   switchState 0关闭/1开启, ip_addr, version, access_token
    logreport       logreporttype / faultnumber / faulttype

═══════════════════════════════════════════════════════════════════
实体清单
═══════════════════════════════════════════════════════════════════

    sensor   屏幕状态 (已熄屏/在线/离线)
    switch   远程控制 (remotecontrol.switchState)
    sensor   远程控制地址 (诊断)

═══════════════════════════════════════════════════════════════════
未映射的服务
═══════════════════════════════════════════════════════════════════

``logreport``（厂商日志通道，对用户无意义）。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_STATE_SID = "devicestate"
_STATE_FIELD = "screenState"
_REMOTE_SID = "remotecontrol"
_REMOTE_FIELD = "switchState"


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        try:
            return int(round(float(value.strip())))
        except (TypeError, ValueError):
            return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    number = _as_int(value)
    return None if number is None else number != 0


def _enum_label(context: DeviceContext, sid: str, field: str, value: Any) -> str | None:
    number = _as_int(value)
    if number is None:
        return None
    profile = context.profile
    if not isinstance(profile, Mapping):
        return None
    for service in profile.get("services", ()) or ():
        if not isinstance(service, Mapping) or service.get("serviceId") != sid:
            continue
        for characteristic in service.get("characteristics", ()) or ():
            if not isinstance(characteristic, Mapping):
                continue
            if characteristic.get("characteristicName") != field:
                continue
            for option in characteristic.get("enumList", ()) or ():
                if not isinstance(option, Mapping):
                    continue
                if _as_int(option.get("enumVal")) == number:
                    label = option.get("descCh") or option.get("descEn")
                    return str(label) if label else None
    return None


def _has_field(context: DeviceContext, sid: str, field: str) -> bool:
    if field in context.service_state(sid):
        return True
    profile = context.profile
    if not isinstance(profile, Mapping):
        return False
    for service in profile.get("services", ()) or ():
        if not isinstance(service, Mapping) or service.get("serviceId") != sid:
            continue
        for characteristic in service.get("characteristics", ()) or ():
            if (isinstance(characteristic, Mapping)
                    and characteristic.get("characteristicName") == field):
                return True
    return False


async def _remote_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service(_REMOTE_SID, {_REMOTE_FIELD: 1})


async def _remote_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service(_REMOTE_SID, {_REMOTE_FIELD: 0})


class ProductV0FTAdapter:
    """V0FT 华为智慧屏适配器（屏状态 + 远程控制开关）。"""

    prod_id = "V0FT"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None:
            return ()
        if not _has_field(context, _STATE_SID, _STATE_FIELD) \
                and not _has_field(context, _REMOTE_SID, _REMOTE_FIELD):
            return ()

        entities: list[EntitySpec] = []

        if _has_field(context, _STATE_SID, _STATE_FIELD):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="screen_state",
                    name="屏幕状态",
                    state=lambda device: {
                        "native_value": _enum_label(
                            context, _STATE_SID, _STATE_FIELD,
                            device.value(_STATE_SID, _STATE_FIELD))
                        or device.value(_STATE_SID, _STATE_FIELD)},
                )
            )

        if _has_field(context, _REMOTE_SID, _REMOTE_FIELD):
            entities.append(
                EntitySpec(
                    platform="switch",
                    key="remote_control",
                    name="远程控制",
                    state=lambda device: {
                        "is_on": _as_bool(device.value(_REMOTE_SID, _REMOTE_FIELD))},
                    actions={"turn_on": _remote_on, "turn_off": _remote_off},
                )
            )

        if _has_field(context, _REMOTE_SID, "ip_addr"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="remote_ip",
                    name="远程控制地址",
                    state=lambda device: {
                        "native_value": device.value(_REMOTE_SID, "ip_addr")},
                    metadata={"entity_category": "diagnostic"},
                )
            )

        return tuple(entities)


ADAPTER = ProductV0FTAdapter()
