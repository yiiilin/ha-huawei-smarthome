"""User-contributed protocol for Huawei product 2NTI (meipont空调挂机).

产品: meipont 空调挂机
厂商: 美邦电器 (meipont)
型号: MAC50V1THR (deviceTypeId 012, 挂机空调, WiFi, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
**不跨产品复用**。

诚实记录（便于维护者判断）：
本机的 Profile 与仓库已接入的 2NJN（同为美邦/meipont 挂机空调）在
**服务集合（16 个）、全部字段名与类型、全部 16 个枚举定义上完全一致**，
差异仅是型号（2NTI=MAC50V1THR，2NJN=MAC35V1Y1HR）与故障码描述文案。
按仓库规范"相似型号不代表协议相同、必须各自独立实现、不接受提取
公共基类"，本文件仍是**完全独立的一份实现**，不 import 也不复用
2NJN 的任何代码；将来若其中一台的真机行为与 Profile 不符，只需改
对应那一份文件，不影响另一台。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  switch.on              bool  RW 1=开 0=关      电源开关   -> climate on/off
  mode.mode              enum  RW 1=自动 2=制冷 3=制热 4=通风 5=除湿
                                                   -> climate hvac_mode
  temperature.target     int   RW 16~32 ℃         -> climate target
  temperature.current    int   R  -20~50 ℃        -> climate current
  freshAirgear.gear      enum  RW 1=低风 2=中风 3=高风 4=自动风
                                                   -> climate fan_mode
  sweepVertical.on       bool  RW 垂直扫风         -> climate swing_mode
  sweepHorizon.on        bool  RW 水平扫风         -> climate swing_mode

  strong.on              bool  RW 强劲开关         -> strong_switch
  ECOswitch.on           bool  RW ECO 开关         -> eco_switch
  sleeping.on            bool  RW 睡眠开关         -> sleep_switch
  selfCleanswitch.on     bool  RW 自清洁开关       -> self_clean_switch
  light.on               bool  RW 灯光开关         -> light_switch
  PtcHeat.PtcHeat        bool  RW 电辅热开关       -> ptc_switch

  faultDetection.status  enum  R  0=正常 1=异常    -> problem (binary_sensor)
  faultDetection.code    enum  R  30 个故障码      -> 作为 problem 的属性

  netInfo.intensity      enum  R  20/40/60/80/100  -> wifi_signal_level
  netInfo.RSSI           int   R  -100~0 dBm       -> wifi_rssi
  netInfo.IP/SSID/BSSID  string R                  -> 诊断传感器
  update.version         string R 固件版本         -> firmware_version
  update.progress/bootTime/introduction/action     不映射（OTA 流程）
  timer.*（定时服务）      RW array[object]         不映射，见下方说明

=====================================================================
为什么不映射 timer
=====================================================================
timer.timer 是 ``array[object]``，元素含
enable/start/end/sid/para/week/id/paraValue 共 8 个字段，
通过 action 的 create/delete/update 枚举驱动。正确写入必须先读取设备
当前的定时器列表、按 id 增删改、再整体回写。本集成没有该"读-改-写"
事务能力，且写错会覆盖用户已配置的定时，风险高于收益，故不映射。
用户仍可在华为智慧生活 App 中配置定时。

=====================================================================
swing_mode 的映射取舍
=====================================================================
本机把垂直/水平扫风拆成两个独立 bool（sweepVertical / sweepHorizon），
而 HA 的 climate swing_mode 是单选。因此按位组合投影为四档：

    off        两个都关（固定送风）
    vertical   只开垂直扫风
    horizontal 只开水平扫风
    both       两个都开

这意味着两个方向无法在 HA 侧独立控制；如需分别控制，
请使用同时暴露的 vertical_sweep / horizontal_sweep 两个 switch 实体。
写入时按目标档位同时下发两个服务，两侧都发出以避免残留旧状态。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"3"``），
但 characteristicType 是 bool/enum/int，真机只接受**数值**。
直接把枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化，
取值本身从 Profile 的 enumList 读取，不硬编码。

另：``_enum_value()`` **只按 enumVal 精确匹配，不做 descCh/descEn
文本回退**——文本回退会在枚举文案相互包含时命中错误档位
（2QWL 适配中踩过的真实 bug：descEn 的 "110" 与另一档混淆）。

=====================================================================
真机实测记录
=====================================================================
[已实测] **选模式不会启动空调**（用户报告，在 2RK1 上定位后确认本机同源）。

现象：HA 的 climate 界面（本机只声明 hvac_modes + 温度/风速等）里，
用户是通过**模式下拉菜单**操作的。空调处于关机态时选「制冷/制热」，
空调没有反应；但选「关」能正常停机。

根因**不在电源字段，也不在报文编码**，而在旧版 ``_set_hvac_mode`` 的
逻辑缺口——选非 off 模式时**只发 mode，从不置电源位**：

    if wanted == "off":
        await _turn_off(...)          # 发 switch.on = 0  -> 能停机
    else:
        await send("mode", {...})     # 只发 mode，电源位保持 0

本机 Profile 里**没有独立的"开机"服务**，电源就是 ``switch.on``。
且 ``mode`` 的枚举里**没有 0/off**（1自动/2制冷/3除湿/4制热/5送风），
无法用模式表达开关机。于是关机态下选模式，设备只收到模式，
电源位仍是 0 —— 空调当然不启动。

"关机生效"恰好反证了 ``switch.on`` **可写**（写 0 有效），
所以问题不是字段权限、也不是取值编码。

修复（见 ``_set_hvac_mode``）：
  选任何非 off 模式时 = 先写 ``mode``，**再补写 ``switch.on = 1``**。
  两步各自等待云端 ACK（集成对每个 sid 单飞，mode/switch 是不同 sid，
  不会互相阻塞）。

[ ] 待确认：本机修复后从模式下拉选「制冷/制热」，空调是否真的启动；
    选「关」是否仍然正常停机。
[ ] 待确认：选模式会顺带开机（这是刻意的，与智慧生活 App 行为一致）。
    若你希望"选模式不改变电源状态"，需要改为先读电源位再决定是否补写。

=====================================================================
为什么诊断实体默认不创建
=====================================================================
`netInfo`（Wi-Fi 信号格数 / RSSI / IP / SSID / BSSID）与 `update.version`
（固件版本）这 6 个实体在真机上**全部长期为 unknown** —— 设备不上报这些
读取字段，集成侧也没有别的读取路径可以拿到。

保留它们只会让设备页被一堆永远没有值的实体占满，用户还会以为是集成坏了。
因此**默认不创建**。

代码并未删除，而是收进 ``_make_diagnostic_entities()``，由模块级开关
``_ENABLE_DIAGNOSTIC_ENTITIES``（当前 False）控制。
若日后在真机上确认这些字段**确实会上报**（例如固件升级后行为改变），
把该开关改为 True 即可全部恢复，无需重新实现。

注意：开关打开后取值逻辑仍是原样——按 Profile 字段读取，不做任何猜测；
设备不上报时依然显示 unknown。这是刻意的：宁可显示 unknown，
也不给一个编造出来的网络状态。

=====================================================================
尚未验证（需真机确认）
=====================================================================
[ ] 状态读取：全部字段未在真机实测，仅依据 Profile 权限/枚举推导。
[ ] 控制命令：climate 的开关/模式/温度/风速/摆风，以及 6 个 switch，
    均未实测。
[ ] 温度：Profile 声明 int、16~32℃、步进 1。写温度时按 1℃ 对齐并夹取；
    若真机范围更窄或支持 0.5℃ 步进，需真机调整。
[ ] swing_mode 组合写：同时下发 sweepVertical 与 sweepHorizon 两个服务，
    会产生两条 MQTT 命令（框架按 sid 单飞、顺序发送）。
    真机上两个服务是否存在相互覆盖或需要特定顺序，未验证。
[ ] faultDetection.code 的枚举值与 status 的一致性未验证：
    当前以 status==1 作为 problem 判定，code 作为描述；
    若真机出现 status=0 但 code!=0，需改为以 code 为准。
[ ] freshAirgear 的 attrName 写作"新风档位"，但服务描述是"风速"。
    按"风速"映射到 climate 的 fan_mode；若该字段实为独立的新风档位
    （与主风量无关），应在真机上改判为独立 select 实体。
[ ] 灯光/自清洁/睡眠/强劲/ECO 这些开关是否在特定模式下才可写，
    未验证；当前不做事前状态校验，写失败会由云端回 errcode。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

# 诊断实体（netInfo / update）总开关。
# 真机实测：这些实体全部为 unknown，设备不上报对应字段。
# 默认关闭以免污染界面；若日后确认真机会上报，改为 True 即可恢复。
_ENABLE_DIAGNOSTIC_ENTITIES = False


# --- 温度范围：取自本机 Profile 的 min/max/step（int） ----------------
_TEMP_MIN = 16
_TEMP_MAX = 32
_TEMP_STEP = 1

# mode.mode -> HA HVACMode
_DEV_TO_HVAC = {1: "auto", 2: "cool", 3: "heat", 4: "fan_only", 5: "dry"}
_HVAC_TO_DEV = {value: key for key, value in _DEV_TO_HVAC.items()}

# freshAirgear.gear -> HA 风速名（用 Profile 的中文档位名）
_DEV_TO_FAN = {1: "低风", 2: "中风", 3: "高风", 4: "自动风"}
_FAN_TO_DEV = {value: key for key, value in _DEV_TO_FAN.items()}

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# swing_mode 四档 <-> (垂直扫风, 水平扫风)
_SWING_TO_FLAGS = {
    "off": (0, 0),
    "vertical": (1, 0),
    "horizontal": (0, 1),
    "both": (1, 1),
}
_FLAGS_TO_SWING = {value: key for key, value in _SWING_TO_FLAGS.items()}

# 需要以 switch 实体暴露的服务（sid, 字段名, key, 名称）
_SWITCH_SPECS = (
    ("strong", "on", "strong", "强劲"),
    ("ECOswitch", "on", "eco", "ECO"),
    ("sleeping", "on", "sleep", "睡眠"),
    ("selfCleanswitch", "on", "self_clean", "自清洁"),
    ("light", "on", "light", "灯光"),
    # 注意：本机字段名与服务名相同，都是 PtcHeat。
    ("PtcHeat", "PtcHeat", "ptc", "电辅热"),
)

# 扫风方向开关（climate 的 swing_mode 由这两个组合而来）
_SWEEP_SERVICES = (
    ("sweepVertical", "vertical_sweep", "垂直扫风"),
    ("sweepHorizon", "horizontal_sweep", "水平扫风"),
)


# ---------------------------------------------------------------------
# 取值解码
# ---------------------------------------------------------------------
def _bool(value: Any) -> bool | None:
    """Decode a Huawei bool/enum characteristic into a Python bool."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().casefold() in {"1", "true", "on"}:
            return True
        if value.strip().casefold() in {"0", "false", "off"}:
            return False
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(round(number))


