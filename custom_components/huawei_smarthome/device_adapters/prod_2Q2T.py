"""User-contributed protocol for Huawei product 2Q2T (MEIPONT智能空调 风神之眼).

产品: MEIPONT 智能空调 风神之眼（挂机空调）
厂商: 美邦电器 (meipont)
型号: MAC35V1P80HR (deviceTypeId 012, 挂机空调, Wi-Fi+BLE+SLE, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
不跨产品复用，不做未经 Profile/真机证据支持的推断。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  switch.on                 bool  RW 1=开 0=关        主开关       -> climate 的 on/off

  mode.mode                 enum  RW 1=自动 2=制冷 3=制热 4=送风 5=除湿
                                                      -> climate hvac_mode
  temperature.target        float RW 16.0~32.0 步进0.5 ℃  -> climate target
  temperature.current       float R  室内温度 ℃        -> climate current
  temperature.out           float R  外机温度 ℃        -> outdoor_temperature

  fan.gear                  enum  RW 0=自动 1=静音 2=低 3=中 4=高 5=强劲
                                                      -> climate fan_mode
  fan.direction             enum  RW 1=固定 2=左右扫风 3=上下扫风 4=全面扫风
                                      5=风随人动 6=风避人吹 7=天幕风地毯风
                                      8=轻风感 9=人近风柔  -> climate swing_mode
  fan.verticalDirection     enum  RW 0=上下扫风 1=最上 ... 11=上下固定
                                      -> vertical_direction (select)
  fan.horizontalDirection   enum  RW 0=左右扫风 1=最左 ... 11=左右固定
                                      -> horizontal_direction (select)
  fan.on                    bool  RW AI舒适风开关        -> ai_comfort_switch

  switchScreen.on           bool  RW 屏显开关            -> screen_switch
  keyToneSwitch.on          bool  RW 提示音开关          -> key_tone_switch
  switchPTC.on              bool  RW 电辅热开关          -> ptc_switch
  favoriteModeSwitch.on     bool  RW 常用模式开关        -> favorite_mode_switch

  sceneMode.mode            enum  RW 0=关闭 1=AI节能 3=睡眠 20=自清洁
                                                      -> scene_mode (select)

  electric.day              float R  当日用电 kWh       -> today_energy
  runtime.runtime           int   R  单日运行时长 min    -> today_runtime
  preTime.preEndTime        int   RW 上次倒计时 min      不映射（App 表单记忆项）

  status.mode               enum  R  0=默认 1=化霜中     -> hvac_action (defrosting)
  commonFaultDetection.code enum  R  0=正常 1..14 故障码  -> fault_code + 故障描述
  commonFaultDetection.status bool R 1=异常 0=正常      -> problem (binary_sensor)

  netInfo.intensity         enum  R  20/40/60/80/100   -> wifi_signal_level
  netInfo.RSSI              int   R  -100~0 dBm        -> wifi_rssi
  netInfo.IP / SSID / BSSID string R                   -> 诊断传感器

  update.version            string R 固件版本           -> firmware_version
  update.progress/bootTime/introduction/action         不映射（OTA 流程）
  checkSum.checkSum         string R 固件校验          不映射（内部校验值）

  favoriteMode.trigger/config  RW 常用模式保存/回放     不映射，见下方说明
  timer.*（定时器服务）        RW array[object]         不映射，见下方说明
  delay.*（倒计时）            RW array[object]         不映射，见下方说明

=====================================================================
为什么不映射 timer / delay / favoriteMode
=====================================================================
1. timer.timer 与 delay.delay 是 ``array[object]``，元素结构含
   enable/start/end/para/sid/id/week/paraValue 共 8~9 个字段，
   且 create/delete/update 通过 action 枚举驱动。要正确写入必须先
   读取设备当前的定时器列表、按 id 增删改、再整体回写。
   本集成没有该"读-改-写"事务能力，且写错会覆盖用户已配置的定时，
   风险高于收益，故不映射。用户仍可在华为智慧生活 App 中配置定时。

2. favoriteMode.trigger 只有 ``0=保存`` 一个枚举值，语义是"把当前状态
   存为常用模式"；config 是 1024 字符的配置串，含义未在 Profile 中定义。
   缺少 config 的结构定义，无法安全构造回放请求，故不映射。

3. preTime.preEndTime 是 App 侧"上次设置的倒计时时长"记忆项，
   仅用于下次打开表单时预填，不是设备运行状态，无 HA 侧价值。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"2"``），
但 characteristicType 是 bool/enum/int，真机只接受**数值**。
直接把枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化，
取值本身从 Profile 的 enumList 读取，不硬编码。

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
[ ] 控制命令：climate 的开关/模式/温度/风速/摆风写入，以及各 switch、
    select 实体，均未实测。
[ ] 温度步进：Profile 声明 step=0.5、范围 16.0~32.0。写温度时按 0.5
    对齐并夹取到该范围；若真机实际范围更窄（常见 16~30），需真机调整。
[ ] swing_mode 的取值来自 fan.direction（1~9）。其中 5~9（风随人动、
    风避人吹、天幕风地毯风、轻风感、人近风柔）是"感知类"高级模式，
    是否与普通扫风互斥、能否直接写入，未验证。
[ ] fan.on（AI舒适风）与 fan.gear/fan.direction 是否互相覆盖未验证，
    当前按独立开关处理。
[ ] 化霜状态（status.mode=1）映射为 hvac_action="defrosting"，
    HA 的 HVACAction 是否接受该值需实机确认（若 HA 报错则改为不映射）。
[ ] 故障码 code 与 status 的关系未验证：当前以 status==1 作为 problem，
    code 作为故障描述文本；若真机出现 status=0 但 code!=0 的情况，
    需改为以 code 为准。
[ ] 电量统计 electric.day 与运行时长 runtime.runtime 设备是否上报未验证；
    若不上报将长期为 unknown（不影响主功能）。
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


# --- 温度范围：直接取自 Profile 的 min/max/step -----------------------
_TEMP_MIN = 16.0
_TEMP_MAX = 32.0
_TEMP_STEP = 0.5

# mode.mode -> HA HVACMode
_DEV_TO_HVAC = {1: "auto", 2: "cool", 3: "heat", 4: "fan_only", 5: "dry"}
_HVAC_TO_DEV = {value: key for key, value in _DEV_TO_HVAC.items()}

# fan.gear -> HA 风速名（用 Profile 的中文档位名，直观且与 App 一致）
_DEV_TO_FAN = {
    0: "自动",
    1: "静音",
    2: "低档",
    3: "中档",
    4: "高档",
    5: "强劲",
}
_FAN_TO_DEV = {value: key for key, value in _DEV_TO_FAN.items()}

# fan.direction -> HA 摆风模式名（用 Profile 的中文枚举名）。
_SWING_TO_DEV = {
    "固定": 1,
    "左右扫风": 2,
    "上下扫风": 3,
    "全面扫风": 4,
    "风随人动": 5,
    "风避人吹": 6,
    "天幕风地毯风": 7,
    "轻风感": 8,
    "人近风柔": 9,
}
_DEV_TO_SWING = {value: key for key, value in _SWING_TO_DEV.items()}

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# 需要以 switch 实体暴露的简单布尔服务（sid, key, 名称）。
_SWITCH_SPECS = (
    ("switchScreen", "screen", "屏显"),
    ("keyToneSwitch", "key_tone", "提示音"),
    ("switchPTC", "ptc", "电辅热"),
    ("favoriteModeSwitch", "favorite_mode", "常用模式"),
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


def _as_int(value: Any) -> int | None:
    """Int decoder that also accepts the string shapes seen in the cloud."""

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        try:
            return int(round(float(value.strip())))
        except (TypeError, ValueError):
            return None
    return _int(value)


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
    """Resolve the Profile-declared enum value matching ``wanted``.

    优先按 descCh/descEn 匹配（便于用可读名字查表），其次按 enumVal 匹配，
    最后回退到 fallback。返回值一律经 _coerce() 编码。
    """

    raw: Any = fallback
    if isinstance(field, Mapping):
        for option in field.get("enumList", ()):
            if not isinstance(option, Mapping):
                continue
            candidate = option.get("enumVal")
            if candidate is None:
                continue
            labels = {
                str(candidate),
                str(option.get("descCh") or ""),
                str(option.get("descEn") or ""),
            }
            if str(wanted) in labels:
                raw = candidate
                break
    return _coerce(raw, field)


def _enum_options(
    field: Mapping[str, Any] | None,
) -> tuple[tuple[str, Any], ...]:
    """Return ``(label, raw_enum_value)`` pairs from a Profile enum list.

    label 优先取 descCh（中文），缺失时退回 enumVal。
    """

    options: list[tuple[str, Any]] = []
    if not isinstance(field, Mapping):
        return ()
    for option in field.get("enumList", ()):
        if not isinstance(option, Mapping):
            continue
        raw = option.get("enumVal")
        if raw is None:
            continue
        label = option.get("descCh") or option.get("descEn") or str(raw)
        options.append((str(label), raw))
    return tuple(options)


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


# ---------------------------------------------------------------------
# climate 动作
# ---------------------------------------------------------------------
def _switch_field(context: DeviceContext) -> Mapping[str, Any] | None:
    return _field(context.profile, "switch", "on")


async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    field = _switch_field(context)
    await context.async_send_service(
        "switch", {"on": _enum_value(field, "开", 1)}
    )


async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    field = _switch_field(context)
    await context.async_send_service(
        "switch", {"on": _enum_value(field, "关", 0)}
    )


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
    await context.async_send_service(
        "switch", {"on": _enum_value(_switch_field(context), "开", 1)}
    )


async def _set_temperature(context: DeviceContext, data: Mapping[str, Any]) -> None:
    raw = _number(data.get("temperature"))
    if raw is None:
        return
    field = _field(context.profile, "temperature", "target")
    minimum = _number((field or {}).get("min"))
    maximum = _number((field or {}).get("max"))
    step = _number((field or {}).get("step"))
    low = minimum if minimum is not None else _TEMP_MIN
    high = maximum if maximum is not None else _TEMP_MAX
    size = step if step and step > 0 else _TEMP_STEP
    target = min(max(raw, low), high)
    # 按 Profile 步进对齐，避免发出设备不接受的小数位。
    target = low + round((target - low) / size) * size
    target = round(target, 2)
    await context.async_send_service("temperature", {"target": target})


async def _set_fan_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    wanted = str(data.get("fan_mode"))
    device_value = _FAN_TO_DEV.get(wanted)
    if device_value is None:
        raise ValueError(f"unsupported fan_mode: {wanted}")
    field = _field(context.profile, "fan", "gear")
    await context.async_send_service(
        "fan", {"gear": _enum_value(field, device_value, device_value)}
    )


async def _set_swing_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    wanted = str(data.get("swing_mode"))
    device_value = _SWING_TO_DEV.get(wanted)
    if device_value is None:
        raise ValueError(f"unsupported swing_mode: {wanted}")
    field = _field(context.profile, "fan", "direction")
    await context.async_send_service(
        "fan", {"direction": _enum_value(field, device_value, device_value)}
    )


# ---------------------------------------------------------------------
# 实体构建
# ---------------------------------------------------------------------
def _make_bool_switch(
    context: DeviceContext,
    sid: str,
    key: str,
    name: str,
) -> EntitySpec:
    field = _field(context.profile, sid, "on")
    on_value = _enum_value(field, "开", 1)
    off_value = _enum_value(field, "关", 0)

    async def turn_on(device: DeviceContext, _data: Mapping[str, Any]) -> None:
        await device.async_send_service(sid, {"on": on_value})

    async def turn_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
        await device.async_send_service(sid, {"on": off_value})

    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=lambda device: {"is_on": _bool(device.value(sid, "on"))},
        actions={"turn_on": turn_on, "turn_off": turn_off},
    )


def _make_enum_select(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
) -> EntitySpec | None:
    """One ``select`` entity backed by an RW enum characteristic."""

    field = _field(context.profile, sid, field_name)
    options = _enum_options(field)
    if not options:
        return None
    labels = tuple(label for label, _ in options)
    label_to_raw = {label: raw for label, raw in options}
    raw_to_label = {str(raw): label for label, raw in options}

    def state(device: DeviceContext) -> Mapping[str, Any]:
        raw = device.value(sid, field_name)
        if raw is None:
            return {"current_option": None}
        return {"current_option": raw_to_label.get(str(raw))}

    async def select(device: DeviceContext, data: Mapping[str, Any]) -> None:
        wanted = str(data.get("option"))
        raw = label_to_raw.get(wanted)
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


class Product2Q2TAdapter:
    """Keep all 2Q2T entity and command choices in this file."""

    prod_id = "2Q2T"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        # --- climate：模式 / 温度 / 风速 / 摆风 -----------------------
        if context.has_service("mode") and context.has_service("temperature"):
            fan_field = _field(profile, "fan", "gear")
            fan_labels = tuple(
                _DEV_TO_FAN[value]
                for value in sorted(_DEV_TO_FAN)
                if _enum_label(fan_field, value) is not None
            ) or tuple(_DEV_TO_FAN.values())
            # swing 列表：以 Profile 的 direction 枚举为准，只保留设备真正
            # 声明且我方有映射的档位，避免出现选了却写不进去的选项。
            direction_field = _field(profile, "fan", "direction")
            swing_labels = tuple(
                _DEV_TO_SWING[value]
                for value in sorted(_DEV_TO_SWING)
                if _enum_label(direction_field, value) is not None
            ) or tuple(_SWING_TO_DEV)

            def climate_state(device: DeviceContext) -> Mapping[str, Any]:
                power = _bool(device.value("switch", "on"))
                mode = _as_int(device.value("mode", "mode"))
                if power is False:
                    hvac_mode = "off"
                elif power is None and mode is None:
                    hvac_mode = None
                else:
                    hvac_mode = _DEV_TO_HVAC.get(mode)
                if hvac_mode is None and power is not False:
                    # 开机但模式未知：交给 HA 用首个 hvac_mode 兜底。
                    hvac_mode = _DEV_TO_HVAC.get(mode, None)
                status = _as_int(device.value("status", "mode"))
                action = None
                if hvac_mode == "off" or power is False:
                    action = "off"
                elif status == 1:
                    action = "defrosting"
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
                gear = _as_int(device.value("fan", "gear"))
                direction = _as_int(device.value("fan", "direction"))
                return {
                    "hvac_mode": hvac_mode,
                    "hvac_action": action,
                    "current_temperature": _number(
                        device.value("temperature", "current")
                    ),
                    "target_temperature": _number(
                        device.value("temperature", "target")
                    ),
                    "fan_mode": _DEV_TO_FAN.get(gear),
                    "swing_mode": _DEV_TO_SWING.get(direction),
                }

            entities.append(
                EntitySpec(
                    platform="climate",
                    key="air_conditioner",
                    name=None,
                    state=climate_state,
                    metadata={
                        "hvac_modes": [
                            "off",
                            "auto",
                            "cool",
                            "heat",
                            "dry",
                            "fan_only",
                        ],
                        "fan_modes": list(fan_labels),
                        "swing_modes": list(swing_labels),
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
            )

        # --- 独立开关 -------------------------------------------------
        for sid, key, name in _SWITCH_SPECS:
            if context.has_service(sid):
                entities.append(_make_bool_switch(context, sid, key, name))

        # fan.on 是 AI 舒适风开关，与 climate 的风速/摆风独立。
        if context.has_service("fan"):
            ai_field = _field(profile, "fan", "on")
            if ai_field is not None:
                ai_on = _enum_value(ai_field, "开", 1)
                ai_off = _enum_value(ai_field, "关", 0)

                async def ai_turn_on(
                    device: DeviceContext, _data: Mapping[str, Any]
                ) -> None:
                    await device.async_send_service("fan", {"on": ai_on})

                async def ai_turn_off(
                    device: DeviceContext, _data: Mapping[str, Any]
                ) -> None:
                    await device.async_send_service("fan", {"on": ai_off})

                entities.append(
                    EntitySpec(
                        platform="switch",
                        key="ai_comfort",
                        name="AI舒适风",
                        state=lambda device: {
                            "is_on": _bool(device.value("fan", "on"))
                        },
                        actions={
                            "turn_on": ai_turn_on,
                            "turn_off": ai_turn_off,
                        },
                    )
                )

        # --- select：情景模式 / 垂直风向 / 水平风向 -------------------
        if context.has_service("sceneMode"):
            spec = _make_enum_select(
                context, "sceneMode", "mode", "scene_mode", "情景模式"
            )
            if spec is not None:
                entities.append(spec)
        if context.has_service("fan"):
            for field_name, key, name in (
                ("verticalDirection", "vertical_direction", "垂直风向"),
                ("horizontalDirection", "horizontal_direction", "水平风向"),
            ):
                spec = _make_enum_select(
                    context, "fan", field_name, key, name
                )
                if spec is not None:
                    entities.append(spec)

        # --- 传感器：温度 / 电量 / 运行时长 ---------------------------
        if context.has_service("temperature"):
            entities.append(
                _make_sensor(
                    "temperature", "current", "current_temperature",
                    "室内温度", unit="°C", device_class="temperature",
                    state_class="measurement",
                )
            )
            entities.append(
                _make_sensor(
                    "temperature", "out", "outdoor_temperature",
                    "外机温度", unit="°C", device_class="temperature",
                    state_class="measurement",
                    entity_category="diagnostic",
                )
            )
        if context.has_service("electric"):
            entities.append(
                _make_sensor(
                    "electric", "day", "today_energy", "当日用电",
                    unit="kWh", device_class="energy", state_class="total",
                )
            )
        if context.has_service("runtime"):
            entities.append(
                _make_sensor(
                    "runtime", "runtime", "today_runtime", "当日运行时长",
                    unit="min", device_class="duration",
                    state_class="total",
                    entity_category="diagnostic",
                    # Profile 声明为 int，避免显示成 320.0。
                    decode=lambda value: _int(value),
                )
            )

        # --- 故障 -----------------------------------------------------
        if context.has_service("commonFaultDetection"):
            code_field = _field(profile, "commonFaultDetection", "code")

            def problem_state(device: DeviceContext) -> Mapping[str, Any]:
                status = _bool(
                    device.value("commonFaultDetection", "status")
                )
                code = _as_int(
                    device.value("commonFaultDetection", "code")
                )
                # status 是权威的"是否有故障"标志；code 仅作描述。
                is_on = status if status is not None else bool(code)
                attributes: dict[str, Any] = {}
                if code is not None:
                    attributes["fault_code"] = code
                description = _enum_label(code_field, code)
                if description is not None and str(code) != "0":
                    attributes["fault_description"] = (
                        description.split("，")[0].strip()
                    )
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
                decode=lambda value: _SIGNAL_LEVELS.get(_as_int(value) or -1),
            )
        )
        out.append(
            _make_sensor(
                "netInfo", "RSSI", "wifi_rssi", "Wi-Fi 信号强度",
                unit="dBm", device_class="signal_strength",
                state_class="measurement", entity_category="diagnostic",
                decode=lambda value: _as_int(value),
            )
        )
        out.append(
            _make_sensor(
                "netInfo", "IP", "ip_address", "IP 地址",
                entity_category="diagnostic",
                decode=_text,
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

ADAPTER = Product2Q2TAdapter()
