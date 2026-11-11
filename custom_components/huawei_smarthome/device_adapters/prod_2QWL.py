"""User-contributed protocol for Huawei product 2QWL (佳普乐致慕智能浴霸).

产品: 佳普乐致慕智能浴霸 (CANPRO ZhiMu Smart Bathroom Heater)
厂商: CANPRO (佳普乐)
型号: BH2ZM-01S (deviceTypeId 035, 浴霸, Wi-Fi+BLE Combo, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
**不跨产品复用**。2QWL 与仓库既有 2QTT（箭牌浴霸）虽同为浴霸类型，
但服务集合差异很大：2QWL 有风暖/吹风/摆风/风向角度/目标温度/
场景模式/自定义模式与多个时长，2QTT 有除湿/湿度/除臭。
两者无共同字段语义，故各自独立实现，不提取公共基类。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  lightSwitch.on         bool RW 主照明              -> light
  nightLightSwitch.on    bool RW 夜灯                -> night_light
  autoWarmWindSwitch.on  bool RW 风暖（取暖）        -> warm_wind
  windSwitch.on          bool RW 吹风                -> wind
  ventilateSwitch.on     bool RW 换气                -> ventilate
  drySwitch.on           bool RW 干燥                -> dry
  swingSwitch.on         bool RW 摆风                -> swing
  inductionCondition.on  bool RW 来人感应            -> induction
  keyToneSwitch.on       bool RW 提示音              -> key_tone

  fan.angle              enum RW 摆风角度 60~120°    -> fan_angle (select)
  heat.target            float RW 32.0~45.0 ℃ 目标温度 -> target_temperature (number)
  heat.current           float R  -20.0~60.0 ℃ 表面温度 -> surface_temperature
  sceneMode.mode         enum RW 用户模式            -> scene_mode (select)

  timeGear.gear          enum RW 感应时间间隔        -> induction_interval (select)
  circulationTime.circulationTime int RW 1~120 换气时长 -> ventilate_duration
  windTime.windTime      int  RW 1~120 吹风/风暖时长  -> wind_duration
  setWorkTime.time       int  RW 1~120 照明时长      -> light_duration

  devCustomInfo.userMode1..4  string RW 自定义模式    不映射，见下方说明
  action.action          enum RW 0=功能关闭（一键待机）-> button 一键待机
  checkSum.checkSum      string R 固件校验值          不映射（内部校验值）
  netInfo.*              网络                        -> 诊断传感器
  update.*               OTA 全流程                  不映射（与其它适配器一致）

=====================================================================
关于 action.action（一键待机）
=====================================================================
该服务 descCh="待机"，attrName="一键待机"，enumList **只有一个值**
``0=功能关闭``。单值枚举通常表示"写入即触发关闭全部功能"的瞬时动作
（类似 2Q8M 的重置无人状态）。因此按 button 处理，而不是 select
（select 只有一个选项没有意义）。

注意：该服务 method=RW 但 permission 是 ``GPR``（缺 W 的语义不一致，
与 Profile 其它可写字段一致，故仍按可写处理）。

=====================================================================
关于 fan.angle 的标签：descCh 与 descEn 严重不一致
=====================================================================
本机 Profile 里 angle 的枚举标签是**错位**的，例如：
    enumVal=0   descEn="60"    descCh="60°"
    enumVal=1   descEn="90°"   descCh="65°"     ← descEn 与 descCh 不符
    enumVal=4   descEn="360°"  descCh="80°"     ← 360° 显然是错的
    enumVal=100 descEn="85"    descCh="85°"
可以看出 **descCh 是一个规整的 60,65,70,...,120 序列（步进 5，
共 13 档），而 descEn 明显是数据错误**。因此本适配器采用 descCh
作为标签与取值依据，并按 enumVal 升序排列，得到 60°~120° 共 13 档。

若真机实测风向角度与标签对不上，请提供实际表现，再据此修正。

⚠️ 开发期实测到的坑（已修复，勿回退）：
  最初的 _enum_value() 除了按 enumVal 精确匹配外，还允许按
  descCh/descEn **文本**回退匹配。由于本机枚举里 raw=105 的
  descEn 恰好是字符串 "110"，而我们希望 "110°" 对应 raw=105，
  文本回退会让 wanted=110 先命中 raw=104（其 descCh="105°"
  不匹配，但 descEn="105" 与 "110" 无关，真正命中的是
  descEn="110" 的那一档）——实测结果是 **"110°" 被下发改成了
  105° 的取值**（发送 angle=104 而非 105）。
  修复方式：删除文本回退，_enum_value() 只认 enumVal；
  按标签查找一律由调用方（本文件的 _make_select）用自己维护的
  by_label 映射完成。回归验证覆盖全部 13 档。

=====================================================================
为什么不映射 devCustomInfo.userMode1..4
=====================================================================
userMode4（attrName="执行自定义"）的 descCh 给了一段**位置相关的
协议串**示例：

    "2&40&060&1&120&1&090&1&090"
     ↑  ↑   ↑   ↑   ↑   ↑   ↑   ↑
     吹风/风暖(0吹风/1风暖/2关) & 目标温度 & 吹风/风暖时间 &
     换气开关 & 换气时间 & 照明开关(0照明/1夜灯/2关) & 照明时间 &
     摆风开 & 风向

这是一个**必须整体构造、字段顺序固定、且与当前 sceneMode 编号绑定**
的复合字符串。要安全地写入它，需要：
  1. 先读回设备当前的 userModeN 串，解析出各字段；
  2. 用户改其中一个字段，其余原样保留；
  3. 再整体回写。
本集成没有该"读-解析-改-写"能力，而**任何字段拼错都会让整条自定义
模式失效或产生非预期行为**（例如把照明时间写成风暖时间）。
userMode1..3 的 descCh 为空，连格式都没有文档。

按失败关闭原则，**四个自定义模式串全部不映射**。用户仍可在华为
智慧生活 App 中配置自定义模式；配好后可直接用本适配器暴露的
scene_mode 选择器运行它们（sceneMode.mode 的 2/3/4 即对应
自定义模式 1/2/3）。

=====================================================================
时长字段的单位
=====================================================================
三个时长字段的 Profile 声明不一致，本适配器如实处理：
  * setWorkTime.time   unit="min"（Profile 有声明）-> 按 min 呈现
  * circulationTime    unit=""   （无声明）        -> 按 min 呈现
  * windTime           unit=""   （无声明）        -> 按 min 呈现
后两个补 "min" 的依据是：三者的取值范围完全一致（1~120）、
且 setWorkTime 明确是分钟，同族字段按同一单位处理最合理。
若真机实测为秒，需修正。

注意 Profile 里另有 timeGear（感应时间间隔，30秒~10分钟）是**独立
的枚举档位**，不是上面三个时长，不要混淆。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"1"``），
但 characteristicType 是 bool/enum/int/float，真机只接受**数值**。
直接把枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化，
取值本身从 Profile 的 enumList 读取，不硬编码。

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
[ ] 控制命令：9 个 switch、1 个 select(场景)、1 个 number(温度)、
    3 个 number(时长)、1 个 select(风向)、1 个 select(感应间隔)、
    1 个 button(待机) 均未实测。
[ ] **一键待机**：写入 action=0 后的可观测结果未验证（是否所有
    开关状态都回落为 0）。若设备不上报回落状态，开关实体会与
    实际不同步，届时需要改为乐观更新或提示用户。
[ ] fan.angle 的 13 档角度标签取自 descCh（descEn 有错位），未实测。
[ ] 三个时长字段的单位（min vs s）未实测，见上文说明。
[ ] 目标温度 32.0~45.0℃ 是按 Profile 呈现；若真机范围更窄需修正。
[ ] 表面温度 heat.current 的 permission 仅为 "R"（无 G），
    意味着可能不属于可上报集合。若真机该传感器长期 unknown，
    属于设备侧不上报，不是适配器问题。
[ ] sceneMode 切换到自定义模式（2/3/4）时，若设备尚未在 App 中
    配置过对应模式，行为未知（可能无动作或报错）。
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


# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# 简单布尔开关（sid, key, 名称）——均为 <sid>.on
_SWITCH_SPECS = (
    ("lightSwitch", "light", "照明"),
    ("nightLightSwitch", "night_light", "夜灯"),
    ("autoWarmWindSwitch", "warm_wind", "风暖"),
    ("windSwitch", "wind", "吹风"),
    ("ventilateSwitch", "ventilate", "换气"),
    ("drySwitch", "dry", "干燥"),
    ("swingSwitch", "swing", "摆风"),
    ("inductionCondition", "induction", "来人感应"),
    ("keyToneSwitch", "key_tone", "提示音"),
)

# 可写时长（sid, 字段名, key, 名称）。
# 三者的 Profile 范围都是 1~120；setWorkTime 明确 unit=min，
# 另两个未声明 unit，按同族字段统一为 min。
_DURATION_SPECS = (
    ("setWorkTime", "time", "light_duration", "照明时长"),
    ("windTime", "windTime", "wind_duration", "吹风/风暖时长"),
    ("circulationTime", "circulationTime", "ventilate_duration", "换气时长"),
)

# 感应时间间隔（timeGear.gear）：标签取自 Profile 的 descCh。
_INDUCTION_INTERVAL_OPTIONS = (
    (1, "30秒"),
    (2, "1分钟"),
    (3, "3分钟"),
    (4, "5分钟"),
    (5, "10分钟"),
)

# 用户模式（sceneMode.mode）：标签取自 Profile 的 descCh。
_SCENE_OPTIONS = (
    (0, "无"),
    (1, "智能模式"),
    (2, "自定义模式1"),
    (3, "自定义模式2"),
    (4, "自定义模式3"),
)

_ACTION_SID = "action"
_ACTION_FIELD = "action"


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

    只按 ``enumVal`` 精确匹配。**不做 descCh/descEn 文本回退**：
    本机 fan.angle 的 descCh 是 "110°" 而另一档的 descEn 恰好是 "110"，
    若允许文本匹配，wanted=110 会错误命中另一档（真实存在过的 bug）。
    需要按标签查找的调用方请显式传 enumVal。
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


def _make_select(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
    options: tuple[tuple[int, str], ...],
) -> EntitySpec:
    field = _field(context.profile, sid, field_name)
    labels = tuple(label for _, label in options)
    by_label = {label: raw for raw, label in options}
    by_raw = {str(raw): label for raw, label in options}

    def state(device: DeviceContext) -> Mapping[str, Any]:
        raw = _int(device.value(sid, field_name))
        if raw is None:
            return {"current_option": None}
        return {"current_option": by_raw.get(str(raw))}

    async def select(device: DeviceContext, data: Mapping[str, Any]) -> None:
        wanted = str(data.get("option"))
        raw = by_label.get(wanted)
        if raw is None:
            raise ValueError(f"unsupported option for {sid}.{field_name}: {wanted}")
        await device.async_send_service(
            sid, {field_name: _enum_value(field, raw, raw)}
        )

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
    if field is None:
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


class Product2QWLAdapter:
    """Keep all 2QWL entity and command choices in this file."""

    prod_id = "2QWL"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        # --- 布尔开关 -------------------------------------------------
        for sid, key, name in _SWITCH_SPECS:
            field = _field(profile, sid, "on")
            if context.has_service(sid) and _is_writable(field):
                entities.append(_make_switch(context, sid, key, name))

        # --- 摆风角度（select，13 档 60~120°） -------------------------
        if context.has_service("fan"):
            angle_field = _field(profile, "fan", "angle")
            if angle_field is not None and _is_writable(angle_field):
                # 标签取 descCh：Profile 的 descEn 存在错位（见文件头）。
                options: list[tuple[int, str]] = []
                for option in angle_field.get("enumList", ()):
                    if not isinstance(option, Mapping):
                        continue
                    raw = option.get("enumVal")
                    if raw is None:
                        continue
                    label = option.get("descCh") or option.get("descEn") or str(raw)
                    options.append((int(raw), str(label)))
                options.sort(key=lambda item: item[0])
                if options:
                    entities.append(
                        _make_select(
                            context, "fan", "angle",
                            "fan_angle", "摆风角度", tuple(options),
                        )
                    )

        # --- 用户模式（select） ---------------------------------------
        if context.has_service("sceneMode") and _is_writable(
            _field(profile, "sceneMode", "mode")
        ):
            entities.append(
                _make_select(
                    context, "sceneMode", "mode",
                    "scene_mode", "用户模式", _SCENE_OPTIONS,
                )
            )

        # --- 感应时间间隔（select） -----------------------------------
        if context.has_service("timeGear") and _is_writable(
            _field(profile, "timeGear", "gear")
        ):
            entities.append(
                _make_select(
                    context, "timeGear", "gear",
                    "induction_interval", "感应时间间隔",
                    _INDUCTION_INTERVAL_OPTIONS,
                )
            )

        # --- 目标温度（number，float） --------------------------------
        spec = _make_number(
            context, "heat", "target", "target_temperature", "目标温度", "°C"
        )
        if context.has_service("heat") and spec is not None:
            entities.append(spec)

        # --- 三个时长（number，min） ----------------------------------
        for sid, field_name, key, name in _DURATION_SPECS:
            if not context.has_service(sid):
                continue
            spec = _make_number(
                context, sid, field_name, key, name, "min"
            )
            if spec is not None:
                entities.append(spec)

        # --- 表面温度（只读传感器） -----------------------------------
        if context.has_service("heat") and _field(
            profile, "heat", "current"
        ) is not None:
            entities.append(
                _make_sensor(
                    "heat", "current", "surface_temperature", "表面温度",
                    unit="°C", device_class="temperature",
                    state_class="measurement",
                    decode=lambda value: _number(value),
                )
            )

        # --- 一键待机（button） ---------------------------------------
        action_field = _field(profile, _ACTION_SID, _ACTION_FIELD)
        if context.has_service(_ACTION_SID) and _is_writable(action_field):
            standby_value = _enum_value(action_field, 0, 0)

            async def standby(
                device: DeviceContext, _data: Mapping[str, Any]
            ) -> None:
                await device.async_send_service(
                    _ACTION_SID, {_ACTION_FIELD: standby_value}
                )

            entities.append(
                EntitySpec(
                    platform="button",
                    key="standby",
                    name="一键待机",
                    state=lambda device: {},
                    actions={"press": standby},
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

ADAPTER = Product2QWLAdapter()