def _text(value: Any) -> str | None:
    """Return a non-empty string, otherwise ``None``."""

    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


# ---------------------------------------------------------------------
# Profile 读取与报文编码
# ---------------------------------------------------------------------
def _field(
    profile: Mapping[str, Any] | None,
    sid: str,
    name: str,
) -> Mapping[str, Any] | None:
    """Return one Profile characteristic definition, if declared."""

    if not isinstance(profile, Mapping):
        return None
    for service in profile.get("services", ()):
        if not isinstance(service, Mapping) or service.get("serviceId") != sid:
            continue
        for field in service.get("characteristics", ()):
            if (
                isinstance(field, Mapping)
                and field.get("characteristicName") == name
            ):
                return field
        return None
    return None


def _is_writable(field: Mapping[str, Any] | None) -> bool:
    """Return whether the Profile declares a write capability."""

    if not isinstance(field, Mapping):
        return False
    return "W" in str(field.get("method") or "")


def _coerce(value: Any, field: Mapping[str, Any] | None) -> Any:
    """Encode a command value using the Profile-declared characteristic type.

    Profile 的 enumList 里 enumVal 是字符串，但 bool/enum/int 类字段
    真机只接受数值（否则云端回 errcode=16001）。此处统一数值化。
    """

    if not isinstance(field, Mapping):
        return value
    data_type = str(field.get("characteristicType") or "").casefold()
    if data_type in {"bool", "int", "integer", "enum"}:
        number = _number(value)
        if number is None:
            return value
        return int(number) if number.is_integer() else number
    if data_type in {"float", "double", "number"}:
        number = _number(value)
        return value if number is None else number
    return value


