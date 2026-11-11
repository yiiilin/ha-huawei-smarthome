"""User-contributed protocol for Huawei product 2MGS (华米元情景灯).

产品: 华米元情景灯（吸顶灯）
厂商: 华米元 (HMinet)
型号: HMY-118 (deviceTypeId 112, 吸顶灯, WiFi, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
不跨产品复用，不做未经 Profile/真机证据支持的推断。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  switch.on                 bool  RW 1=开 0=关        -> light on/off
  brightness.brightness     int   RW 1~100 %          -> light brightness
  cct.colorTemperature      int   RW 2700~6400 (K)    -> light color_temp_kelvin

  lightMode.mode            enum  RW 0=非情景模式 1=夜灯模式 2=阅读模式
                                      3=休闲模式 4=工作模式
                                                      -> light_mode (select)
  fade.fade                 int   RW 1~5 秒 渐变时长   -> fade_duration (number)
  switch1.type              enum  RW 0=普通开关 1=凌动开关 -> atomic_switch (select)

  netInfo.intensity         enum  R  20/40/60/80/100  -> wifi_signal_level
  netInfo.RSSI              int   R  -100~0 dB        -> wifi_rssi
  netInfo.IP/SSID/BSSID     string R                  -> 诊断传感器
  update.version            string R 固件版本          -> firmware_version
  update.autoUpdateOn/progress/bootTime/introduction/action  不映射（OTA 运维）
  timer.*（定时）            RW enum/int/array[object]  不映射，见下方说明

=====================================================================
★ 关键取舍：情景模式（lightMode）不映射到 HA 的 effect
=====================================================================
本机 lightMode.mode 的 5 个取值中，**只有 0=非情景模式 是"无情景"**，
1~4 是四套预设场景（夜灯/阅读/休闲/工作）。

按 HA 惯例，这类"设备内置预设场景"通常投影为 light 的 effect 列表。
但本适配器**没有把它做成 effect**，理由是证据不足：

  * Profile 只说这些模式"是"预设，**没有给出任何一档的具体参数**
    （射多少亮度、多少色温、是否只亮某一路灯珠？）。
  * 因此**无法判断**：切换到"阅读模式"后，设备上报的
    brightness/cct 是会被改写、还是保持不变？
  * 如果做成 effect，用户会看到 light 实体同时暴露 brightness、
    color_temp 和 effect 三套控制，但**它们之间是否互相覆盖没有证据**。
    HA 的 effect 语义是"调用一个预设，实体状态随之改变"；在没有证据的
    情况下把 mode 塞进 effect，用户切换 effect 后可能看到亮度色温
    纹丝不动（因为设备改的是内部灯珠组合），从而**误判为功能失效**。

因此本适配器把灯光模式做成**独立的 select 实体**（如实表达"当前处于
哪个模式"），并**不在 light 实体上声明 effect**。这样：
  * 语义诚实：select 就是选模式，light 就是调亮度/色温；
  * 若要联动，可在自动化里同时设置 select + light，行为可预期。

若日后真机确认"切换模式会同步改写 brightness/cct"，可以把 mode 改为
light 的 effect 并在 light_state 里按 mode 投影状态。

=====================================================================
渐变时长（fade）与凌动开关（switch1.type）
=====================================================================
* fade.fade：1~5 秒，控制开关灯时的渐变过渡时间。这是**设备行为参数**
  （不是灯光输出本身），故做成独立 number。
* switch1.type：0=普通开关 / 1=凌动开关。凌动开关指配套的墙面开关
  工作在"回弹式"模式（开关瞬间断开又闭合，靠设备识别脉冲翻转灯光），
  **不是灯光的开关状态**。它是**线路配套方式的配置项**，做成 select。

  ⚠️ 注意：`switch1` 的 characteristicName 是 **type**（不是 on），
  且它是 enum 而非 bool。写入时按 enumVal 数值下发。

=====================================================================
亮度与色温的单位换算
=====================================================================
* 亮度：Profile 用 **1~100 (%)**，HA light 用 **0~255**。
  因此按 Profile 的 min/max 线性映射（1% -> 0，100% -> 255），
  写入时把 0~255 反算回 1~100 并夹取到该整数区间。
  注意 Profile 的 min 是 **1 而非 0**：关灯由 switch.on=0 表达，
  亮度 0 不是合法值，故不能把 HA 的 brightness=0 直传。

* 色温：Profile 直接给 **开尔文**（2700~6400），与 HA 的
  `color_temp_kelvin` 单位一致，**无需 mired 换算**，直接透传并按
  Profile 范围夹取。light 元数据的 min/max_color_temp_kelvin 也
  直接取自 Profile，不写死。

亮度与色温都是 int，写入时按 Profile 的 step(=1) 对齐。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"1"``），
但 characteristicType 是 bool/enum/int，真机只接受**数值**。
直接把枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化。

``_enum_value()`` **只按 enumVal 精确匹配，不做 descCh/descEn
文本回退**——文本回退会在枚举文案互相包含时命中错误档位
（2QWL 适配中踩过的真实 bug）。

=====================================================================
为什么不映射 timer
=====================================================================
timer.timer 是 ``array[object]``，元素含
enable/end/start/sid/para/paraValue/week/id 共 8 个字段，
通过 action 的 更新/新建/删除 驱动。正确写入必须先读取设备当前的
定时列表、按 id 增删改、再整体回写。本集成没有该"读-改-写"事务
能力，且写错会覆盖用户已配置的定时，风险高于收益，故不映射。
用户仍可在华为智慧生活 App 中配置定时。

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
验证环境：真实设备 + 智慧生活 App 对照。

[已实测] light 开关：**通过**。
[已实测] `lightMode` 灯光模式：**通过**。
[已实测] `fade` 渐变时长：**通过**。
[已实测] `atomicSwitch` 开关类型：**通过**。
[已实测] 上面「高风险项」除此项外已逐项确认。

⚠️ **已知问题（当时未解决）**：**亮度 / 色温在 HA 中不可用** —— 实体属性里
   `brightness`、`color_temp_kelvin`、`color_mode` 均为 `null`，界面只显示
   开关，没有亮度与色温滑块。适配器侧已按 Profile 声明
   `supported_color_modes = {color_temp}` 与 2700–6400 K 范围，
   `brightness`（1–100 %）与 `cct.colorTemperature` 两个服务也确实是
   `method=RW / report=1`，**静态检查未发现缺陷，根因当时未定位**，
   怀疑与设备是否上报这两个字段有关。
   → 因此本机是**部分验证**：开关类功能已实测通过，亮度/色温尚未可用。

=====================================================================
尚未覆盖的细节（如需可再确认）
=====================================================================
[ ] **情景模式与亮度/色温的关系**：见上方"关键取舍"。装好后请在
    App 里切到"阅读模式"，观察 HA 中 brightness/color_temp 是否变化。
    若会变化，可把模式改为 light 的 effect（我会据此调整）。
[ ] 亮度映射：Profile 是 1~100%，HA 是 0~255。当前按 min/max 线性
    映射（1%->0、100%->255）。若真机实测最低亮度并非 1%，需修正。
[ ] 色温方向：Profile 2700~6400 直接当作开尔文透传。若真机色温
    档位与数值方向相反（部分厂商用小值表示暖光），需取反修正。
[ ] fade.fade 的取值范围 1~5 秒与单位来自 Profile；是否线性未验证。
[ ] switch1.type（凌动开关）写入后需要配套墙面开关处于对应模式才
    生效；单独改这一项可能没有可观测效果，属预期行为。
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


# --- 服务/字段常量 ---------------------------------------------------
_SWITCH_SID = "switch"
_SWITCH_FIELD = "on"

_BRIGHTNESS_SID = "brightness"
_BRIGHTNESS_FIELD = "brightness"

_CCT_SID = "cct"
_CCT_FIELD = "colorTemperature"

_COLOR_MODE_CCT = "color_temp"

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# HA light 的亮度刻度。
_HA_BRIGHTNESS_MAX = 255


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


def _profile_range(field: Mapping[str, Any] | None) -> tuple[float, float] | None:
    minimum = _number((field or {}).get("min"))
    maximum = _number((field or {}).get("max"))
    if minimum is None or maximum is None or maximum <= minimum:
        return None
    return minimum, maximum


def _coerce(value: Any, field: Mapping[str, Any] | None) -> Any:
    """按 Profile 声明的 characteristicType 数值化命令取值。"""

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
    """只按 enumVal 精确匹配，不做 descCh/descEn 文本回退。"""

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
    order: tuple[str, ...] | None = None,
) -> tuple[tuple[Any, str], ...]:
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


def _clamp(value: Any, field: Mapping[str, Any] | None) -> Any:
    """夹取到 Profile 范围并按 step 对齐后编码。"""

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
# 亮度换算（Profile 百分比 <-> HA 0..255）
# ---------------------------------------------------------------------
def _device_brightness_to_ha(
    value: Any,
    field: Mapping[str, Any] | None,
) -> int | None:
    """把 Profile 的亮度百分比换算到 HA 的 0~255 刻度。"""

    number = _number(value)
    value_range = _profile_range(field)
    if number is None or value_range is None:
        return None
    minimum, maximum = value_range
    number = min(max(number, minimum), maximum)
    return int(round((number - minimum) * _HA_BRIGHTNESS_MAX / (maximum - minimum)))


def _ha_brightness_to_device(
    value: Any,
    field: Mapping[str, Any] | None,
) -> Any:
    """把 HA 的 0~255 亮度反算回 Profile 范围。

    Profile 的 min 是 1（不是 0）：关灯由 switch.on=0 表达，
    亮度 0 不是合法值，因此这里夹取到 [min, max] 而不是允许 0。
    """

    number = _number(value)
    value_range = _profile_range(field)
    if number is None or value_range is None:
        raise ValueError("2MGS brightness range is missing from the Profile")
    minimum, maximum = value_range
    number = min(max(number, 0.0), float(_HA_BRIGHTNESS_MAX))
    device_value = minimum + number * (maximum - minimum) / _HA_BRIGHTNESS_MAX
    return _clamp(device_value, field)


# ---------------------------------------------------------------------
# light 动作
# ---------------------------------------------------------------------
async def _turn_on(context: DeviceContext, data: Mapping[str, Any]) -> None:
    switch_field = _field(context.profile, _SWITCH_SID, _SWITCH_FIELD)
    await context.async_send_service(
        _SWITCH_SID, {_SWITCH_FIELD: _enum_value(switch_field, 1, 1)}
    )
    brightness_field = _field(context.profile, _BRIGHTNESS_SID, _BRIGHTNESS_FIELD)
    if data.get("brightness") is not None:
        await context.async_send_service(
            _BRIGHTNESS_SID,
            {
                _BRIGHTNESS_FIELD: _ha_brightness_to_device(
                    data["brightness"], brightness_field
                )
            },
        )
    cct_field = _field(context.profile, _CCT_SID, _CCT_FIELD)
    if data.get("color_temp_kelvin") is not None:
        await context.async_send_service(
            _CCT_SID,
            {_CCT_FIELD: _clamp(data["color_temp_kelvin"], cct_field)},
        )


async def _turn_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    switch_field = _field(context.profile, _SWITCH_SID, _SWITCH_FIELD)
    await context.async_send_service(
        _SWITCH_SID, {_SWITCH_FIELD: _enum_value(switch_field, 0, 0)}
    )


# ---------------------------------------------------------------------
# 实体构造
# ---------------------------------------------------------------------
def _make_select(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
    order: tuple[str, ...] | None = None,
) -> EntitySpec | None:
    field = _field(context.profile, sid, field_name)
    if field is None or not _is_writable(field):
        return None
    options = _enum_options(field, order)
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


class Product2MGSAdapter:
    """Keep all 2MGS entity and command choices in this file."""

    prod_id = "2MGS"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        # --- light：开关 / 亮度 / 色温 --------------------------------
        brightness_field = _field(profile, _BRIGHTNESS_SID, _BRIGHTNESS_FIELD)
        cct_field = _field(profile, _CCT_SID, _CCT_FIELD)
        cct_range = _profile_range(cct_field)
        if (
            context.has_service(_SWITCH_SID)
            and context.has_service(_BRIGHTNESS_SID)
            and context.has_service(_CCT_SID)
            and _profile_range(brightness_field) is not None
            and cct_range is not None
        ):
            def light_state(device: DeviceContext) -> Mapping[str, Any]:
                return {
                    "is_on": _bool(device.value(_SWITCH_SID, _SWITCH_FIELD)),
                    "brightness": _device_brightness_to_ha(
                        device.value(_BRIGHTNESS_SID, _BRIGHTNESS_FIELD),
                        brightness_field,
                    ),
                    "color_temp_kelvin": _int(
                        device.value(_CCT_SID, _CCT_FIELD)
                    ),
                    "color_mode": _COLOR_MODE_CCT,
                }

            entities.append(
                EntitySpec(
                    platform="light",
                    key="light",
                    name=None,
                    state=light_state,
                    metadata={
                        "supported_color_modes": {_COLOR_MODE_CCT},
                        "min_color_temp_kelvin": int(cct_range[0]),
                        "max_color_temp_kelvin": int(cct_range[1]),
                    },
                    actions={"turn_on": _turn_on, "turn_off": _turn_off},
                )
            )

        # --- 灯光模式（select，刻意不做 effect，见文件头说明） --------
        mode_spec = _make_select(
            context, "lightMode", "mode", "light_mode", "灯光模式"
        )
        if mode_spec is not None:
            entities.append(mode_spec)

        # --- 渐变时长（number） ---------------------------------------
        fade_spec = _make_number(
            context, "fade", "fade", "fade_duration", "渐变时长", "s"
        )
        if fade_spec is not None:
            entities.append(fade_spec)

        # --- 凌动开关（select；字段名是 type，不是 on） ---------------
        atomic_spec = _make_select(
            context, "switch1", "type", "atomic_switch", "开关类型"
        )
        if atomic_spec is not None:
            entities.append(atomic_spec)

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

ADAPTER = Product2MGSAdapter()
