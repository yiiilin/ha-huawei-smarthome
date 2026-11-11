"""User-contributed protocol for Huawei product 2QMC (箭牌智能花洒).

产品: 箭牌智能花洒
厂商: 箭牌家居 (ARROW)
型号: HM-S01ZCP (deviceTypeId 300, 花洒, WiFi, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
不跨产品复用，不做未经 Profile/真机证据支持的推断。

=====================================================================
这个设备是什么
=====================================================================
「花洒精灵」：装在淋浴管路前的智能阀体。核心能力是
**冷水预排**——打开后先把管路里的冷水放掉，等热水到位后进入
**循环保温**，让你开龙头就有热水。它自带电池（无外接电源）。

因此本适配器的实体围绕这三件事组织：
  1. 预排 / 保温 的开关与时长（可写）
  2. 当前处于哪个阶段（只读状态机）
  3. 电池与故障（安全相关，只读）

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  battery.level            int  R 0~100 %           -> battery_level
  battery.alarm            bool R 1=低电量告警       -> low_battery (binary_sensor)

  coldWaterSwitch.on       bool RW 冷水预排开关      -> cold_water_switch
  coldWaterSwitch.offTimer int  RW 1~10 (最大排水时长) -> cold_water_off_timer
  circulationInsulationSwitch.on       bool RW 循环保温开关 -> insulation_switch
  circulationInsulationSwitch.offTimer int  RW 1~10 (保温时长) -> insulation_off_timer

  drainageDelay.time       int  RW 0~10 排水延时      -> drainage_delay

  switch2.on               bool RW 提示音            -> key_tone_switch
  screenSwitch.on          bool RW 花洒精灵屏幕      -> screen_switch

  status.status            enum R 0=空闲 1=保温中 2=预排水完成 3=预排水中 100=预警提示
                                                    -> shower_status (sensor)
  temperatureSetting.current float R 0~100 ℃ 当前出水温度 -> water_temperature
  commonFaultDetection.code enum R 0=正常 1~5 故障    -> problem + 故障描述属性

  netInfo.intensity        enum R 20/40/60/80/100    -> wifi_signal_level
  netInfo.RSSI             int  R -100~0 dBm         -> wifi_rssi
  netInfo.IP/SSID/BSSID    string R                  -> 诊断传感器
  update.version           string R 固件版本          -> firmware_version
  update.updatedVersion/progress/bootTime/introduction/action  不映射（OTA 流程）
  checkSum.checkSum        string R 固件校验值        不映射（内部校验值）
  timer.*（时间设置）       RW enum/int/array[object]  不映射，见下方说明

=====================================================================
关于名称：circulationInsulationSwitch 是"循环保温"不是"循环"
=====================================================================
该服务 descCh = "预排后循环保温开关"，on 的 attrName = "循环保温"，
offTimer = "保温时长(min)"。即：预排完成 → 进入保温循环 →
offTimer 到点后自动关闭。因此实体命名为"循环保温"，不要与
风扇/空调的"循环风"混淆。

=====================================================================
为什么把 offTimer 做成 number 而不是 select
=====================================================================
两个 offTimer 都是 int、RW、有明确 min/max（1~10），单位分别是
"最大排水时长"和"保温时长(min)"。这是连续可调量，HA 的 number
平台是正确投影（框架 metadata 需要 min/max/step，本 Profile 齐全）。
排水延时 drainageDelay.time（0~10）同理。

注意：Profile 未给这三个字段 unit，我在 metadata 里补了 "min"
（依据 descCh 中的"时长/延时"语义）。若真机单位不同需修正。

=====================================================================
为什么不映射 timer
=====================================================================
timer.array 是 ``array[object]``，元素含
enable/start/para/sid/end/week/id/paraValue 共 8 个字段，通过 mode
的 更新/新建/删除 驱动。正确写入必须先读取设备当前的定时列表、
按 id 增删改、再整体回写。本集成没有该"读-改-写"事务能力，
且写错会覆盖用户已配置的定时，风险高于收益，故不映射。
用户仍可在华为智慧生活 App 中配置定时。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"1"``），
但 characteristicType 是 bool/enum/int，真机只接受**数值**。
直接把枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化，
取值本身从 Profile 的 enumList 读取，不硬编码。

=====================================================================
安全相关的取舍
=====================================================================
本设备涉及**出水**。因此：
  * 所有阀门类写入（预排/保温开关、两个时长、排水延时）
    一律严格按 Profile 的 min/max 夹取，绝不越界下发；
  * 故障码（出水温度过高、预排冷水异常等）以 binary_sensor
    device_class=problem 呈现，便于自动化联动告警；
  * 不臆造任何"开机即排空"之类的复合动作——一次动作只写一个
    服务，避免自动化误触发导致意外放水。

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
真机实测记录
=====================================================================
验证环境：真实设备（箭牌智能花洒 HM-S01ZCP）+ 智慧生活 App 对照。

[已实测] 实体创建与状态读取：**通过**。花洒状态、出水温度、电池电量与
    故障告警的显示与 App 一致。
[已实测] 控制命令：**通过**。冷水预排 / 循环保温 两个开关，以及三个时长
    （最大排水 / 保温 / 排水延时）的写入均已确认生效。
[已实测] 上面「高风险项」已逐项确认。

以下为**尚未覆盖的细节**，与上表不冲突（它们不是"没验过"，
而是当时没有专门做实验去区分）：

=====================================================================
尚未覆盖的细节（如需可再确认）
=====================================================================
[ ] 三个时长字段（two offTimer + drainageDelay）的单位：Profile 未声明
    unit，本适配器按 descCh 语义填 "min"。若真机是秒或其它单位需修正。
[ ] status 与两个开关的联动关系：例如预排结束后
    coldWaterSwitch.on 是否自动回落为 0。当前只如实投影状态机，
    不做事后推断。
[ ] status=100（预警提示）的具体含义未在 Profile 中说明，
    本适配器原样输出该标签，未做额外处理。
[ ] battery.level 的实际上报频率与精度（电池供电设备，
    可能为省电而降低上报频率）。
[ ] 故障码 code 与 status 无联动字段，仅 code 一个来源；
    若真机只在故障时上报 code 而恢复后不再上报，problem 可能
    长期保持 on（与告警类字段同类的"一次性信号"问题）。
[ ] netInfo 各字段设备是否实际上报；若不上报将长期为
    unknown（诊断类，不影响主功能）。
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


# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# status.status 枚举 -> 中文标签。取值来自本机 Profile，不跨产品复用。
_STATUS_LABELS = {
    0: "空闲",
    1: "保温中",
    2: "预排水完成",
    3: "预排水中",
    100: "预警提示",
}

# 布尔开关服务（sid, 字段名, key, 名称）
_SWITCH_SPECS = (
    ("coldWaterSwitch", "on", "cold_water", "冷水预排"),
    ("circulationInsulationSwitch", "on", "insulation", "循环保温"),
    ("switch2", "on", "key_tone", "提示音"),
    ("screenSwitch", "on", "screen", "屏幕"),
)

# 整数可调项（sid, 字段名, key, 名称, 缺省 min/max）
_NUMBER_SPECS = (
    ("coldWaterSwitch", "offTimer", "cold_water_timer", "最大排水时长", 1, 10),
    (
        "circulationInsulationSwitch",
        "offTimer",
        "insulation_timer",
        "保温时长",
        1,
        10,
    ),
    ("drainageDelay", "time", "drainage_delay", "排水延时", 0, 10),
)


# ---------------------------------------------------------------------
# 取值解码
# ---------------------------------------------------------------------
def _bool(value: Any) -> bool | None:
    """Decode a Huawei bool/enum characteristic into a Python bool."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.casefold() in {"1", "true", "on"}:
            return True
        if value.casefold() in {"0", "false", "off"}:
            return False
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
    """Resolve the Profile-declared enum value matching ``wanted``."""

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
            if str(wanted) in {
                str(option.get("descCh") or ""),
                str(option.get("descEn") or ""),
            }:
                raw = candidate
                break
    return _coerce(raw, field)