def _enum_value(
    field: Mapping[str, Any] | None,
    wanted: Any,
    fallback: Any,
) -> Any:
    """Resolve the Profile-declared enum value matching ``wanted``.

    只按 ``enumVal`` 精确匹配，不做 descCh/descEn 文本回退
    （文本回退会在枚举文案互相包含时命中错误档位）。
    """

    raw: Any = fallback
    if isinstance(field, Mapping):
        for option in field.get("enumList", ()):
            if not isinstance(option, Mapping):
                continue
            candidate = option.get("enumVal")
            if candidate is None:
                continue
            if str(candidate) == str(wanted):
                raw = candidate
                break
    return _coerce(raw, field)


def _enum_label(field: Mapping[str, Any] | None, value: Any) -> str | None:
    """Resolve a reported raw value to its Profile label."""

    if not isinstance(field, Mapping) or value is None:
        return None
    for option in field.get("enumList", ()):
        if not isinstance(option, Mapping):
            continue
        if str(option.get("enumVal")) != str(value):
            continue
        label = option.get("descCh") or option.get("descEn")
        if isinstance(label, str) and label.strip():
            return label.strip()
    return None


def _clamp(value: Any, field: Mapping[str, Any] | None) -> Any:
    """Clamp a numeric write to the Profile range and align to its step."""

    number = _number(value)
    if number is None:
        return None
    minimum = _number((field or {}).get("min"))
    maximum = _number((field or {}).get("max"))
    if minimum is not None and maximum is not None and maximum < minimum:
        minimum, maximum = maximum, minimum
    if minimum is not None:
        number = max(number, minimum)
    if maximum is not None:
        number = min(number, maximum)
    step = _number((field or {}).get("step"))
    if step is None or step <= 0:
        data_type = str((field or {}).get("characteristicType") or "").casefold()
        step = 1.0 if data_type in {"int", "integer", "enum", "bool"} else None
    if step:
        base = minimum if minimum is not None else 0.0
        number = base + round((number - base) / step) * step
        if minimum is not None:
            number = max(number, minimum)
        if maximum is not None:
            number = min(number, maximum)
    return _coerce(round(number, 4), field)


