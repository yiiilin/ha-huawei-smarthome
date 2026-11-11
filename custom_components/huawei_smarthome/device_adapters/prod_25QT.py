"""User-contributed protocol for Huawei product 25QT (海鸟贴纸打印机 无屏版).

产品: 海鸟贴纸打印机(无屏版)
厂商: 中山市三藏电子科技有限公司
型号: SEABIRD P1-12A / deviceTypeName 便签打印机 / protocol BLE
Profile: https://smarthome-drcn.dbankcdn.com/device/guide/25QT/25QT.json

═══════════════════════════════════════════════════════════════════
数据与验证状态
═══════════════════════════════════════════════════════════════════

字段名与枚举取自该产品物模型。本适配器**只做只读状态**：物模型里
``Labeltemplate`` / ``Edittext`` / ``Print`` 都是内容与动作类字段（标签模板、
待打印文本、打印指令），语义与取值格式没有声明 dataType，贸然下发可能打印出
乱码标签，所以在确认之前不映射任何动作。

**重要：这是蓝牙(BLE)设备。** 它不直连华为云，云端只有在手机 App 连接过之后
才可能有数据；因此多数实体平时会显示"未知"，属正常现象。

核心服务（取自该产品物模型）:

    Connection       Connection 0未连接/1连接中/2已连接
    Powerdisplay     Powerdisplay 电量
    Print            Print 0打印成功/1数据传输错误/2数据漏传/3超时
    update           version 固件版本
    netInfo          intensity / SSID / RSSI

═══════════════════════════════════════════════════════════════════
实体清单
═══════════════════════════════════════════════════════════════════

    sensor   连接状态 (未连接/连接中/已连接)
    sensor   打印状态 (打印成功/数据传输错误/数据漏传/超时)
    sensor   电量
    sensor   固件版本（诊断）
    sensor   Wi-Fi 信号强度（诊断，BLE 机型可能不上报）

═══════════════════════════════════════════════════════════════════
未映射的服务
═══════════════════════════════════════════════════════════════════

``Labeltemplate`` / ``Edittext`` / ``Print``（打印动作）/ ``update.action``（OTA）。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_CONNECTION_SID = "Connection"
_POWER_SID = "Powerdisplay"
_PRINT_SID = "Print"
_UPDATE_SID = "update"
_NET_SID = "netInfo"


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


def _enum_sensor(context: DeviceContext, sid: str, field: str, key: str, name: str,
                 category: str | None = None) -> EntitySpec | None:
    if not _has_field(context, sid, field):
        return None
    metadata: dict[str, Any] = {}
    if category:
        metadata["entity_category"] = category

    def state(device: DeviceContext) -> Mapping[str, Any]:
        raw = device.value(sid, field)
        if raw is None:
            return {"native_value": None}
        return {"native_value": _enum_label(context, sid, field, raw) or str(raw)}

    return EntitySpec(platform="sensor", key=key, name=name, state=state,
                      metadata=metadata)


class Product25QTAdapter:
    """25QT 海鸟贴纸打印机适配器（只读状态）。"""

    prod_id = "25QT"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None:
            return ()

        entities: list[EntitySpec] = []

        for spec in (
            _enum_sensor(context, _CONNECTION_SID, "Connection", "connection", "连接状态"),
            _enum_sensor(context, _PRINT_SID, "Print", "print_status", "打印状态",
                         "diagnostic"),
        ):
            if spec is not None:
                entities.append(spec)

        if _has_field(context, _POWER_SID, "Powerdisplay"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="battery",
                    name="电量",
                    state=lambda device: {
                        "native_value": _as_int(
                            device.value(_POWER_SID, "Powerdisplay"))},
                    metadata={"unit": "%", "device_class": "battery",
                              "state_class": "measurement"},
                )
            )

        if _has_field(context, _NET_SID, "intensity"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="wifi_signal",
                    name="Wi-Fi 信号强度",
                    state=lambda device: {
                        "native_value": _as_int(device.value(_NET_SID, "intensity"))},
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
                        "native_value": device.value(_UPDATE_SID, "version")},
                    metadata={"entity_category": "diagnostic"},
                )
            )

        return tuple(entities)


ADAPTER = Product25QTAdapter()
