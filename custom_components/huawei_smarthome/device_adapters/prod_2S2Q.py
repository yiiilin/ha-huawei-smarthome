"""User-contributed protocol for Huawei product 2S2Q (720智能空气净化器5).

产品: 720 智能空气净化器 5
厂商: 柒贰零 (720)
型号: KJ620F-E620 (deviceTypeId 013, 空气净化器, WiFi, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
**不跨产品复用**。2S2Q 与仓库既有 170W（同为 720 净化器）服务命名
完全不同（170W 用 airPurifying/wind/pm2p5，本机用 mode/fan/pm25），
字段类型与档位定义也不一致，故各自独立实现。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  switch.on              bool RW 电源开关            -> fan on/off
  mode.mode              enum RW 0=手动 1=自动 2=睡眠 5=节能
                                                     -> fan preset_mode
  fan.gear               enum RW 0~5 档              -> fan percentage
  fan.autoFanSwitch      bool RW 自动风速            -> auto_fan_switch

  airQuality.level       enum R 1=优 2=良 3=差        -> air_quality (sensor)
  pm25.current           int  R 0~1000 μg/m³         -> pm25
  pm25.level             enum R 1=优 2=良 3=差        -> pm25_level
  hcho.current           int  R 0~10000 μg/m³        -> hcho (甲醛)
  hcho.level             enum R 1=优 2=良 3=差        -> hcho_level
  humidity.current       int  R 0~1000 %             -> humidity
  humidity.level         enum RW 1=优 2=良 3=差       -> humidity_level (select)
  temperature.current    int  R -100~400 ℃           -> temperature
  outdoorPM25.current    int  R 0~1000 μg/m³         -> outdoor_pm25
  cav.current            float R 洁净空气体积 m³      -> clean_air_volume
  cmw.weight             int  R 洁净颗粒物重量 ug     -> clean_particle_weight
  workStatus.status      enum R 0=已关闭 1=已开启 2=待机中 -> work_status

  UVSwitch.on            bool RW 除菌(紫外线)         -> uv
  anionSwitch.on         bool RW 负离子               -> anion
  childLockSwitch.on     bool RW 童锁                 -> child_lock
  screenSwitch.on        bool RW 息屏                 -> screen
  lightSwitch.lightSwitch bool RW 氛围灯开关           -> ambient_light
  ambientLight.level     enum RW 0=低 1=中 2=强        -> ambient_light_level
  keyToneSwitch.on       bool RW 按键音               -> key_tone
  monitoringSwitch.on    bool RW 待机监测模式          -> monitoring

  ecoSetting.standbySet  enum RW 1=优 2=良 3=差       -> eco_standby_set
  ecoSetting.autoSet     enum RW 1=优 2=良 3=差       -> eco_auto_set
  ecoSetting.workStatus  enum R 0=待机 1=运行          -> eco_work_status

  filterElement1.leftPercentage int R 0~100 % 滤芯余量 -> filter_left_percentage
  filterElement1.leftTime       int R 0~9999 h 滤芯余时 -> filter_left_time
  filterElement1.alarm          bool R 1=有告警        -> filter_alarm
  filterElement1.reset          enum RW 1=耗材复位      -> button 滤芯复位
  filterElement1.filterType/name/id  R/RW/RW          不映射（静态元数据）

  faultDetection.status  enum R 0=正常 1=异常          -> problem (binary_sensor)
  faultDetection.code    enum R 0/100/101/102 故障码    -> 作为 problem 属性

  netInfo.*              网络                         -> 诊断传感器
  update.version         string R 固件版本             -> firmware_version

  capabilitySet.freshairfanSpeedSet string RW 能力位图  不映射，见下方说明
  outdoorPM25.cityCode   string RW 城市编码            不映射（需 App 选择城市）
  timer.*（定时）          array[object]               不映射（同其它机型理由）
  update.autoUpdateOn/progress/bootTime/introduction/action 不映射（OTA 运维）
  checkSum.checkSum      string R 固件校验值           不映射（内部校验值）

=====================================================================
风速用 fan 平台，档位映射为百分比
=====================================================================
本机 fan.gear 是 0~5 六档枚举（0=0档 … 5=5档），而 Profile 的档位名
就是"0档/1档/…/5档"。HA 的 fan 平台用百分比表达速度，故按
档位线性映射到 0~100%（每档 20%），并把档位名放进 preset_modes，
这样两种操作方式都可用：

    gear 0 -> 0%  gear 1 -> 20%  gear 2 -> 40%
    gear 3 -> 60% gear 4 -> 80%  gear 5 -> 100%

写入时把百分比反算回最接近的档位（四舍五入），保证下发的始终是
Profile 声明的合法枚举值。

注意 fan.autoFanSwitch（自动风速）是**独立开关**。Profile 明确写道
"智选产品自动风速后续使用新功能 fan/autoFanSwitch 来表示，将不再
使用枚举值 0 来表示自动风速"。因此本机 gear=0 是"0档风速"而**不是**
自动风；自动风由 autoFanSwitch 控制。本适配器据此把两者分开暴露，
不把 gear=0 当作 auto。

=====================================================================
为什么不映射 capabilitySet.freshairfanSpeedSet
=====================================================================
该字段是**位图能力集**（Profile descCh 逐位说明：
Bit0=自动 / Bit1=超低风 / Bit2=低风 / Bit3=中风 / Bit4=中高风 /
Bit5=高风 / Bit6=强风 / Bit7=超强风 / Bit8=无风）。
它的语义是"本机支持哪些风速档"，属于**能力声明**而非运行状态；
而且与 fan.gear（0~5 档）描述的档位集合**并不一致**，两者关系
未在 Profile 中说明。原样输出一串位图对用户没有可读性，
要做成有意义的实体需要拆 bit，属于额外投影决策，故不映射。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"2"``），
但 characteristicType 是 bool/enum/int/float，真机只接受**数值**。
直接把枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化。

``_enum_value()`` **只按 enumVal 精确匹配，不做 descCh/descEn
文本回退**——本机多个服务的枚举文案完全相同（如 airQuality/pm25/
hcho/ecoSetting 都是"优/良/差"），文本回退极易命中错误字段或档位
（2QWL 适配中踩过的真实 bug）。

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
[ ] 控制命令：fan 的开关/档位/预设模式、9 个 switch、4 个 select、
    1 个 button 均未实测。
[ ] **风速档位映射**：0~5 档线性映射到 0/20/40/60/80/100% 是投影
    决策（Profile 未定义档位与风量的数值关系）。真机上若发现
    档位与风量非线性，可改为只保留 preset_modes 而不暴露百分比。
[ ] **gear=0 的含义**：Profile 说明自动风改由 autoFanSwitch 表达，
    故本适配器把 gear=0 当"0档"而非"自动"。请在真机确认
    gear=0 是否真的代表最低档/静音，而不是自动风。
[ ] humidity.level 是 RW（可写），但本机没有"目标湿度"字段，
    该写入的真实作用未验证；当前做成 select，写入 1/2/3。
[ ] ecoSetting.standbySet / autoSet 的"空气质量条件"含义来自
    Profile 文字，具体触发阈值（对应多少 PM2.5）未给出，未验证。
[ ] 滤芯余量/余时的实际上报频率未验证；
    filterElement1.reset 写入后是否立即清零未验证。
[ ] 故障码 100/101/102 的清除条件未验证（100=仓门未关是瞬时态，
    101/102 是滤芯寿命类长期态）。
[ ] 空气质量/PM2.5/甲醛/湿度四个 level 字段都只有"优/良/差"三档，
    与 App 显示是否一致未验证。
[ ] outdoorPM25 依赖 cityCode（需在 App 设置城市）才会上报，
    本适配器不映射 cityCode，故户外 PM2.5 可能长期为空。
[ ] netInfo 各字段设备是否实际上报未验证（诊断类，不影响主功能）。
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


# --- 风速档位（fan.gear 0~5） <-> 百分比 ------------------------------
# Profile 的档位名就是 "0档".."5档"，共 6 档。线性映射到 0~100%。
_GEAR_MIN = 0
_GEAR_MAX = 5
_GEAR_STEP_PERCENT = 100 // (_GEAR_MAX - _GEAR_MIN)  # 20

# 预设模式名（取自 Profile 的档位 descCh）
_GEAR_PRESETS = tuple(f"{gear}档" for gear in range(_GEAR_MIN, _GEAR_MAX + 1))

# --- 净化器模式（mode.mode） ------------------------------------------
# 用 Profile 的 descCh 作 preset 名；数值即设备 enumVal。
_MODE_OPTIONS = (
    (0, "手动"),
    (1, "自动"),
    (2, "睡眠"),
    (5, "节能"),
)
_MODE_BY_LABEL = {label: raw for raw, label in _MODE_OPTIONS}
_MODE_BY_RAW = {str(raw): label for raw, label in _MODE_OPTIONS}

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# 简单布尔开关（sid, 字段名, key, 名称）
_SWITCH_SPECS = (
    ("UVSwitch", "on", "uv", "除菌(紫外线)"),
    ("anionSwitch", "on", "anion", "负离子"),
    ("childLockSwitch", "on", "child_lock", "童锁"),
    ("screenSwitch", "on", "screen", "息屏"),
    ("lightSwitch", "lightSwitch", "ambient_light", "氛围灯"),
    ("keyToneSwitch", "on", "key_tone", "按键音"),
    ("monitoringSwitch", "on", "monitoring", "待机监测"),
    ("fan", "autoFanSwitch", "auto_fan", "自动风速"),
)

# 空气质量类 level 枚举（优/良/差），多处复用同一刻度。
_LEVEL_LABELS = {1: "优", 2: "良", 3: "差"}


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
    """Encode a command value using the Profile-declared characteristic type."""

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

    只按 enumVal 精确匹配，**不做 descCh/descEn 文本回退**：
    本机 airQuality / pm25 / hcho / ecoSetting 的枚举文案完全相同
    （都是 优/良/差），文本匹配会命中错误字段或档位。
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


# ---------------------------------------------------------------------
# 档位 <-> 百分比
# ---------------------------------------------------------------------
def _gear_from_percentage(percentage: Any) -> int | None:
    """Map an HA fan percentage onto the nearest Profile gear."""

    number = _number(percentage)
    if number is None:
        return None
    number = min(max(number, 0.0), 100.0)
    gear = _GEAR_MIN + round((number / 100.0) * (_GEAR_MAX - _GEAR_MIN))
    return int(min(max(gear, _GEAR_MIN), _GEAR_MAX))


def _percentage_from_gear(gear: Any) -> int | None:
    """Map a reported Profile gear onto an HA fan percentage."""

    value = _int(gear)
    if value is None:
        return None
    value = min(max(value, _GEAR_MIN), _GEAR_MAX)
    return int(value * _GEAR_STEP_PERCENT)


# ---------------------------------------------------------------------
# 实体构造
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


def _make_level_select(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
) -> EntitySpec | None:
    """A select backed by a 优/良/差 style level enum."""

    field = _field(context.profile, sid, field_name)
    if field is None or not _is_writable(field):
        return None
    options: list[tuple[Any, str]] = []
    for option in field.get("enumList", ()):
        if not isinstance(option, Mapping):
            continue
        raw = option.get("enumVal")
        if raw is None:
            continue
        label = option.get("descCh") or option.get("descEn") or str(raw)
        options.append((raw, str(label)))
    if not options:
        return None
    labels = tuple(label for _, label in options)
    by_label = {label: raw for raw, label in options}
    by_raw = {str(raw): label for raw, label in options}

    def state(device: DeviceContext) -> Mapping[str, Any]:
        raw = device.value(sid, field_name)
        if raw is None:
            return {"current_option": None}
        return {"current_option": by_raw.get(str(_int(raw)))}

    async def select(device: DeviceContext, data: Mapping[str, Any]) -> None:
        wanted = str(data.get("option"))
        raw = by_label.get(wanted)
        if raw is None:
            raise ValueError(f"unsupported option for {sid}.{field_name}: {wanted}")
        await device.async_send_service(sid, {field_name: _coerce(raw, field)})

    return EntitySpec(
        platform="select",
        key=key,
        name=name,
        state=state,
        metadata={"options": labels},
        actions={"select_option": select},
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


def _make_enum_level_sensor(
    profile: Mapping[str, Any] | None,
    sid: str,
    field_name: str,
    key: str,
    name: str,
    *,
    entity_category: str | None = None,
) -> EntitySpec:
    """A read-only sensor showing a Profile level label with raw in attributes."""

    level_field = _field(profile, sid, field_name)

    def state(device: DeviceContext) -> Mapping[str, Any]:
        raw = _int(device.value(sid, field_name))
        if raw is None:
            return {"native_value": None}
        label = _enum_label(level_field, raw)
        if label is None:
            label = _LEVEL_LABELS.get(raw)
        return {
            "native_value": label if label is not None else raw,
            "extra_state_attributes": {"raw_level": raw},
        }

    metadata: dict[str, Any] = {}
    if entity_category is not None:
        metadata["entity_category"] = entity_category

    return EntitySpec(
        platform="sensor",
        key=key,
        name=name,
        state=state,
        metadata=metadata,
    )


class Product2S2QAdapter:
    """Keep all 2S2Q entity and command choices in this file."""

    prod_id = "2S2Q"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        # --- fan：电源 / 档位 / 预设模式 -------------------------------
        if context.has_service("switch"):
            gear_field = _field(profile, "fan", "gear")
            mode_field = _field(profile, "mode", "mode")
            power_field = _field(profile, "switch", "on")
            on_value = _enum_value(power_field, 1, 1)
            off_value = _enum_value(power_field, 0, 0)
            # --- 预设模式 -------------------------------------------------
            # fan 平台的 preset_mode 是单一列表，而本机有两组互相独立的
            # 概念要表达：
            #   * 净化器模式 mode.mode（手动/自动/睡眠/节能）
            #   * 风速档位 fan.gear（0档~5档）
            # 为避免歧义，档位预设统一加前缀 "风速:"；模式预设用原名。
            # 每组都只保留 Profile 真实声明的取值（从 enumVal 取，不用
            # 列表下标推断，避免枚举非连续时张冠李戴）。
            gear_values: tuple[int, ...] = ()
            if gear_field is not None:
                gear_values = tuple(
                    value
                    for value in sorted(
                        _int(option.get("enumVal"))
                        for option in gear_field.get("enumList", ())
                        if isinstance(option, Mapping)
                    )
                    if value is not None
                )
            gear_presets = tuple(f"风速:{value}档" for value in gear_values)

            mode_values: tuple[int, ...] = ()
            if mode_field is not None:
                mode_values = tuple(
                    value
                    for value in sorted(
                        _int(option.get("enumVal"))
                        for option in mode_field.get("enumList", ())
                        if isinstance(option, Mapping)
                    )
                    if value is not None
                )
            mode_labels = tuple(
                _MODE_BY_RAW[str(value)]
                for value in mode_values
                if str(value) in _MODE_BY_RAW
            )
            presets = mode_labels + gear_presets

            def fan_state(device: DeviceContext) -> Mapping[str, Any]:
                gear = device.value("fan", "gear")
                raw_mode = _int(device.value("mode", "mode"))
                return {
                    "is_on": _bool(device.value("switch", "on")),
                    "percentage": _percentage_from_gear(gear),
                    "preset_mode": _MODE_BY_RAW.get(str(raw_mode)),
                }

            async def turn_on(
                device: DeviceContext, data: Mapping[str, Any]
            ) -> None:
                await device.async_send_service(
                    "switch", {"on": on_value}
                )
                # fan 平台可能在开机时同时给出 presets/percentage。
                preset = data.get("preset_mode")
                percentage = data.get("percentage")
                if preset is not None:
                    await _apply_preset(device, preset)
                elif percentage is not None:
                    await _apply_percentage(device, percentage)

            async def turn_off(
                device: DeviceContext, _data: Mapping[str, Any]
            ) -> None:
                await device.async_send_service(
                    "switch", {"on": off_value}
                )

            async def _apply_percentage(
                device: DeviceContext, percentage: Any
            ) -> None:
                gear = _gear_from_percentage(percentage)
                if gear is None:
                    return
                await device.async_send_service(
                    "fan",
                    {"gear": _enum_value(gear_field, gear, gear)},
                )

            async def _apply_preset(
                device: DeviceContext, preset: Any
            ) -> None:
                wanted = str(preset)
                # 先试净化器模式（手动/自动/睡眠/节能）
                mode_raw = _MODE_BY_LABEL.get(wanted)
                if mode_raw is not None and str(mode_raw) in {
                    str(value) for value in mode_values
                }:
                    await device.async_send_service(
                        "mode",
                        {"mode": _enum_value(mode_field, mode_raw, mode_raw)},
                    )
                    return
                # 再试档位预设（"风速:N档"），直接从标签反解出真实档位值。
                if wanted.startswith("风速:") and wanted.endswith("档"):
                    body = wanted[len("风速:"):-len("档")]
                    gear = _int(body)
                    if gear is not None and gear in gear_values:
                        await device.async_send_service(
                            "fan",
                            {"gear": _enum_value(gear_field, gear, gear)},
                        )
                        return
                raise ValueError(f"unsupported preset_mode: {wanted}")

            async def set_percentage(
                device: DeviceContext, data: Mapping[str, Any]
            ) -> None:
                await _apply_percentage(device, data.get("percentage"))

            async def set_preset_mode(
                device: DeviceContext, data: Mapping[str, Any]
            ) -> None:
                await _apply_preset(device, data.get("preset_mode"))

            entities.append(
                EntitySpec(
                    platform="fan",
                    key="purifier",
                    name=None,
                    state=fan_state,
                    metadata={
                        "supports_percentage": True,
                        "percentage_step": _GEAR_STEP_PERCENT,
                        "preset_modes": list(presets),
                    },
                    actions={
                        "turn_on": turn_on,
                        "turn_off": turn_off,
                        "set_percentage": set_percentage,
                        "set_preset_mode": set_preset_mode,
                    },
                )
            )

        # --- 布尔开关 -------------------------------------------------
        for sid, field_name, key, name in _SWITCH_SPECS:
            field = _field(profile, sid, field_name)
            if context.has_service(sid) and _is_writable(field):
                entities.append(
                    _make_switch(context, sid, field_name, key, name)
                )

        # --- select ---------------------------------------------------
        for sid, field_name, key, name in (
            ("ambientLight", "level", "ambient_light_level", "氛围灯亮度"),
            ("humidity", "level", "humidity_level", "湿度等级"),
            ("ecoSetting", "standbySet", "eco_standby_set", "自动待机条件"),
            ("ecoSetting", "autoSet", "eco_auto_set", "自动运行条件"),
        ):
            if not context.has_service(sid):
                continue
            spec = _make_level_select(context, sid, field_name, key, name)
            if spec is not None:
                entities.append(spec)

        # --- 传感器：环境读数 -----------------------------------------
        if context.has_service("pm25"):
            entities.append(
                _make_sensor(
                    "pm25", "current", "pm25", "室内 PM2.5",
                    unit="µg/m³", device_class="pm25",
                    state_class="measurement", decode=_int,
                )
            )
            entities.append(
                _make_enum_level_sensor(
                    profile, "pm25", "level", "pm25_level", "PM2.5 等级"
                )
            )
        if context.has_service("hcho"):
            entities.append(
                _make_sensor(
                    "hcho", "current", "hcho", "甲醛",
                    unit="µg/m³", state_class="measurement", decode=_int,
                )
            )
            entities.append(
                _make_enum_level_sensor(
                    profile, "hcho", "level", "hcho_level", "甲醛等级"
                )
            )
        if context.has_service("airQuality"):
            entities.append(
                _make_enum_level_sensor(
                    profile, "airQuality", "level", "air_quality", "空气质量"
                )
            )
        if context.has_service("humidity"):
            entities.append(
                _make_sensor(
                    "humidity", "current", "humidity", "湿度",
                    unit="%", device_class="humidity",
                    state_class="measurement", decode=_int,
                )
            )
        if context.has_service("temperature"):
            entities.append(
                _make_sensor(
                    "temperature", "current", "temperature", "温度",
                    unit="°C", device_class="temperature",
                    state_class="measurement", decode=_int,
                )
            )
        if context.has_service("outdoorPM25"):
            entities.append(
                _make_sensor(
                    "outdoorPM25", "current", "outdoor_pm25", "户外 PM2.5",
                    unit="µg/m³", device_class="pm25",
                    state_class="measurement",
                    entity_category="diagnostic", decode=_int,
                )
            )
        if context.has_service("cav"):
            entities.append(
                _make_sensor(
                    "cav", "current", "clean_air_volume", "洁净空气体积",
                    unit="m³", state_class="total_increasing",
                    entity_category="diagnostic", decode=_number,
                )
            )
        if context.has_service("cmw"):
            entities.append(
                _make_sensor(
                    "cmw", "weight", "clean_particle_weight",
                    "洁净颗粒物重量", unit="µg",
                    state_class="total_increasing",
                    entity_category="diagnostic", decode=_int,
                )
            )

        # --- 运行状态 -------------------------------------------------
        if context.has_service("workStatus"):
            status_field = _field(profile, "workStatus", "status")

            def work_status_state(device: DeviceContext) -> Mapping[str, Any]:
                raw = _int(device.value("workStatus", "status"))
                if raw is None:
                    return {"native_value": None}
                label = _enum_label(status_field, raw)
                return {
                    "native_value": label if label is not None else raw,
                    "extra_state_attributes": {"raw_status": raw},
                }

            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="work_status",
                    name="运行状态",
                    state=work_status_state,
                    metadata={"entity_category": "diagnostic"},
                )
            )
        if context.has_service("ecoSetting"):
            eco_status_field = _field(profile, "ecoSetting", "workStatus")

            def eco_status_state(device: DeviceContext) -> Mapping[str, Any]:
                raw = _int(device.value("ecoSetting", "workStatus"))
                if raw is None:
                    return {"native_value": None}
                label = _enum_label(eco_status_field, raw)
                return {
                    "native_value": label if label is not None else raw,
                    "extra_state_attributes": {"raw_status": raw},
                }

            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="eco_work_status",
                    name="节能运行状态",
                    state=eco_status_state,
                    metadata={"entity_category": "diagnostic"},
                )
            )

        # --- 滤芯耗材 -------------------------------------------------
        if context.has_service("filterElement1"):
            if _field(profile, "filterElement1", "leftPercentage") is not None:
                entities.append(
                    _make_sensor(
                        "filterElement1", "leftPercentage",
                        "filter_left_percentage", "滤芯剩余",
                        unit="%", state_class="measurement", decode=_int,
                    )
                )
            if _field(profile, "filterElement1", "leftTime") is not None:
                entities.append(
                    _make_sensor(
                        "filterElement1", "leftTime", "filter_left_time",
                        "滤芯剩余时间", unit="h",
                        state_class="measurement",
                        entity_category="diagnostic", decode=_int,
                    )
                )
            if _field(profile, "filterElement1", "alarm") is not None:
                entities.append(
                    EntitySpec(
                        platform="binary_sensor",
                        key="filter_alarm",
                        name="滤芯告警",
                        state=lambda device: {
                            "is_on": _bool(
                                device.value("filterElement1", "alarm")
                            )
                        },
                        metadata={"device_class": "problem"},
                    )
                )
            reset_field = _field(profile, "filterElement1", "reset")
            if _is_writable(reset_field):
                reset_value = _enum_value(reset_field, 1, 1)

                async def reset_filter(
                    device: DeviceContext, _data: Mapping[str, Any]
                ) -> None:
                    await device.async_send_service(
                        "filterElement1", {"reset": reset_value}
                    )

                entities.append(
                    EntitySpec(
                        platform="button",
                        key="filter_reset",
                        name="滤芯复位",
                        state=lambda device: {},
                        actions={"press": reset_filter},
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

ADAPTER = Product2S2QAdapter()