def _enum_label(
    field: Mapping[str, Any] | None,
    value: Any,
) -> str | None:
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


def _clamp(value: Any, field: Mapping[str, Any] | None, low: Any, high: Any) -> Any:
    """Clamp a numeric write to the Profile-declared range and step.

    出水相关设备一律严格夹取，绝不越界下发。
    Profile 里这些字段都是 int + step=1，因此按步进对齐后再编码，
    避免下发 5.7 这类设备不接受的小数。
    """

    number = _number(value)
    if number is None:
        return None
    minimum = _number((field or {}).get("min"))
    maximum = _number((field or {}).get("max"))
    lo = minimum if minimum is not None else float(low)
    hi = maximum if maximum is not None else float(high)
    if hi < lo:
        lo, hi = hi, lo
    number = min(max(number, lo), hi)
    step = _number((field or {}).get("step"))
    if step is None or step <= 0:
        # Profile 未声明 step 时，按 characteristicType 决定对齐粒度。
        data_type = str((field or {}).get("characteristicType") or "").casefold()
        step = 1.0 if data_type in {"int", "integer", "enum", "bool"} else None
    if step:
        number = lo + round((number - lo) / step) * step
        number = min(max(number, lo), hi)
    return _coerce(round(number, 4), field)


# ---------------------------------------------------------------------
# 实体构建
# ---------------------------------------------------------------------
def _make_switch(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
) -> EntitySpec:
    field = _field(context.profile, sid, field_name)
    on_value = _enum_value(field, 1, 1)
    off_value = _enum_value(field, 0, 0)

    async def turn_on(device: DeviceContext, _data: Mapping[str, Any]) -> None:
        await device.async_send_service(sid, {field_name: on_value})

    async def turn_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
        await device.async_send_service(sid, {field_name: off_value})

    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=lambda device: {"is_on": _bool(device.value(sid, field_name))},
        actions={"turn_on": turn_on, "turn_off": turn_off},
    )


