"""User-contributed protocol for Huawei product 2RK1 (美的智能空调 鸿蒙全面风Pro).

产品: 美的智能空调 鸿蒙全面风 Pro（柜机）
厂商: 美的 (midea)
型号: KFR-72L/HWR3 (deviceTypeId 2F9, 柜机空调, WiFi, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
**不跨产品复用**。2RK1 与 2Q2T / 2NJN 虽同为挂/柜机空调，但模式枚举
不同（见下方"模式枚举"一节），且 2RK1 有独立的风向枚举与智清洁/
除菌/干燥防霉等服务，故各自独立实现。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  switch.on                  bool RW 总开关            -> climate on/off
                                ★ 单独写不生效，开机需先发 mode（见"真机实测记录"）
  mode.mode                  enum RW 运行模式           -> climate hvac_mode
  temperature.target         float RW 16.0~30.0 ℃ 步进0.5 -> climate target
  temperature.current        float R  室内温度          -> climate current
  fan.gear                   enum RW 0=自动 1=静音 2=低 3=中 4=高 5=超强
                                                      -> climate fan_mode

  fan.verticalDirection      enum RW 上下风向(7档)      -> vertical_direction (select)
  fan.horizontalDirection    enum RW 水平风向(7档)      -> horizontal_direction (select)
  fan.direction              enum RW AI舒适风(5档)      -> ai_comfort_wind (select)

  ECOswitch.on               bool RW AI节能(酷省电)      -> eco
  sterilization.on           bool RW 除菌               -> sterilization
  mildewProofswitch.on       bool RW 干燥防霉            -> mildew_proof
  switchScreen.on            bool RW 屏显               -> screen
  keyToneSwitch.on           bool RW 提示音              -> key_tone
  favoriteModeSwitch.on      bool RW 常用模式开关         -> favorite_mode_switch
  favoriteMode.trigger       enum RW 0=保存 1=删除       -> favorite_mode (select)

  intelligentClean.mode      enum RW 智清洁模式(4档)      -> intelligent_clean (select)
  modePTC.mode               enum RW 电辅热模式(3档)      -> ptc_mode (select)
  status.mode                enum R  0=默认 1=化霜中      -> hvac_action (defrosting)
  commonFaultDetection.{code,status,message}  R          -> problem + 描述属性

  netInfo.*                  网络                       -> 诊断传感器
  update.version             string R 固件版本            -> firmware_version

  delay.*（倒计时）           array[object]              不映射，见下方说明
  checkSum.checkSum          string R 固件校验值          不映射（内部校验值）
  update.progress/bootTime/introduction/action           不映射（OTA 流程）

=====================================================================
⚠️ 模式枚举：Profile 的 descCh 与 descEn 互相矛盾（务必真机确认）
=====================================================================
mode.mode 的原始枚举只带 descCh/descEn 两列（**没有可靠的单列可同时
对齐两侧**），而这两列在 enumVal>=3 处发生错位：

    enumVal  descCh      descEn
    -------  ----------  -------------------
      1      自动         Auto
      2      制冷         Cooling
      3      除湿         Heating          ← 冲突
      4      制热         Ventilation      ← 冲突
      5      送风         Dehumidification ← 冲突
      7      衡温除湿      Sleep            ← 冲突

两种解读：
  A) 信 descCh（本文件采用）：3=除湿 4=制热 5=送风 7=衡温除湿
  B) 信 descEn：3=制热 4=送风 5=除湿 7=睡眠

旁证：同厂商/同协议的另两台机器（2Q2T、2NJN）都是
  1=自动 2=制冷 3=制热 4=送风 5=除湿
其 descEn 列与 2RK1 的 descEn 列**逐字相同**，说明 descEn 是华为的
通用模板列（按 1~5 顺序套用），**并不反映本机的真实语义**；本机真实
差异（多了 7=衡温除湿、且 3/4 互换）体现在 descCh 里。

因此本文件**采用 descCh**，与我在 2QWL（浴霸）中处理同类冲突的做法
一致。写入时按 enumVal 数字下发，读取时按 descCh 显示。

**但这一条有实质风险**：如果真机实际是解读 B，则"制热"会写成除湿、
"送风"会写成除湿。装机后请务必做一次验证：
    在 HA 里点"制热"，看设备是否真的出热风。
若相反，只需修改本文件 _DEV_TO_HVAC 里 3/4/5 三个数字即可。

=====================================================================
关于 fan.direction（AI舒适风）
=====================================================================
该字段 attrName="AI舒适风"，枚举 1=风避人吹 2=风随人动 3=人近风柔
5=全面风 100=关闭。它**不是**普通的上下/左右扫风（那由
verticalDirection / horizontalDirection 表达），而是"全面风 Pro"
机型的**感知类送风模式**，因此单独做成 select，不与 climate 的
swing_mode 混用，避免把两套语义压进一个字段。

=====================================================================
为什么不映射 delay（倒计时）
=====================================================================
delay.delay 是 ``array[object]``，元素含
enable/para/start/end/sid/paraValue/id 共 7 个字段，通过 action 的
update/create/delete 驱动。正确写入必须先读取设备当前倒计时列表、
按 id 增删改、再整体回写。本集成没有该"读-改-写"事务能力，且写错会
覆盖用户已配置的倒计时，风险高于收益，故不映射。用户仍可在华为
智慧生活 App 中配置。

=====================================================================
真机实测记录
=====================================================================
[已实测] 读取：**完全正确**。在智慧生活 App 里控制空调后，HA 显示全部一致。
[已实测] 关机：**生效**（从模式下拉选「关」，空调停机）。
[已实测·已修复] **开机/选模式不生效**（用户报告，2026-10）。

现象：
  * 在 HA 里通过**模式下拉菜单**选「制冷/制热」→ 空调没反应；
  * 但同样路径选「关」→ 能正常停机；
  * HA 侧不报错，且在 App 里控制后 HA 状态显示正确。

★ 根因（不是开关字段的问题，也不是 payload 类型问题）：

  旧版 ``_set_hvac_mode`` 在选非 off 模式时**只发 mode，从不置电源位**：

      if wanted == "off":
          await _turn_off(...)          # 发 switch.on = 0  -> 能停机
      else:
          await send("mode", {...})     # 只发 mode，电源位保持 0
          # （从未发送 switch.on = 1）

  本机的 Profile 里 **没有独立的"开机"服务**，电源就是 ``switch.on``。
  于是空调处于关机态时，用户选「制冷」只让设备收到 mode=2，
  电源位仍是 0 —— 空调当然不启动。

  而"关机生效"恰好说明 ``switch.on`` **是可写的**（写 0 有用），
  进一步反证问题不在字段权限、也不在取值编码
  （已验证 on/off 两个取值都是 int，编码对称）。

关于 HA 界面形态（容易误判的地方）：
  本机 climate 只声明了 hvac_modes + 温度/风速，**没有独立电源按钮**，
  用户是从模式下拉菜单操作的。因此"开机"实际上走的是
  ``set_hvac_mode`` 而不是 ``turn_on`` —— 旧版只修 ``turn_on``
  是修不到这条路径的，必须让 set_hvac_mode 自己补开机位。

修复（见 _set_hvac_mode / _turn_on）：
  选任何非 off 模式时 = 先写 mode，**再补写 switch.on = 1**。
  两步各自等待云端 ACK（集成对每个 sid 单飞，且 mode/switch 是不同
  sid，不会互相阻塞）。

[已实测] 修复**有效**：从模式下拉选非 off 模式，空调正常启动；
    选「关」也能正常停机。两个方向均已确认。
[ ] 待确认：开机后模式是否与所选一致（若被改成制冷，需检查回退逻辑）。
[ ] 待确认：``switch.on=1`` 与 ``mode`` 连发两次命令时，若网络慢，
    两步之间可能有数百毫秒间隔；真机上是否会出现"模式已切、电源未置"
    的中间态（表现为短暂显示已开机但机身未启动）。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"3"``），
但 characteristicType 是 bool/enum/int/float，真机只接受**数值**。
直接把枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化，
取值本身从 Profile 的 enumList 读取，不硬编码。

另：``_enum_value()`` **只按 enumVal 精确匹配，不做 descCh/descEn
文本回退**。这是 2QWL 适配中踩过的真实 bug：本机 modePTC 的
descEn="Off"/"Auto" 与别的档位文本相似，一旦允许文本匹配就可能
命中错误档位（如 enumVal=100=关闭 与 1=自动辅热 的 descEn 冲突）。

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
[已实测] 状态读取：**正确**。在智慧生活 App 里控制空调后，HA 显示全部一致。
[已实测] 控制命令：**温度与模式下发生效**；**单独下发开关不生效**
    （见上方"真机实测记录"）。开关已改为"先 mode 再 switch.on"两步下发。
[ ] **关机是否生效（待确认）**：见上方真机实测记录末尾。这决定两步策略
    是否需要进一步调整。
[ ] 开机两步下发的**附加效果**：先发 mode 会顺带把空调切到该模式。
    若用户原本只想要"开机并保持原模式"，请确认 `_current_hvac()` 读到的
    上报模式确实等于用户预期（设备上报滞后时可能用到回退值 cool）。
[ ] **模式语义（最高优先级）**：见上方"模式枚举"一节。装好后请逐档
    验证 制热/送风/除湿 是否与实物一致。
[ ] 其余控制命令：climate 的风速，以及 5 个 switch、6 个 select，
    均未实测。
[ ] 温度步进：Profile 声明 step=0.5、范围 16.0~30.0。写温度时按 0.5
    对齐并夹取到该范围。
[ ] 智清洁模式（快速/高温/全面/关闭）与电辅热模式（持续/自动/关闭）
    的实际生效时长与前置条件（如是否需先开机）未验证。
[ ] favoriteMode.trigger 只有 保存/删除 两个动作，但**没有任何字段
    能回读"当前保存了什么"**，因此该 select 无法反映真实状态；
    本适配器把它做成 select，选中即下发，但 current_option 会立即
    回落为上报值（可能始终是 unknown）。真机确认后若确实无回读，
    建议改为两个 button（保存常用模式 / 删除常用模式）。
[ ] status.mode=1（化霜）映射为 hvac_action="defrosting"，
    HA 的 HVACAction 是否接受该值需实机确认。
[ ] 故障码 code 与 status 的一致性未验证：当前以 status 为主、
    code 作描述；message 字段作为补充文本一并输出。
[ ] netInfo 各字段设备是否实际上报未验证；若不上报将长期为 unknown
    （诊断类，不影响主功能）。
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
_TEMP_STEP = 0.5

# --- 模式映射 --------------------------------------------------------
# ⚠️ 采用 descCh（见文件头"模式枚举"）。enumVal=7 是"衡温除湿"，
#    归入 HA 的 dry（除湿）；enumVal=5 是"送风" -> fan_only。
#    若真机验证与 descEn 一致，交换 3/4/5 的下标即可。
_DEV_TO_HVAC = {
    1: "auto",       # 自动
    2: "cool",       # 制冷
    3: "dry",        # 除湿   ← 争议项
    4: "heat",       # 制热   ← 争议项
    5: "fan_only",   # 送风   ← 争议项
    7: "dry",        # 衡温除湿
}
_HVAC_TO_DEV = {
    "auto": 1,
    "cool": 2,
    "dry": 3,
    "heat": 4,
    "fan_only": 5,
}

# --- 风速（fan.gear） ------------------------------------------------
_DEV_TO_FAN = {0: "自动", 1: "静音", 2: "低档", 3: "中档", 4: "高档", 5: "超强"}

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# 简单布尔开关（sid, key, 名称）
_SWITCH_SPECS = (
    ("ECOswitch", "eco", "AI节能"),
    ("sterilization", "sterilization", "除菌"),
    ("mildewProofswitch", "mildew_proof", "干燥防霉"),
    ("switchScreen", "screen", "屏显"),
    ("keyToneSwitch", "key_tone", "提示音"),
    ("favoriteModeSwitch", "favorite_mode_switch", "常用模式开关"),
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

    只按 ``enumVal`` 精确匹配，**不做 descCh/descEn 文本回退**：
    本机多个服务的 descEn 文本互相冲突（如 modePTC 的 'Off'/'Auto'），
    文本匹配会命中错误档位（2QWL 适配中踩过的真实 bug）。
    需要按标签查找的调用方请自行维护 label 映射。
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
    """Return ``(raw_value, label)`` pairs from a Profile enum list.

    label 取 descCh（中文，与 App 显示一致）。``order`` 给定时按该顺序
    排列（用于把功能的自然顺序强加给 Profile 的乱序枚举）。
    """

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
def _switch_on_value(context: DeviceContext) -> Any:
    return _enum_value(_field(context.profile, "switch", "on"), 1, 1)


def _switch_off_value(context: DeviceContext) -> Any:
    return _enum_value(_field(context.profile, "switch", "on"), 0, 0)


def _mode_payload(context: DeviceContext, hvac: str) -> dict[str, Any]:
    """Build the ``mode`` service payload for one HA hvac mode."""

    device_value = _HVAC_TO_DEV.get(hvac)
    if device_value is None:
        raise ValueError(f"unsupported hvac_mode: {hvac}")
    field = _field(context.profile, "mode", "mode")
    return {"mode": _enum_value(field, device_value, device_value)}


def _current_hvac(context: DeviceContext) -> str | None:
    """Return the hvac mode the device currently reports, if recognised."""

    raw = _number(context.value("mode", "mode"))
    if raw is None:
        return None
    return _DEV_TO_HVAC.get(int(raw))


async def _turn_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    """Power the AC on, keeping the mode the device currently reports.

    ★ 真机实测（用户报告）：在 HA 里"打开空调"不生效。

    根因**不在开关字段本身**，而在旧版 ``_set_hvac_mode`` 的逻辑缺口：

        HA 的 climate 界面（本机只声明 hvac_modes + 温度/风速）里，
        用户是通过**模式下拉菜单**操作的，没有独立电源按钮。
        而旧版代码在选非 off 模式时**只发 mode，从不置电源位**：

            if wanted == "off": await _turn_off(...)   # 发 switch.on=0
            else:               await send("mode", ...) # 只有 mode！

        于是当空调处于关机态、用户从下拉选「制冷」时，
        设备收到 mode=2 但电源位仍是 0 -> **空调不开机**。
        而选「关」时确实发了 switch.on=0，所以"关机生效"。

    这解释了为什么现象是"读正常、关正常、开机不生效"——
    不是写入通道问题，也不是 payload 类型问题
    （on/off 两个取值都是 int，编码对称，已验证）。

    修复：选任何非 off 模式时，**先把模式写下去，再补一个开机位**。
    这样"选模式"既能切模式、也能把关机状态的空调开起来，
    与用户在智慧生活 App 里的操作预期一致。

    为什么用"当前上报的模式"而不是硬编码：
      * 保持用户的选择，不擅自把空调切到制冷；
      * 仅在设备没上报过模式、或上报值不在映射表内时回退到 cool。

    注：本机 Profile 里 ``switch.on`` 声明为 ``method=RW``、``perm=GPR``，
    是货真价实的可写电源位——旧版只是**没有去写它**。
    """

    mode = _current_hvac(context) or "cool"
    await context.async_send_service("mode", _mode_payload(context, mode))
    await context.async_send_service("switch", {"on": _switch_on_value(context)})


async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    """Power the AC off by clearing the switch bit.

    该路径已由用户真机确认**生效**（"关机是生效的"）。
    """

    await context.async_send_service("switch", {"on": _switch_off_value(context)})


async def _set_hvac_mode(context: DeviceContext, data: Mapping[str, Any]) -> None:
    """Set the device mode.

    这是 HA climate 界面上用户最常走的路径（模式下拉菜单）。
    非 off 模式必须**同时把空调开起来**，否则在关机态下选模式不会有效果
    （见 ``_turn_on`` 的说明）。
    """

    wanted = str(data.get("hvac_mode"))
    if wanted == "off":
        await _turn_off(context, data)
        return
    if wanted not in _HVAC_TO_DEV:
        raise ValueError(f"unsupported hvac_mode: {wanted}")
    await context.async_send_service("mode", _mode_payload(context, wanted))
    # 关键：补开机位。缺了这一步，关机态下选模式不会启动空调。
    await context.async_send_service("switch", {"on": _switch_on_value(context)})


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
    device_value = next(
        (raw for raw, label in _DEV_TO_FAN.items() if label == wanted),
        None,
    )
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
    key: str,
    name: str,
) -> EntitySpec:
    field = _field(context.profile, sid, "on")
    on_value = _enum_value(field, 1, 1)
    off_value = _enum_value(field, 0, 0)

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
    *,
    order: tuple[Any, ...] | None = None,
) -> EntitySpec | None:
    """One ``select`` backed by a Profile enum characteristic."""

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
        await device.async_send_service(
            sid, {field_name: _coerce(raw, field)}
        )

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


class Product2RK1Adapter:
    """Keep all 2RK1 entity and command choices in this file."""

    prod_id = "2RK1"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        # --- climate --------------------------------------------------
        if context.has_service("mode") and context.has_service("temperature"):
            gear_field = _field(profile, "fan", "gear")
            fan_labels = tuple(
                _DEV_TO_FAN[value]
                for value in sorted(_DEV_TO_FAN)
                if _enum_label(gear_field, value) is not None
            ) or tuple(_DEV_TO_FAN.values())

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
                elif hvac_mode == "auto":
                    action = "idle"
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
                        "hvac_modes": [
                            "off", "auto", "cool", "heat", "dry", "fan_only",
                        ],
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

        # --- 独立开关 -------------------------------------------------
        for sid, key, name in _SWITCH_SPECS:
            if context.has_service(sid) and _is_writable(
                _field(profile, sid, "on")
            ):
                entities.append(_make_switch(context, sid, key, name))

        # --- 风向 / AI舒适风 / 各模式（select） -----------------------
        select_specs = (
            # 风向：按功能自然顺序排列（停止 -> 扫风 -> 各固定位）
            ("fan", "verticalDirection", "vertical_direction", "上下风向",
             ("0", "1", "2", "3", "4", "5", "6")),
            ("fan", "horizontalDirection", "horizontal_direction", "水平风向",
             ("0", "1", "2", "3", "4", "5", "6")),
            # AI舒适风：关闭放最后
            ("fan", "direction", "ai_comfort_wind", "AI舒适风",
             ("1", "2", "3", "5", "100")),
            ("intelligentClean", "mode", "intelligent_clean", "智清洁模式",
             ("0", "1", "2", "100")),
            ("modePTC", "mode", "ptc_mode", "电辅热模式",
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

ADAPTER = Product2RK1Adapter()
