"""User-contributed protocol for Huawei product 2RC9 (名豆之约智能插座10A 2代).

产品: 名豆之约智能插座 10A 2代
厂商: 广州名豆 (MINDOR)
型号: ZCZ003 (deviceTypeId 01D, 转换插座, Wi-Fi+BLE+SLE, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
**不跨产品复用**。2RC9 与仓库既有 2MFF（佛山照明插座）同属转换插座，
但服务集合不同（2MFF 有 electric.voltage/current/saveConsum 与
power.maximum/load，本机只有 electric.totalElectricity 与
power.current），故各自独立实现。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  switch.on                 bool  RW 1=开 0=关   电源开关   -> switch (主控)
  childLockSwitch.on        bool  RW 童锁         -> child_lock
  indicator.on              bool  RW 指示灯        -> indicator

  power.current             int   R 0~3000 W 当前功率  -> power (device_class=power)
  electric.totalElectricity float R 0~99999 kWh 总用电量
                                                   -> energy_total (total_increasing)

  commonMemorySwitch.status enum  RW 0=关 1=开 2=保持上次状态
                                                   -> power_on_memory (select)

  commonFaultDetection.code   enum R 0=正常 1=功率过载已断电 2=电流异常已断电
                                                   -> problem + 故障描述属性
  commonFaultDetection.status bool R 1=异常 0=正常  -> 同上

  netInfo.intensity         enum  R 20/40/60/80/100   -> wifi_signal_level
  netInfo.RSSI              int   R -100~0 dB         -> wifi_rssi
  netInfo.IP/SSID/BSSID     string R                  -> 诊断传感器

  update.version            string R 固件版本          -> firmware_version
  update.on/action/progress/bootTime/introduction      不映射（OTA 运维）
  checkSum.checkSum         string R 固件校验值       不映射（内部校验值）
  delay.*（倒计时）          array[object]            不映射，见下方说明
  timer.*（定时器服务）      array[object]            不映射，见下方说明

=====================================================================
为什么不映射 delay / timer
=====================================================================
两个服务都是"读-改-写"型：
  * delay.delay —— 倒计时，元素含
    enable/para/start/end/sid/id/paraValue 共 7 个字段；
  * timer.timer —— 定时器，元素含
    enable/sid/end/para/start/id/paraValue/week 共 8 个字段。
两者都通过 ``action`` 的 更新/创建/删除 驱动。正确写入必须先读取设备
当前的列表、按 id 增删改、再整体回写。本集成没有该事务能力，
且写错会覆盖用户已配置的定时/倒计时，风险高于收益，故不映射。
用户仍可在华为智慧生活 App 中配置。

注意：这两个服务的 sid 是 ``delay`` 与 ``timer``，与其它机型的同名
服务结构近似但**字段顺序不同**（本机 delay 无 week、timer 有 week），
因此**不能按字段位置解析**，这也是不映射的理由之一。

=====================================================================
断电记忆（commonMemorySwitch.status）的语义
=====================================================================
Profile 的 descCh 明确："断电后上电的初始插座的状态"，枚举为
  0=关（上电后保持关闭）
  1=开（上电后自动开启）
  2=保持上次状态（恢复断电前的状态）
这是**设备行为配置**，做成 select 暴露三个语义明确的选项。
注意它的 characteristicName 是 ``status``（不是 on），且是 **enum**
而非 bool，写入时按 enumVal 数值下发。

=====================================================================
用电量与功率的 HA 映射
=====================================================================
* power.current：单位 W，Profile 声明 int、0~3000。
  HA 的 ``device_class=power`` 配合 ``state_class=measurement``，
  单位用 "W"，与 HA 原生单位一致，无需换算。
* electric.totalElectricity：单位 kWh，Profile 声明 float、0~99999。
  HA 的 ``device_class=energy`` 配合 ``state_class=total_increasing``
  （累计递增，适合"总用电量"），单位 "kWh"。

  ⚠️ 只映射"总用电量"这一个字段：本机 Profile **没有**当日用电、
  峰值功率、电压、电流等字段，故不构造这些实体（避免凭空造值）。

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
[ ] 控制命令：电源开关、童锁、指示灯、断电记忆 4 项均未实测。
[ ] **过载告警的联动**：故障码 1/2 表示"已自动断电"。真机上出现
    该告警时，``switch.on`` 是否会被设备置 0？当前只如实读取开关
    状态，不做事后推断；若设备不上报回落状态，开关实体会与实际
    不符，届时需要调整。
[ ] power.current 与 totalElectricity 的**上报频率**未验证
    （影响 HA 统计曲线密度，但不影响正确性）。
[ ] totalElectricity 的初值/清零行为未验证（换插座或复位后是否归零）。
    total_increasing 语义能容忍归零，但若真机把"清零"表现为大幅回退
    以外的形式，需再评估。
[ ] commonMemorySwitch.status=2（保持上次状态）的生效条件未验证。
[ ] netInfo 各字段设备是否实际上报未验证（诊断类，不影响主功能）。
[ ] 本机没有电压/电流字段，因此无法实现"过载阈值"类自动化；
    如需，应基于 power.current 自行设定阈值。
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

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# 需要以 switch 实体暴露的布尔开关（sid, key, 名称）
_SWITCH_SPECS = (
    ("childLockSwitch", "child_lock", "童锁"),
    ("indicator", "indicator", "指示灯"),
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


def _enum_label(field: Mapping[str, Any] | None, value: Any) -> str | None:
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
# 实体构造
# ---------------------------------------------------------------------
def _make_switch(
    context: DeviceContext,
    sid: str,
    key: str,
    name: str,
) -> EntitySpec | None:
    field = _field(context.profile, sid, "on")
    if field is None or not _is_writable(field):
        return None
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


class Product2RC9Adapter:
    """Keep all 2RC9 entity and command choices in this file."""

    prod_id = "2RC9"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []

        # --- 主控开关（必须有 switch 服务才建实体） --------------------
        if context.has_service(_SWITCH_SID):
            spec = _make_switch(context, _SWITCH_SID, "power", "电源")
            if spec is not None:
                entities.append(spec)

        # --- 童锁 / 指示灯 --------------------------------------------
        for sid, key, name in _SWITCH_SPECS:
            if not context.has_service(sid):
                continue
            spec = _make_switch(context, sid, key, name)
            if spec is not None:
                entities.append(spec)

        # --- 断电记忆（select；字段名是 status，非 on） ---------------
        memory_spec = _make_select(
            context,
            "commonMemorySwitch",
            "status",
            "power_on_memory",
            "断电记忆",
            # 按语义排序：关 -> 开 -> 保持上次状态
            ("0", "1", "2"),
        )
        if memory_spec is not None:
            entities.append(memory_spec)

        # --- 功率 / 用电量 --------------------------------------------
        # 注意 key 必须与上面的主控 switch 区分：HA 的 unique_id 由
        # (home_id, dev_id, key) 组成，若两者都用 "power" 会冲突，
        # 导致实体注册互相覆盖。故开关用 "power"，传感器加后缀。
        if context.has_service("power"):
            entities.append(
                _make_sensor(
                    "power", "current", "power_meter", "当前功率",
                    unit="W", device_class="power",
                    state_class="measurement", decode=_int,
                )
            )
        if context.has_service("electric"):
            entities.append(
                _make_sensor(
                    "electric", "totalElectricity", "energy_total",
                    "总用电量", unit="kWh", device_class="energy",
                    state_class="total_increasing", decode=_number,
                )
            )

        # --- 故障 -----------------------------------------------------
        if context.has_service("commonFaultDetection"):
            code_field = _field(
                profile, "commonFaultDetection", "code"
            )

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

ADAPTER = Product2RC9Adapter()