# ---------------------------------------------------------------------
# 通用动作构造
# ---------------------------------------------------------------------
def _on_off_actions(
    context: DeviceContext,
    sid: str,
    field_name: str,
) -> tuple[Any, Any]:
    """Build (turn_on, turn_off) coroutines for a boolean characteristic."""

    field = _field(context.profile, sid, field_name)
    on_value = _enum_value(field, 1, 1)
    off_value = _enum_value(field, 0, 0)

    async def turn_on(device: DeviceContext, _data: Mapping[str, Any]) -> None:
        await device.async_send_service(sid, {field_name: on_value})

    async def turn_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
        await device.async_send_service(sid, {field_name: off_value})

    return turn_on, turn_off


def _make_switch(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
) -> EntitySpec:
    turn_on, turn_off = _on_off_actions(context, sid, field_name)
    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=lambda device: {"is_on": _bool(device.value(sid, field_name))},
        actions={"turn_on": turn_on, "turn_off": turn_off},
    )


# ---------------------------------------------------------------------
# climate 动作
# ---------------------------------------------------------------------
async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    turn_on, _ = _on_off_actions(context, "switch", "on")
    await turn_on(context, {})


async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    _, turn_off = _on_off_actions(context, "switch", "on")
    await turn_off(context, {})


async def _set_hvac_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    """Set the device mode; ``off`` is handled by the switch service."""

    wanted = str(data.get("hvac_mode"))
    if wanted == "off":
        await _turn_off(context, data)
        return
    device_value = _HVAC_TO_DEV.get(wanted)
    if device_value is None:
        raise ValueError(f"unsupported hvac_mode: {wanted}")
    field = _field(context.profile, "mode", "mode")
    await context.async_send_service(
        "mode", {"mode": _enum_value(field, device_value, device_value)}
    )
    # 补开机位：本机没有独立的"开机"服务，电源就是 switch.on。
    # 缺了这一步，空调处于关机态时从 HA 的模式下拉选模式不会启动空调
    # （与 2RK1 的真机结论一致）。模式枚举里没有 0/off，
    # 无法用模式表达关机，因此选模式必须显式置电源位。
    turn_on, _ = _on_off_actions(context, "switch", "on")
    await turn_on(context, {})


