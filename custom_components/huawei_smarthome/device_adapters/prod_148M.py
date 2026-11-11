"""User-contributed protocol for Huawei product 148M (正泰快充智能插排).

产品: 正泰快充智能插排
厂商: 正泰 (CHINT)
型号: 1.0 / deviceTypeName 智能插排 / protocol WiFi
Profile: https://smarthome-drcn.dbankcdn.com/device/guide/148M/148M.json

═══════════════════════════════════════════════════════════════════
数据来源与验证状态
═══════════════════════════════════════════════════════════════════

字段名、枚举与单位全部取自该产品自己的物模型。开关/断电记忆的写帧形状与
同为插座的 ``124U`` 适配器一致（``{"on": 0/1}``、``{"status": 0/1/2}``），
这是该品类在华为物模型里的标准写法。

核心服务（取自该产品物模型）:

    switch           on 0关/1开                       继电器开关
    memorySwitch     status 0关/1开/2保持上次          断电记忆
    power            current 实时功率(W), percentage
    consumption      consumption 累计电量(kWh)
    faultDetection   status 0正常/1异常, code 0无故障/1过载警告
    netInfo          intensity(格数) / RSSI / SSID / IP
    update           version 固件版本

═══════════════════════════════════════════════════════════════════
实体清单
═══════════════════════════════════════════════════════════════════

    switch            开关
    select            断电记忆 (关/开/保持上次)
    sensor            功率 (W)
    sensor            累计电量 (kWh)
    binary_sensor     设备故障 (device_class problem)
    sensor            故障代码
    sensor            Wi-Fi 信号强度 (%)
    sensor            固件版本（诊断）

═══════════════════════════════════════════════════════════════════
未映射的服务
═══════════════════════════════════════════════════════════════════

``timer`` / ``delay``（倒计时与定时，需要链式下发整组参数）、``update.action``
（OTA）—— 留给厂商 App。

═══════════════════════════════════════════════════════════════════
已知限制
═══════════════════════════════════════════════════════════════════

1. 若插排是"多路"版本，本适配器只映射物模型里的总开关 ``switch.on``。
2. ``power.percentage`` 语义未确认（无单位声明），不建实体。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_SWITCH_SID = "switch"
_MEMORY_SID = "memorySwitch"
_POWER_SID = "power"
_CONSUMPTION_SID = "consumption"
_FAULT_SID = "faultDetection"
_NET_SID = "netInfo"
_UPDATE_SID = "update"

_MEMORY_OPTIONS = ("关", "开", "保持上次")
_MEMORY_TO_DEV = {"关": 0, "开": 1, "保持上次": 2}
_FAULT_STATUS_ABNORMAL = 1


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


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    number = _as_int(value)
    return None if number is None else number != 0


def _enum_label(context: DeviceContext, sid: str, field: str, value: Any) -> str | None:
    """Resolve one enum value to its Profile label."""

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


async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service(_SWITCH_SID, {"on": 1})


async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service(_SWITCH_SID, {"on": 0})


async def _set_memory(context: DeviceContext, data: Mapping[str, Any]) -> None:
    value = _MEMORY_TO_DEV.get(str(data.get("option")))
    if value is None:
        raise ValueError(f"unsupported option: {data.get('option')}")
    await context.async_send_service(_MEMORY_SID, {"status": value})


class Product148MAdapter:
    """148M 正泰快充智能插排适配器。"""

    prod_id = "148M"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service(_SWITCH_SID):
            return ()

        def switch_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"is_on": _as_bool(device.value(_SWITCH_SID, "on"))}

        def memory_state(device: DeviceContext) -> Mapping[str, Any]:
            status = _as_int(device.value(_MEMORY_SID, "status"))
            return {"current_option": _MEMORY_OPTIONS[status]
                    if status is not None and 0 <= status < len(_MEMORY_OPTIONS)
                    else _MEMORY_OPTIONS[0]}

        def power_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _as_float(device.value(_POWER_SID, "current"))}

        def consumption_state(device: DeviceContext) -> Mapping[str, Any]:
            return {"native_value": _as_float(
                device.value(_CONSUMPTION_SID, "consumption"))}

        def fault_state(device: DeviceContext) -> Mapping[str, Any]:
            status = _as_int(device.value(_FAULT_SID, "status"))
            return {"is_on": None if status is None else status == _FAULT_STATUS_ABNORMAL}

        def fault_code_state(device: DeviceContext) -> Mapping[str, Any]:
            raw = device.value(_FAULT_SID, "code")
            if raw is None:
                return {"native_value": None}
            return {"native_value": _enum_label(context, _FAULT_SID, "code", raw)
                    or str(_as_int(raw))}

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="switch",
                key="switch",
                name=None,
                state=switch_state,
                actions={"turn_on": _turn_on, "turn_off": _turn_off},
            )
        ]

        if context.has_service(_MEMORY_SID):
            entities.append(
                EntitySpec(
                    platform="select",
                    key="memory",
                    name="断电记忆",
                    state=memory_state,
                    metadata={"options": list(_MEMORY_OPTIONS)},
                    actions={"select_option": _set_memory},
                )
            )

        if _has_field(context, _POWER_SID, "current"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="power",
                    name="功率",
                    state=power_state,
                    metadata={"unit": "W", "device_class": "power",
                              "state_class": "measurement"},
                )
            )

        if _has_field(context, _CONSUMPTION_SID, "consumption"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="consumption",
                    name="累计电量",
                    state=consumption_state,
                    metadata={"unit": "kWh", "device_class": "energy",
                              "state_class": "total_increasing"},
                )
            )

        if _has_field(context, _FAULT_SID, "status"):
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="fault",
                    name="设备故障",
                    state=fault_state,
                    metadata={"device_class": "problem"},
                )
            )

        if _has_field(context, _FAULT_SID, "code"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="fault_code",
                    name="故障代码",
                    state=fault_code_state,
                    metadata={"entity_category": "diagnostic"},
                )
            )

        if _has_field(context, _NET_SID, "intensity"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="wifi_signal",
                    name="Wi-Fi 信号强度",
                    state=lambda device: {
                        "native_value": _as_int(device.value(_NET_SID, "intensity"))
                    },
                    metadata={"unit": "%", "entity_category": "diagnostic",
                              "state_class": "measurement"},
                )
            )

        if _has_field(context, _UPDATE_SID, "version"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="firmware_version",
                    name="固件版本",
                    state=lambda device: {
                        "native_value": device.value(_UPDATE_SID, "version")
                    },
                    metadata={"entity_category": "diagnostic"},
                )
            )

        return tuple(entities)


ADAPTER = Product148MAdapter()
