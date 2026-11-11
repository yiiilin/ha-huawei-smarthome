"""User-contributed protocol for Huawei product 2REC (美的智能空调 鸿蒙空气机Pro).

产品: 美的智能空调 鸿蒙空气机 Pro（挂机/空气机）
厂商: 美的 (midea)
型号: KFR-35G/HWR7 (deviceTypeId 012, 挂机空调, WiFi, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
**不跨产品复用**。2REC 是"空气机"（空调 + 新风 + 净化 + 除菌 + 加湿），
服务数 32，远超此前的 2Q2T/2NJN/2RK1/2NTI，故独立实现。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  switch.on              bool RW 总开关              -> climate on/off
  mode.mode              enum RW 运行模式（见下方）   -> climate hvac_mode
  temperature.target     float RW 16.0~30.0 步进0.5  -> climate target
  temperature.current    float R  室内温度           -> climate current
  fan.gear               enum RW 0=自动 1=静音 2=低 3=中 4=高 5=超强
                                                     -> climate fan_mode
  fan.verticalDirection  enum RW 上下风向(7档)       -> vertical_direction
  fan.horizontalDirection enum RW 水平风向(7档)      -> horizontal_direction
  fan.direction          enum RW AI舒适风(5档)       -> ai_comfort_wind

  airConditioner.on      bool RW 空调开关             -> ac_switch
  airClean.on            bool RW 空气净化             -> air_clean
  airCleangear.gear      enum RW 净化档位 1~4         -> air_clean_gear
  aiFreshair.on          bool RW AI新风托管           -> ai_fresh_air
  freshAirSwitch.on      bool RW 新风开关             -> fresh_air
  freshAirSpeed.gear     enum RW 新风档位 0=自动 1~4  -> fresh_air_speed

  co2Switch.on           bool RW CO2 监测开关         -> co2_switch
  co2.current            int  R 0~10000 ppm CO2 浓度   -> co2
  co2.level              enum R 1=正常 2=超标 3=严重   -> co2_level

  humidity.current       int  R 0~100 % 室内湿度       -> humidity
  humidity.target        int  RW 30~90 % 目标湿度      -> humidity_target
  humidity.levelTarget   enum RW 1=干燥 2=清爽 3=平衡 4=湿润 -> humidity_level
  keepHumidity.on        bool RW 保湿控制             -> keep_humidity

  filterElement.leftPer  int  R 0~100 % 滤芯余量       -> filter_left_percent
  filterElement.leftTime int  R 0~600 h 滤芯余时       -> filter_left_time
  filterElement.alarm    bool R 1=有告警               -> filter_alarm
  filterElement.reset    enum RW 1=耗材复位            -> button 滤芯复位
  filterElement.filterType/name  R/RW 滤芯类型/名称    不映射（静态元数据）

  sterilization.on       bool RW 除菌                 -> sterilization
  mildewProofswitch.on   bool RW 干燥防霉             -> mildew_proof
  sleepCurveSwitch.on    bool RW 睡眠曲线开关          -> sleep_curve
  switchScreen.on        bool RW 屏显                 -> screen
  keyToneSwitch.on       bool RW 提示音               -> key_tone
  ECOswitch.on           bool RW AI节能               -> eco
  favoriteModeSwitch.on  bool RW 常用模式开关          -> favorite_mode_switch
  favoriteMode.trigger   enum RW 0=保存 1=删除         -> favorite_mode (select)

  intelligentClean.mode  enum RW 智清洁(4档)           -> intelligent_clean
  modePTC.mode           enum RW 电辅热(3档)           -> ptc_mode
  status.mode            enum R  0=默认 1=化霜中       -> hvac_action
  commonFaultDetection.{code,status,message} R        -> problem + 描述属性

  netInfo.*              网络                        -> 诊断传感器
  update.version         string R 固件版本             -> firmware_version

  sleepCurve.config/temperatureArray  睡眠曲线数据     不映射，见下方说明
  delay.*（倒计时）        array[object]               不映射（同其它机型理由）
  checkSum.checkSum      string R 固件校验值           不映射（内部校验值）
  update.progress/bootTime/introduction/action         不映射（OTA 流程）

=====================================================================
⚠️ 本机没有"自动"模式（与其它四台美的/美邦机型的关键差异）
=====================================================================
mode.mode 的枚举**不含 enumVal=1（自动）**：

    2=制冷  3=除湿  4=制热  5=送风  8=舒适除湿  9=个性除湿

对比我此前适配的机型：
    2Q2T/2NJN/2NTI: 1=自动 2=制冷 3=制热 4=送风 5=除湿
    2RK1 (美的柜机): 1=自动 2=制冷 3=除湿 4=制热 5=送风 7=衡温除湿
    2REC (本机)    :              2=制冷 3=除湿 4=制热 5=送风 8=舒适除湿 9=个性除湿

因此本适配器的 climate **不声明 "auto"**（否则用户会选到一个设备
不支持的档位，下发后被云端拒绝）。hvac_modes 为：
    off / cool / heat / dry / fan_only

另外 enumVal=8（舒适除湿）、9（个性除湿）都是除湿的变体，一并映射为
HA 的 ``dry``；回读时 3/8/9 都会显示为"除湿"。这是 HA climate 模型
粒度所限（无法表达三种除湿子模式）；如需区分，可用本机同时暴露的
favoriteMode 或直接在 App 内切换。

=====================================================================
为什么不映射 sleepCurve（睡眠曲线）
=====================================================================
sleepCurve 由两个字段组成：
  * config            —— string（1024 字符），无任何格式说明；
  * temperatureArray  —— ``array[object]``，但 **arrayObjs 是空数组**，
                        即 Profile 完全没有给出数组元素的字段定义。
缺少字段定义的数组无法安全构造；config 的编码格式也没有文档。
二者都属于"睡眠曲线的整体配置"，必须整体读写且格式未知，
按失败关闭原则**不映射**。

注意：**睡眠曲线的"开关"（sleepCurveSwitch.on）是可用的**，本适配器
已暴露为 switch；只是曲线内容本身需要在华为智慧生活 App 里编辑。

=====================================================================
关于两套"新风/净化/湿度"的能力划分
=====================================================================
本机把空气能力拆成多条独立服务，我按其语义分别暴露，不做合并：
  * 新风：freshAirSwitch（开关）+ freshAirSpeed（档位）
  * AI新风托管：aiFreshair（让设备自行管理新风，与手动新风开关是
    两种策略，故独立成一个 switch）
  * 净化：airClean（开关）+ airCleangear（1~4 档）
  * 保湿：keepHumidity（开关）+ humidity.target（目标湿度）
    + humidity.levelTarget（档位预设，与 target 是两条并行通道）
  * CO2：co2Switch（监测开关）+ co2.current / co2.level（读数）

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"2"``），
但 characteristicType 是 bool/enum/int/float，真机只接受**数值**。
直接把枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化。

``_enum_value()`` **只按 enumVal 精确匹配，不做 descCh/descEn
文本回退**——本机 mode 枚举里 enumVal=3 与 enumVal=5 的 descEn
**都是 "Dehumidification"**（Profile 笔误），文本匹配必然出错。
这是 2QWL 适配中踩过的同类 bug，此处已从设计上规避。

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
[ ] 控制命令：climate 的开关/模式/温度/风速，以及 11 个 switch、
    6 个 select、3 个 number、1 个 button，均未实测。
[ ] **模式枚举**：本机无"自动"档，且 8/9 两个除湿变体一并映射为 dry。
    请真机确认 制冷/制热/送风/除湿 四个基本档位动作正确。
[ ] **两套电源开关**：``switch.on``（总开关）与 ``airConditioner.on``
    （空调开关）的关系未验证——是主从（总开关控制全部）还是并列？
    本适配器把 climate 绑在 ``switch.on`` 上，``airConditioner.on``
    单独做成 switch。若真机实测二者必须同开同关，需要调整。
[ ] humidity.target（30~90%）与 humidity.levelTarget（4 档预设）
    是否互相覆盖未验证；当前作为两条独立通道分别下发。
[ ] 滤芯余量/余时/告警的实际上报频率未验证；
    filterElement.reset（耗材复位）写入后是否立即清零未验证。
[ ] co2.current 是否持续上报未验证（部分机型仅在 co2Switch=1 时上报）。
[ ] sleepCurveSwitch 打开后，若设备侧没有已保存的曲线，行为未知。
[ ] favoriteMode.trigger 只有 保存/删除，无回读字段，
    current_option 可能长期为 unknown（与 2RK1 同类问题）。
[ ] status.mode=1（化霜）映射为 hvac_action="defrosting"，
    HA 的 HVACAction 是否接受该值需实机确认。
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


# --- 温度范围：取自本机 Profile（float，步进 0.5） -------------------
_TEMP_MIN = 16.0
_TEMP_MAX = 30.0

# --- 模式映射（本机无 auto） -----------------------------------------
# HA hvac_mode -> 设备 enumVal。8/9 是除湿变体，无对应 HA 概念，
# 仅用于回读，不参与写入（写入 dry 用标准的 3）。
_HVAC_TO_DEV = {
    "cool": 2,       # 制冷
    "dry": 3,        # 除湿
    "heat": 4,       # 制热
    "fan_only": 5,   # 送风
}
_DEV_TO_HVAC = {
    2: "cool",
    3: "dry",
    4: "heat",
    5: "fan_only",
    8: "dry",        # 舒适除湿 -> dry
    9: "dry",        # 个性除湿 -> dry
}
# climate 声明的档位（不含 auto —— 本机 Profile 没有该档）
_HVAC_MODES = ["off", "cool", "heat", "dry", "fan_only"]

# --- 风速（fan.gear） ------------------------------------------------
_DEV_TO_FAN = {0: "自动", 1: "静音", 2: "低档", 3: "中档", 4: "高档", 5: "超强"}
_FAN_TO_DEV = {value: key for key, value in _DEV_TO_FAN.items()}

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# 简单布尔开关（sid, 字段名, key, 名称）
_SWITCH_SPECS = (
    ("airConditioner", "on", "ac_switch", "空调开关"),
    ("airClean", "on", "air_clean", "空气净化"),
    ("aiFreshair", "on", "ai_fresh_air", "AI新风托管"),
    ("freshAirSwitch", "on", "fresh_air", "新风"),
    ("co2Switch", "on", "co2_switch", "CO2 监测"),
    ("keepHumidity", "on", "keep_humidity", "保湿控制"),
    ("sterilization", "on", "sterilization", "除菌"),
    ("mildewProofswitch", "on", "mildew_proof", "干燥防霉"),
    ("sleepCurveSwitch", "on", "sleep_curve", "睡眠曲线"),
    ("switchScreen", "on", "screen", "屏显"),
    ("keyToneSwitch", "on", "key_tone", "提示音"),
    ("ECOswitch", "on", "eco", "AI节能"),
    ("favoriteModeSwitch", "on", "favorite_mode_switch", "常用模式开关"),
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

    只按 enumVal 精确匹配。**绝不按 descCh/descEn 文本回退**：
    本机 mode 枚举里 enumVal=3 与 enumVal=5 的 descEn 都是
    "Dehumidification"（Profile 笔误），文本匹配必然命中错误档位。
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


def _enum_options(
    field: Mapping[str, Any] | None,
    *,
    order: tuple[Any, ...] | None = None,
) -> tuple[tuple[Any, str], ...]:
    """Return ``(raw_value, label)`` pairs from a Profile enum list."""

    options: list[tuple[Any, str]] = []
    if not isinstance(field, Mapping):
        return ()
    for option in field.get("enumList", ()):
        if not isinstance(option, Mapping):
            continue
        raw = option.get("enumVal")
        if raw is None:
            continue
        label = option.get("descCh") or option.get("descEn") or str(raw)
        options.append((raw, str(label)))
    if order is not None:
        rank = {str(value): index for index, value in enumerate(order)}
        options.sort(key=lambda item: rank.get(str(item[0]), len(rank)))
    return tuple(options)


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
# climate 动作
# ---------------------------------------------------------------------
def _power_field(context: DeviceContext) -> Mapping[str, Any] | None:
    return _field(context.profile, "switch", "on")


async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service(
        "switch", {"on": _enum_value(_power_field(context), 1, 1)}
    )


async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service(
        "switch", {"on": _enum_value(_power_field(context), 0, 0)}
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
        "switch", {"on": _enum_value(_power_field(context), 1, 1)}
    )


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
    field = _field(context.profile, "fan", "gear")
    await context.async_send_service(
        "fan", {"gear": _enum_value(field, device_value, device_value)}
    )


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


def _make_enum_select(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
    *,
    order: tuple[Any, ...] | None = None,
) -> EntitySpec | None:
    field = _field(context.profile, sid, field_name)
    if field is None or not _is_writable(field):
        return None
    options = _enum_options(field, order=order)
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


def _make_number(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
    unit: str | None,
) -> EntitySpec | None:
    field = _field(context.profile, sid, field_name)
    if field is None or not _is_writable(field):
        return None
    minimum = _number(field.get("min"))
    maximum = _number(field.get("max"))
    step = _number(field.get("step"))

    async def set_value(device: DeviceContext, data: Mapping[str, Any]) -> None:
        value = _clamp(data.get("value"), field)
        if value is None:
            return
        await device.async_send_service(sid, {field_name: value})

    def state(device: DeviceContext) -> Mapping[str, Any]:
        return {"native_value": _number(device.value(sid, field_name))}

    metadata: dict[str, Any] = {
        "min": minimum if minimum is not None else 0,
        "max": maximum if maximum is not None else 100,
        "step": step if step and step > 0 else 1,
    }
    if unit is not None:
        metadata["unit"] = unit

    return EntitySpec(
        platform="number",
        key=key,
        name=name,
        state=state,
        metadata=metadata,
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


class Product2RECAdapter:
    """Keep all 2REC entity and command choices in this file."""

    prod_id = "2REC"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        # --- climate：模式 / 温度 / 风速 -------------------------------
        if context.has_service("mode") and context.has_service("temperature"):
            gear_field = _field(profile, "fan", "gear")
            fan_labels = tuple(
                _DEV_TO_FAN[value]
                for value in sorted(_DEV_TO_FAN)
                if _enum_label(gear_field, value) is not None
            ) or tuple(_DEV_TO_FAN.values())
            # 只声明设备 Profile 里真实存在的档位（本机无 auto，故
            # 不能用固定的 _HVAC_MODES；也不可再额外前置 "off"，
            # 因为 _HVAC_MODES 已含 "off"，会重复）。
            mode_field = _field(profile, "mode", "mode")
            declared = {
                str(option.get("enumVal"))
                for option in (mode_field or {}).get("enumList", ())
                if isinstance(option, Mapping)
            }
            hvac_modes = [
                value
                for value in _HVAC_MODES
                if value == "off" or str(_HVAC_TO_DEV[value]) in declared
            ]
            if not hvac_modes:
                hvac_modes = ["off"]

            def climate_state(device: DeviceContext) -> Mapping[str, Any]:
                power = _bool(device.value("switch", "on"))
                mode = _int(device.value("mode", "mode"))
                if power is False:
                    hvac_mode = "off"
                elif power is None and mode is None:
                    hvac_mode = None
                else:
                    hvac_mode = _DEV_TO_HVAC.get(mode)
                status = _int(device.value("status", "mode"))
                if power is False or hvac_mode == "off":
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
                else:
                    action = None
                gear = _int(device.value("fan", "gear"))
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
                }

            entities.append(
                EntitySpec(
                    platform="climate",
                    key="air_conditioner",
                    name=None,
                    state=climate_state,
                    metadata={
                        "hvac_modes": hvac_modes,
                        "fan_modes": list(fan_labels),
                        "min_temp": _TEMP_MIN,
                        "max_temp": _TEMP_MAX,
                    },
                    actions={
                        "turn_on": _turn_on,
                        "turn_off": _turn_off,
                        "set_hvac_mode": _set_hvac_mode,
                        "set_temperature": _set_temperature,
                        "set_fan_mode": _set_fan_mode,
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
        select_specs = (
            ("fan", "verticalDirection", "vertical_direction", "上下风向",
             ("0", "1", "2", "3", "4", "5", "6")),
            ("fan", "horizontalDirection", "horizontal_direction", "水平风向",
             ("0", "1", "2", "3", "4", "5", "6")),
            ("fan", "direction", "ai_comfort_wind", "AI舒适风",
             ("1", "2", "3", "4", "100")),
            ("airCleangear", "gear", "air_clean_gear", "净化档位",
             ("1", "2", "3", "4")),
            ("freshAirSpeed", "gear", "fresh_air_speed", "新风档位",
             ("0", "1", "2", "3", "4")),
            ("humidity", "levelTarget", "humidity_level", "保湿档位",
             ("1", "2", "3", "4")),
            ("intelligentClean", "mode", "intelligent_clean", "智清洁",
             ("0", "1", "2", "100")),
            ("modePTC", "mode", "ptc_mode", "电辅热",
             ("0", "1", "100")),
            ("favoriteMode", "trigger", "favorite_mode", "常用模式",
             ("0", "1")),
        )
        for sid, field_name, key, name, order in select_specs:
            if not context.has_service(sid):
                continue
            spec = _make_enum_select(
                context, sid, field_name, key, name, order=order
            )
            if spec is not None:
                entities.append(spec)

        # --- number ---------------------------------------------------
        for sid, field_name, key, name, unit in (
            ("humidity", "target", "humidity_target", "目标湿度", "%"),
        ):
            if not context.has_service(sid):
                continue
            spec = _make_number(context, sid, field_name, key, name, unit)
            if spec is not None:
                entities.append(spec)

        # --- 传感器 ---------------------------------------------------
        if context.has_service("temperature"):
            entities.append(
                _make_sensor(
                    "temperature", "current", "current_temperature",
                    "室内温度", unit="°C", device_class="temperature",
                    state_class="measurement", decode=_number,
                )
            )
        if context.has_service("humidity"):
            entities.append(
                _make_sensor(
                    "humidity", "current", "humidity", "室内湿度",
                    unit="%", device_class="humidity",
                    state_class="measurement", decode=_int,
                )
            )
        if context.has_service("co2"):
            entities.append(
                _make_sensor(
                    "co2", "current", "co2", "CO2 浓度",
                    unit="ppm", device_class="carbon_dioxide",
                    state_class="measurement", decode=_int,
                )
            )
            level_field = _field(profile, "co2", "level")

            def co2_level_state(device: DeviceContext) -> Mapping[str, Any]:
                raw = _int(device.value("co2", "level"))
                if raw is None:
                    return {"native_value": None}
                label = _enum_label(level_field, raw)
                return {
                    "native_value": label if label is not None else raw,
                    "extra_state_attributes": {"raw_level": raw},
                }

            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="co2_level",
                    name="CO2 等级",
                    state=co2_level_state,
                    metadata={"entity_category": "diagnostic"},
                )
            )

        # --- 滤芯耗材 -------------------------------------------------
        if context.has_service("filterElement"):
            if _field(profile, "filterElement", "leftPer") is not None:
                entities.append(
                    _make_sensor(
                        "filterElement", "leftPer", "filter_left_percent",
                        "滤芯余量", unit="%", state_class="measurement",
                        decode=_int,
                    )
                )
            if _field(profile, "filterElement", "leftTime") is not None:
                entities.append(
                    _make_sensor(
                        "filterElement", "leftTime", "filter_left_time",
                        "滤芯余时", unit="h", state_class="measurement",
                        entity_category="diagnostic", decode=_int,
                    )
                )
            if _field(profile, "filterElement", "alarm") is not None:
                entities.append(
                    EntitySpec(
                        platform="binary_sensor",
                        key="filter_alarm",
                        name="滤芯告警",
                        state=lambda device: {
                            "is_on": _bool(
                                device.value("filterElement", "alarm")
                            )
                        },
                        metadata={"device_class": "problem"},
                    )
                )
            reset_field = _field(profile, "filterElement", "reset")
            if _is_writable(reset_field):
                reset_value = _enum_value(reset_field, 1, 1)

                async def reset_filter(
                    device: DeviceContext, _data: Mapping[str, Any]
                ) -> None:
                    await device.async_send_service(
                        "filterElement", {"reset": reset_value}
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
        if context.has_service("commonFaultDetection"):
            code_field = _field(profile, "commonFaultDetection", "code")

            def problem_state(device: DeviceContext) -> Mapping[str, Any]:
                status = _bool(
                    device.value("commonFaultDetection", "status")
                )
                code = _int(device.value("commonFaultDetection", "code"))
                # status 是权威的"是否有故障"标志；code 仅作描述。
                is_on = status if status is not None else (
                    None if code is None else code != 0
                )
                attributes: dict[str, Any] = {}
                if code is not None:
                    attributes["fault_code"] = code
                label = _enum_label(code_field, code)
                if label is not None and code != 0:
                    attributes["fault_description"] = label
                message = _text(
                    device.value("commonFaultDetection", "message")
                )
                if message is not None:
                    attributes["fault_message"] = message
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

ADAPTER = Product2RECAdapter()
