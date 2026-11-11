"""User-contributed protocol for Huawei product 294P (遥控大师空调伴侣).

产品: 遥控大师空调伴侣
厂商: 深圳遥看科技有限公司
型号: YKK-KT16A（与 115J 同型号、不同 prodId）
Profile: https://smarthome-drcn.dbankcdn.com/device/guide/294P/294P.json

═══════════════════════════════════════════════════════════════════
数据来源与验证状态
═══════════════════════════════════════════════════════════════════

字段名、取值集合与温度范围全部取自该产品自己的物模型 (Profile)；写帧的形状
（``id`` 恒为 0、关机只发 ``power``、缺省字段不下发）沿用同厂商同型号产品
``115J`` 已在真机上核对过的厂商 H5 下发逻辑。

**294P 本身尚未在真机上逐项实测。** 首次使用请依次核对：开关机、模式、
温度、风速、扫风。若某项无反应，删掉对应动作即可，其余实体不受影响。

核心服务（取自该产品物模型）:

    airKey      空调遥控: power 0关/1开,
                mode 0自动 1除湿 2送风 3制热 4制冷,
                wind 0自动 1低 2中 3高, temp 16-30℃,
                airSwing 0全关 1上下+左右 2仅上下 3仅左右
    switchPower 开关 on 0/1
    indicator1  指示灯 on 0/1
    power       实时功率 current（W，变化上报）
    electric    实时电流 current（mA，每 10 分钟上报）
    netInfo     Wi-Fi: intensity / ssid / ip / rssi
    update      固件: version / introduction / progress

═══════════════════════════════════════════════════════════════════
实体清单
═══════════════════════════════════════════════════════════════════

    air               climate  空调（模式/温度/风速/扫风/开关）
    indicator_led     switch   指示灯
    main_switch       switch   开关
    current_power     sensor   实时功率 (W)
    current_electric  sensor   实时电流 (mA)
    wifi_signal       sensor   Wi-Fi 信号强度 (%)
    firmware_version  sensor   固件版本（诊断）

═══════════════════════════════════════════════════════════════════
未映射的服务
═══════════════════════════════════════════════════════════════════

``sleepCurve``（睡眠曲线）/ ``delay1``（倒计时）/ ``deviceList`` /
``matchKey*``（码库配对）/ ``update.action``（OTA）—— 睡眠曲线与倒计时需要
链式下发整组参数，码库配对与 OTA 属于厂商 App 的职责，未实测之前不映射。

═══════════════════════════════════════════════════════════════════
已知限制
═══════════════════════════════════════════════════════════════════

1. 设备不上报室温，``current_temperature`` 恒为 None（HA 界面不显示当前温度）。
2. ``switchPower`` 按物模型 descCh「开关」命名；若你的设备实际是
   「自动判断开关机」，改一下实体名即可，写入逻辑不变。
3. 除湿模式强制低风（沿用同厂商 H5 行为）。
4. ``indicator1`` 是否主动上报取决于设备固件；不上报时 HA 重启后该实体
   会短暂显示未知，直到下一次操作。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_AIR_SID = "airKey"
_AIR_POWER_SID = "switchPower"
_LED_SID = "indicator1"
_POWER_SID = "power"
_ELECTRIC_SID = "electric"
_NET_SID = "netInfo"
_UPDATE_SID = "update"

_AIR_ID = 0
_POWER_ON = 1
_POWER_OFF = 0

_TEMP_MIN = 16
_TEMP_MAX = 30

# 物模型 airKey.mode: 0自动 1除湿 2送风 3制热 4制冷
_DEV_TO_HVAC = {0: "auto", 1: "dry", 2: "fan_only", 3: "heat", 4: "cool"}
_HVAC_TO_DEV = {value: key for key, value in _DEV_TO_HVAC.items()}

# 物模型 airKey.wind: 0自动 1低 2中 3高
_DEV_TO_FAN = {0: "auto", 1: "low", 2: "medium", 3: "high"}
_FAN_TO_DEV = {value: key for key, value in _DEV_TO_FAN.items()}

# 物模型 airKey.airSwing:
# 0 上下和左右扫风关 / 1 上下和左右扫风开 / 2 上下开左右关 / 3 上下关左右开
_SWING_MODES = ("off", "vertical", "horizontal", "both")
_SWING_TO_DEV = {"off": 0, "both": 1, "vertical": 2, "horizontal": 3}
_DEV_TO_SWING = {value: key for key, value in _SWING_TO_DEV.items()}

# 除湿必须低风（同厂商 H5 行为）
_MODE_FORCED_FAN = {"dry": 1}

_FRAME_FIELDS = ("mode", "wind", "temp", "airSwing")


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


def _has_field(context: DeviceContext, sid: str, field: str) -> bool:
    """字段是否可用 = 当前上报值里有，或物模型里声明了。"""

    if field in context.service_state(sid):
        return True
    profile = context.profile
    if not isinstance(profile, Mapping):
        return False
    for service in profile.get("services", ()) or ():
        if not isinstance(service, Mapping) or service.get("serviceId") != sid:
            continue
        for characteristic in service.get("characteristics", ()) or ():
            if (
                isinstance(characteristic, Mapping)
                and characteristic.get("characteristicName") == field
            ):
                return True
    return False


def _air_frame(
    context: DeviceContext,
    state: Mapping[str, Any],
    **overrides: Any,
) -> dict[str, Any]:
    """按厂商 H5 口径拼一帧 airKey 控制参数。

    取值优先级：本次动作要改的字段 → 设备当前上报值；**拿不到就不放该字段**，
    因为设备对缺省字段保持原值，补 0 反而会把风速/扫风打到自动档。
    """

    frame: dict[str, Any] = {"id": _AIR_ID}
    for field in _FRAME_FIELDS:
        value = _as_int(overrides.get(field, state.get(field)))
        if value is not None:
            frame[field] = value
    power = _as_int(overrides.get("power"))
    if power is not None:
        frame["power"] = power
    return frame


def _wake_power(state: Mapping[str, Any]) -> int | None:
    """已关机时顺带带上 power=1，否则参数写下去也不生效。"""

    if _as_int(state.get("power")) == _POWER_ON:
        return None
    return _POWER_ON


async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    state = context.service_state(_AIR_SID)
    await context.async_send_service(
        _AIR_SID,
        _air_frame(context, state, power=_POWER_ON),
    )


async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service(_AIR_SID, {"id": _AIR_ID, "power": _POWER_OFF})


async def _set_hvac_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    hvac_mode = str(data.get("hvac_mode"))
    if hvac_mode == "off":
        await _turn_off(context, data)
        return
    dev_mode = _HVAC_TO_DEV.get(hvac_mode)
    if dev_mode is None:
        raise ValueError(f"unsupported hvac_mode: {hvac_mode}")

    state = context.service_state(_AIR_SID)
    overrides: dict[str, Any] = {"mode": dev_mode}
    if hvac_mode in _MODE_FORCED_FAN:
        overrides["wind"] = _MODE_FORCED_FAN[hvac_mode]
    elif hvac_mode == "fan_only" and not _as_int(state.get("wind")):
        overrides["wind"] = _FAN_TO_DEV["low"]
    await context.async_send_service(
        _AIR_SID,
        _air_frame(context, state, power=_wake_power(state), **overrides),
    )


async def _set_temperature(context: DeviceContext, data: Mapping[str, Any]) -> None:
    temperature = _as_float(data.get("temperature"))
    if temperature is None:
        return
    target = max(_TEMP_MIN, min(_TEMP_MAX, int(round(temperature))))
    state = context.service_state(_AIR_SID)
    await context.async_send_service(
        _AIR_SID,
        _air_frame(context, state, power=_wake_power(state), temp=target),
    )


async def _set_fan_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    fan_mode = str(data.get("fan_mode"))
    wind = _FAN_TO_DEV.get(fan_mode)
    if wind is None:
        raise ValueError(f"unsupported fan_mode: {fan_mode}")
    state = context.service_state(_AIR_SID)
    await context.async_send_service(
        _AIR_SID,
        _air_frame(context, state, power=_wake_power(state), wind=wind),
    )


async def _set_swing_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    swing_mode = str(data.get("swing_mode"))
    air_swing = _SWING_TO_DEV.get(swing_mode)
    if air_swing is None:
        raise ValueError(f"unsupported swing_mode: {swing_mode}")
    state = context.service_state(_AIR_SID)
    await context.async_send_service(
        _AIR_SID,
        _air_frame(context, state, power=_wake_power(state), airSwing=air_swing),
    )


def _switch_actions(sid: str, field: str = "on"):
    async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(sid, {field: 1})

    async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
        await context.async_send_service(sid, {field: 0})

    return _turn_on, _turn_off


class Product294PAdapter:
    """294P 遥控大师空调伴侣适配器。"""

    prod_id = "294P"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service(_AIR_SID):
            return ()

        def climate_state(device: DeviceContext) -> Mapping[str, Any]:
            state = device.service_state(_AIR_SID)
            power = _as_int(state.get("power"))
            mode = _as_int(state.get("mode"))
            if power == _POWER_OFF:
                hvac_mode: str | None = "off"
            elif power is None:
                hvac_mode = None
            else:
                hvac_mode = _DEV_TO_HVAC.get(mode)
            return {
                "hvac_mode": hvac_mode,
                "target_temperature": _as_float(state.get("temp")),
                "fan_mode": _DEV_TO_FAN.get(_as_int(state.get("wind"))),
                "swing_mode": _DEV_TO_SWING.get(_as_int(state.get("airSwing"))),
            }

        entities: list[EntitySpec] = [
            EntitySpec(
                platform="climate",
                key="air",
                name=None,
                state=climate_state,
                metadata={
                    "hvac_modes": list(_DEV_TO_HVAC.values()) + ["off"],
                    "fan_modes": list(_DEV_TO_FAN.values()),
                    "swing_modes": list(_SWING_MODES),
                    "min_temp": _TEMP_MIN,
                    "max_temp": _TEMP_MAX,
                },
                actions={
                    "turn_on": _turn_on,
                    "turn_off": _turn_off,
                    "set_hvac_mode": _set_hvac_mode,
                    "set_temperature": _set_temperature,
                    "set_fan_mode": _set_fan_mode,
                    "set_swing_mode": _set_swing_mode,
                },
            )
        ]

        if context.has_service(_AIR_POWER_SID) or _has_field(context, _AIR_POWER_SID, "on"):
            on, off = _switch_actions(_AIR_POWER_SID)
            entities.append(
                EntitySpec(
                    platform="switch",
                    key="main_switch",
                    name="开关",
                    state=lambda device: {
                        "is_on": _as_bool(device.value(_AIR_POWER_SID, "on"))
                    },
                    actions={"turn_on": on, "turn_off": off},
                )
            )

        if context.has_service(_LED_SID) or _has_field(context, _LED_SID, "on"):
            led_on, led_off = _switch_actions(_LED_SID)
            entities.append(
                EntitySpec(
                    platform="switch",
                    key="indicator_led",
                    name="指示灯",
                    state=lambda device: {
                        "is_on": _as_bool(device.value(_LED_SID, "on"))
                    },
                    actions={"turn_on": led_on, "turn_off": led_off},
                )
            )

        if _has_field(context, _POWER_SID, "current"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="current_power",
                    name="实时功率",
                    state=lambda device: {
                        "native_value": _as_float(device.value(_POWER_SID, "current"))
                    },
                    metadata={
                        "unit": "W",
                        "device_class": "power",
                        "state_class": "measurement",
                    },
                )
            )

        if _has_field(context, _ELECTRIC_SID, "current"):
            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="current_electric",
                    name="实时电流",
                    state=lambda device: {
                        "native_value": _as_float(device.value(_ELECTRIC_SID, "current"))
                    },
                    # 物模型单位是 mA，HA 的 device_class=current 只接受 A，
                    # 所以不设 device_class，避免出现单位不符的告警。
                    metadata={"unit": "mA", "state_class": "measurement"},
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
                    metadata={"unit": "%", "state_class": "measurement"},
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


ADAPTER = Product294PAdapter()