async def _set_temperature(context: DeviceContext, data: Mapping[str, Any]) -> None:
    raw = _number(data.get("temperature"))
    if raw is None:
        return
    field = _field(context.profile, "temperature", "target")
    value = _clamp(raw, field)
    if value is None:
        return
    await context.async_send_service("temperature", {"target": value})


async def _set_fan_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    wanted = str(data.get("fan_mode"))
    device_value = _FAN_TO_DEV.get(wanted)
    if device_value is None:
        raise ValueError(f"unsupported fan_mode: {wanted}")
    field = _field(context.profile, "freshAirgear", "gear")
    await context.async_send_service(
        "freshAirgear",
        {"gear": _enum_value(field, device_value, device_value)},
    )


async def _set_swing_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    """Project one HA swing_mode onto the two independent sweep services."""

    wanted = str(data.get("swing_mode"))
    flags = _SWING_TO_FLAGS.get(wanted)
    if flags is None:
        raise ValueError(f"unsupported swing_mode: {wanted}")
    vertical, horizontal = flags
    # 两侧都发送，避免目标为 0 时旧状态残留。
    vert_field = _field(context.profile, "sweepVertical", "on")
    horiz_field = _field(context.profile, "sweepHorizon", "on")
    await context.async_send_service(
        "sweepVertical",
        {"on": _enum_value(vert_field, vertical, vertical)},
    )
    await context.async_send_service(
        "sweepHorizon",
        {"on": _enum_value(horiz_field, horizontal, horizontal)},
    )


# ---------------------------------------------------------------------
# 实体构建
# ---------------------------------------------------------------------
def _make_sensor(
    sid: str,
    field_name: str,
    key: str,
    name: str,
    *,
    unit: str | None = None,
    device_class: str | None = None,
    state_class: str | None = None,
    entity_category: str | None = None,
    decode: Any = None,
) -> EntitySpec:
    decoder = decode or (lambda value: _number(value))

    def state(device: DeviceContext) -> Mapping[str, Any]:
        return {"native_value": decoder(device.value(sid, field_name))}

    metadata: dict[str, Any] = {}
    if unit is not None:
        metadata["unit"] = unit
    if device_class is not None:
        metadata["device_class"] = device_class
    if state_class is not None:
        metadata["state_class"] = state_class
    if entity_category is not None:
        metadata["entity_category"] = entity_category

    return EntitySpec(
        platform="sensor",
        key=key,
        name=name,
        state=state,
        metadata=metadata,
    )