def _make_number(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
    default_low: int,
    default_high: int,
) -> EntitySpec:
    field = _field(context.profile, sid, field_name)
    minimum = _number((field or {}).get("min"))
    maximum = _number((field or {}).get("max"))
    step = _number((field or {}).get("step"))
    low = minimum if minimum is not None else float(default_low)
    high = maximum if maximum is not None else float(default_high)

    async def set_value(device: DeviceContext, data: Mapping[str, Any]) -> None:
        value = _clamp(data.get("value"), field, low, high)
        if value is None:
            return
        await device.async_send_service(sid, {field_name: value})

    def state(device: DeviceContext) -> Mapping[str, Any]:
        return {"native_value": _number(device.value(sid, field_name))}

    return EntitySpec(
        platform="number",
        key=key,
        name=name,
        state=state,
        metadata={
            "min": low,
            "max": high,
            "step": step if step and step > 0 else 1,
            # Profile 未声明 unit；按 descCh 的"时长/延时"语义补 min。
            "unit": "min",
        },
        actions={"set_value": set_value},
    )


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


class Product2QMCAdapter:
    """Keep all 2QMC entity and command choices in this file."""

    prod_id = "2QMC"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        # --- 控制开关 -------------------------------------------------
        for sid, field_name, key, name in _SWITCH_SPECS:
            if context.has_service(sid) and _field(profile, sid, field_name):
                entities.append(
                    _make_switch(context, sid, field_name, key, name)
                )

        # --- 可调时长 -------------------------------------------------
        for sid, field_name, key, name, low, high in _NUMBER_SPECS:
            if context.has_service(sid) and _field(profile, sid, field_name):
                entities.append(
                    _make_number(
                        context, sid, field_name, key, name, low, high
                    )
                )

        # --- 花洒状态机 -----------------------------------------------
        if context.has_service("status"):
            status_field = _field(profile, "status", "status")

            def status_state(device: DeviceContext) -> Mapping[str, Any]:
                raw = _int(device.value("status", "status"))
                if raw is None:
                    return {"native_value": None}
                # 优先用 Profile 的 descCh，保持与 App 措辞一致；
                # Profile 缺标签时回退到本文件内置表。
                label = _enum_label(status_field, raw)
                if label is None:
                    label = _STATUS_LABELS.get(raw)
                attributes: dict[str, Any] = {"raw_status": raw}
                return {
                    "native_value": label if label is not None else raw,
                    "extra_state_attributes": attributes,
                }

            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="shower_status",
                    name="花洒状态",
                    state=status_state,
                )
            )

        # --- 水温 -----------------------------------------------------
        if context.has_service("temperatureSetting"):
            entities.append(
                _make_sensor(
                    "temperatureSetting", "current", "water_temperature",
                    "出水温度", unit="°C", device_class="temperature",
                    state_class="measurement",
                    decode=_number,
                )
            )

        # --- 电池 -----------------------------------------------------
        if context.has_service("battery"):
            if _field(profile, "battery", "level") is not None:
                entities.append(
                    _make_sensor(
                        "battery", "level", "battery_level", "电池电量",
                        unit="%", device_class="battery",
                        state_class="measurement",
                        decode=_int,
                    )
                )
            if _field(profile, "battery", "alarm") is not None:
                entities.append(
                    EntitySpec(
                        platform="binary_sensor",
                        key="low_battery",
                        name="低电量告警",
                        state=lambda device: {
                            "is_on": _bool(device.value("battery", "alarm"))
                        },
                        metadata={"device_class": "battery"},
                    )
                )

        # --- 故障 -----------------------------------------------------
        if context.has_service("commonFaultDetection"):
            code_field = _field(profile, "commonFaultDetection", "code")

            def problem_state(device: DeviceContext) -> Mapping[str, Any]:
                code = _int(device.value("commonFaultDetection", "code"))
                attributes: dict[str, Any] = {}
                if code is not None:
                    attributes["fault_code"] = code
                label = _enum_label(code_field, code)
                if label is not None and code != 0:
                    attributes["fault_description"] = label
                return {
                    # 0=正常，其余为具体故障码。
                    "is_on": None if code is None else code != 0,
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

ADAPTER = Product2QMCAdapter()
