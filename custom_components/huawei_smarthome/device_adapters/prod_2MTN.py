"""User-contributed protocol for Huawei product 2MTN (华为智选 海雀智能摄像头3 4K).

产品: 华为智选 海雀智能摄像头3 4K版 64GB
厂商: 深圳市海雀科技有限公司
型号: IS8SC800B2 / deviceTypeName 网络摄像头 / protocol WiFi
Profile: https://smarthome-drcn.dbankcdn.com/device/guide/2MTN/2MTN.json

═══════════════════════════════════════════════════════════════════
数据与验证状态
═══════════════════════════════════════════════════════════════════

字段名与枚举取自该产品物模型。开关类写帧为 ``{"on": 0/1}``（该品类在华为
物模型里的标准写法）；预置位按钮下发 ``{"move": 1}``，与物模型里
``move 1:移到该预置点 / 0:无动作`` 的声明一致，但**未在本机实测**。

**重要：视频画面无法接入 HA。** 物模型里没有任何取流地址字段（华为把实时
画面放在 P2P/私有协议里），所以本适配器只提供「控制与告警」实体，摄像头
实体（camera）做不出来 —— 想看画面请继续用华为智慧生活 / 海雀 App。

核心服务（取自该产品物模型）:

    switch         on 0/1   设备开关
    videoSwitch    on 0/1   视频开关
    shootSwitch    on 0/1   抓拍开关
    cruiseSwitch   on 0/1   巡航开关
    visitPoint1-6  enable/move/name/id   预置位（move=1 移到该预置点）
    alarmEvent     alarm 1有告警/0无告警, alarmDescription,
                   audioAlarm / videoAlarm / carAlarm / babyCryAlarm /
                   animalAlarm / humanBodyAlarm
    netInfo        intensity(格数) / RSSI / IP / SSID
    update         version 固件版本

═══════════════════════════════════════════════════════════════════
实体清单
═══════════════════════════════════════════════════════════════════

    switch         摄像头开关 / 视频 / 抓拍 / 巡航
    button         预置位 1-6（按下 = 云台移到该预置点）
    binary_sensor  告警中 + 声音/画面/车辆/哭声/动物/人形 告警
    sensor         告警说明 · Wi-Fi 信号强度 · 固件版本

═══════════════════════════════════════════════════════════════════
已知限制
═══════════════════════════════════════════════════════════════════

1. 无摄像头(camera)实体 —— 取流地址不在物模型里。
2. 摄像头是低功耗设备：不告警时几乎不上报，多数实体平时显示"未知"，
   只有报警/操作时才刷新，属正常。
3. 部分告警字段（车辆/动物/哭声）取决于机型与固件是否上报。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_ALARM_SID = "alarmEvent"
_NET_SID = "netInfo"
_UPDATE_SID = "update"

_SWITCHES = (
    ("switch", "摄像头开关", None),
    ("videoSwitch", "视频", None),
    ("shootSwitch", "抓拍", None),
    ("cruiseSwitch", "巡航", None),
)

_ALARM_FLAGS = (
    ("audioAlarm", "声音告警"),
    ("videoAlarm", "画面告警"),
    ("carAlarm", "车辆告警"),
    ("babyCryAlarm", "哭声告警"),
    ("animalAlarm", "动物告警"),
    ("humanBodyAlarm", "人形告警"),
)

_PRESET_SIDS = tuple("visitPoint%d" % i for i in range(1, 7))


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


def _switch_actions(sid: str):
    async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(sid, {"on": 1})

    async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(sid, {"on": 0})

    return _turn_on, _turn_off


def _preset_press(sid: str):
    async def _press(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(sid, {"move": 1})

    return _press


class Product2MTNAdapter:
    """2MTN 海雀智能摄像头适配器（控制与告警；不含视频画面）。"""

    prod_id = "2MTN"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None:
            return ()
        if not any(context.has_service(sid) for sid, _, _ in _SWITCHES) \
                and not context.has_service(_ALARM_SID):
            return ()

        entities: list[EntitySpec] = []

        for sid, name, _ in _SWITCHES:
            if not context.has_service(sid):
                continue
            on, off = _switch_actions(sid)
            entities.append(
                EntitySpec(
                    platform="switch",
                    key=sid,
                    name=name,
                    state=(lambda device, s=sid: {
                        "is_on": _as_bool(device.value(s, "on"))}),
                    actions={"turn_on": on, "turn_off": off},
                )
            )

        for index, sid in enumerate(_PRESET_SIDS, start=1):
            if not context.has_service(sid):
                continue
            entities.append(
                EntitySpec(
                    platform="button",
                    key=sid,
                    name="预置位 %d" % index,
                    state=lambda device: {},
                    actions={"press": _preset_press(sid)},
                )
            )

        if _has_field(context, _ALARM_SID, "alarm"):
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="alarm",
                    name="告警中",
                    state=lambda device: {
                        "is_on": _as_bool(device.value(_ALARM_SID, "alarm"))},
                    metadata={"device_class": "motion"},
                )
            )

        for field, name in _ALARM_FLAGS:
            if not _has_field(context, _ALARM_SID, field):
                continue
            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key=field,
                    name=name,
                    state=(lambda device, f=field: {
                        "is_on": _as_bool(device.value(_ALARM_SID, f))}),
                    metadata={"entity_category": "diagnostic"},
                )
            )

        if _has_field(context, _ALARM_SID, "alarmDescription"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="alarm_description",
                    name="告警说明",
                    state=lambda device: {
                        "native_value": device.value(_ALARM_SID, "alarmDescription")},
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


ADAPTER = Product2MTNAdapter()