class Product2NTIAdapter:
    """Keep all 2NTI entity and command choices in this file."""

    prod_id = "2NTI"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        # --- climate：模式 / 温度 / 风速 / 扫风 -----------------------
        if context.has_service("mode") and context.has_service("temperature"):
            fan_field = _field(profile, "freshAirgear", "gear")
            fan_labels = tuple(
                _DEV_TO_FAN[value]
                for value in sorted(_DEV_TO_FAN)
                if _enum_label(fan_field, value) is not None
            ) or tuple(_DEV_TO_FAN.values())
            # 只在设备确实提供扫风服务时才暴露 swing_mode。
            has_vertical = context.has_service("sweepVertical")
            has_horizontal = context.has_service("sweepHorizon")
            swing_labels: tuple[str, ...] = ()
            if has_vertical and has_horizontal:
                swing_labels = ("off", "vertical", "horizontal", "both")
            elif has_vertical:
                swing_labels = ("off", "vertical")
            elif has_horizontal:
                swing_labels = ("off", "horizontal")

            swing_allowed = set(swing_labels)

            def climate_state(device: DeviceContext) -> Mapping[str, Any]:
                power = _bool(device.value("switch", "on"))
                mode = _int(device.value("mode", "mode"))
                if power is False:
                    hvac_mode = "off"
                elif power is None and mode is None:
                    hvac_mode = None
                else:
                    hvac_mode = _DEV_TO_HVAC.get(mode)
                # 运行动作：本机没有独立的运行状态服务，仅按模式推断。
                if power is False or hvac_mode == "off":
                    action = "off"
                elif hvac_mode == "cool":
                    action = "cooling"
                elif hvac_mode == "heat":
                    action = "heating"
                elif hvac_mode == "dry":
                    action = "drying"
                elif hvac_mode == "fan_only":
                    action = "fan"
                elif hvac_mode == "auto":
                    action = "idle"
                else:
                    action = None
                gear = _int(device.value("freshAirgear", "gear"))
                swing_mode = None
                if swing_labels:
                    vertical = (
                        1 if _bool(device.value("sweepVertical", "on")) else 0
                    )
                    horizontal = (
                        1 if _bool(device.value("sweepHorizon", "on")) else 0
                    )
                    if not has_vertical:
                        vertical = 0
                    if not has_horizontal:
                        horizontal = 0
                    swing_mode = _FLAGS_TO_SWING.get((vertical, horizontal))
                    if swing_mode not in swing_allowed:
                        swing_mode = None
                return {
                    "hvac_mode": hvac_mode,
                    "hvac_action": action,
                    "current_temperature": _int(
                        device.value("temperature", "current")
                    ),
                    "target_temperature": _int(
                        device.value("temperature", "target")
                    ),
                    "fan_mode": _DEV_TO_FAN.get(gear),
                    "swing_mode": swing_mode,
                }

            climate_actions: dict[str, Any] = {
                "turn_on": _turn_on,
                "turn_off": _turn_off,
                "set_hvac_mode": _set_hvac_mode,
                "set_temperature": _set_temperature,
                "set_fan_mode": _set_fan_mode,
            }
            if swing_labels:
                climate_actions["set_swing_mode"] = _set_swing_mode

            climate_metadata: dict[str, Any] = {
                "hvac_modes": ["off", "auto", "cool", "heat", "dry", "fan_only"],
                "fan_modes": list(fan_labels),
                "min_temp": _TEMP_MIN,
                "max_temp": _TEMP_MAX,
            }
            if swing_labels:
                climate_metadata["swing_modes"] = list(swing_labels)

            entities.append(
                EntitySpec(
                    platform="climate",
                    key="air_conditioner",
                    name=None,
                    state=climate_state,
                    metadata=climate_metadata,
                    actions=climate_actions,
                )
            )

        # --- 独立开关 -------------------------------------------------
        for sid, field_name, key, name in _SWITCH_SPECS:
            field = _field(profile, sid, field_name)
            if context.has_service(sid) and _is_writable(field):
                entities.append(
                    _make_switch(context, sid, field_name, key, name)
                )

        # --- 扫风方向开关（与 climate 的 swing_mode 并存，便于分向控制）
        for sid, key, name in _SWEEP_SERVICES:
            if context.has_service(sid) and _is_writable(
                _field(profile, sid, "on")
            ):
                entities.append(_make_switch(context, sid, "on", key, name))

        # --- 传感器：温度 ---------------------------------------------
        if context.has_service("temperature"):
            entities.append(
                _make_sensor(
                    "temperature", "current", "current_temperature",
                    "室内温度", unit="°C", device_class="temperature",
                    state_class="measurement",
                    decode=_int,
                )
            )

        # --- 故障 -----------------------------------------------------
        if context.has_service("faultDetection"):
            code_field = _field(profile, "faultDetection", "code")

            def problem_state(device: DeviceContext) -> Mapping[str, Any]:
                status = _int(device.value("faultDetection", "status"))
                code = _int(device.value("faultDetection", "code"))
                # status 是权威的"是否有故障"标志；code 仅作描述。
                is_on = bool(status) if status is not None else bool(code)
                attributes: dict[str, Any] = {}
                if code is not None:
                    attributes["fault_code"] = code
                label = _enum_label(code_field, code)
                if label is not None and code != 0:
                    attributes["fault_description"] = label
                return {
                    "is_on": is_on,
                    "extra_state_attributes": attributes or None,
                }

            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="problem",
                    name="故障",
                    state=problem_state,
                    metadata={"device_class": "problem"},
                )
            )

        # --- 诊断实体（默认关闭，见文件头说明） ----------------------
        if _ENABLE_DIAGNOSTIC_ENTITIES:
            entities.extend(_make_diagnostic_entities(context))

        return tuple(entities)



def _make_diagnostic_entities(
    context: DeviceContext,
) -> tuple[EntitySpec, ...]:
    """Build the netInfo / update diagnostic entities.

    默认不创建（见 ``_ENABLE_DIAGNOSTIC_ENTITIES``）。代码保留是为了：
    若日后在真机上确认这些字段**确实会上报**，把开关打开即可恢复，
    无需重新实现。取值逻辑未做任何猜测，仍是按 Profile 的字段读取。
    """

    out: list[EntitySpec] = []

    # --- 网络诊断 -------------------------------------------------
    if context.has_service("netInfo"):
        out.append(
            _make_sensor(
                "netInfo", "intensity", "wifi_signal_level",
                "Wi-Fi 信号格数",
                state_class="measurement", entity_category="diagnostic",
                decode=lambda value: _SIGNAL_LEVELS.get(_int(value) or -1),
            )
        )
        out.append(
            _make_sensor(
                "netInfo", "RSSI", "wifi_rssi", "Wi-Fi 信号强度",
                unit="dBm", device_class="signal_strength",
                state_class="measurement", entity_category="diagnostic",
                decode=_int,
            )
        )
        out.append(
            _make_sensor(
                "netInfo", "IP", "ip_address", "IP 地址",
                entity_category="diagnostic", decode=_text,
            )
        )
        out.append(
            _make_sensor(
                "netInfo", "SSID", "wifi_ssid", "Wi-Fi SSID",
                entity_category="diagnostic", decode=_text,
            )
        )
        out.append(
            _make_sensor(
                "netInfo", "BSSID", "bssid", "路由器 BSSID",
                entity_category="diagnostic", decode=_text,
            )
        )

    # --- 固件版本（诊断） -----------------------------------------
    if context.has_service("update"):
        out.append(
            _make_sensor(
                "update", "version", "firmware_version", "固件版本",
                entity_category="diagnostic", decode=_text,
            )
        )

    return tuple(out)

ADAPTER = Product2NTIAdapter()
