"""User-contributed protocol for Huawei product 2QCQ (杜亚智能窗帘 隐形大师).

产品: 杜亚智能窗帘 隐形大师
厂商: 杜亚 (dooya)
型号: Hx (deviceTypeId 01C, 开合帘, WiFi, uiType H5)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
**不跨产品复用**。2QCQ 与 2AOQ 虽同为杜亚开合帘，但控制通道不同：

  差异点        2AOQ (DH6)              2QCQ (隐形大师)
  ------------  ----------------------  ----------------------
  开/关/暂停    mode.mode  (0/1/2)      action.action (0=关/1=开/2=暂停)
  开合度        opener.{target,current}  opener.{target,current}
  开合速度      无                      switchSpeed.action (0/1/2)
  常用位置      无                      favorate.{putFavorate,setFavorate}
  转向/方向     无                      changeDirection / directionalmode

因此各自独立实现，不提取公共基类，也不共享映射表。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  opener.current         int  R  0~100 %  当前开合度  -> cover current_position
  opener.target          int  RW 0~100 %  目标开合度  -> cover set_position
  action.action          enum RW 0=关 1=开 2=暂停     -> cover open/close/stop

  switchSpeed.action     enum RW 0=慢速(静音) 1=中速 2=高速 -> speed (select)
  favorate.putFavorate   enum RW 0=常用位置  运行到常用位置 -> button
  favorate.setFavorate   int  RW 0~100 %     设置常用位置   -> number
  commonFaultDetection.{code,status}  R      故障            -> problem
  netInfo.*                                  网络            -> 诊断传感器

  changeDirection.action enum RW 0=转向 1=启用          不映射，见下方说明
  directionalmode.mode   enum RW 1=左右                 不映射，见下方说明
  mode.mode              enum RW 0=双开 1=左开 2=右开    不映射，见下方说明
  timer.*                                     定时器      不映射（同 2Q2T 理由）
  checkSum.checkSum     string R 固件校验值              不映射（内部校验值）
  update.*（25 个字段）  OTA 全流程                      不映射（OTA 运维，无用户价值）

=====================================================================
为什么不映射 changeDirection / directionalmode / mode
=====================================================================
1. changeDirection.action 的枚举是 ``0=转向 / 1=启用``，attrName 为
   "设备转向"，descCh 只有一句"改变电机转动方向"。语义不清：写入
   0 是"执行一次转向"还是"切换到正向"？写入 1 是"启用反向"还是
   "确认转向"？Profile 没有任何状态回报字段能验证结果（该服务只有
   action 一个特征，无 report 状态），因此**无法确认写入效果**，
   按失败关闭原则不暴露。

2. directionalmode.mode 的枚举**只有一个值** ``1=左右``。单值枚举
   通常表示"当前/唯一支持的取值"，写入它没有任何控制意义（写了也
   只是回读同一个值），因此不做 select。

3. mode.mode 的枚举是 ``0=双开 1=左开 2=右开``，attrName 明确写的是
   **"配置产品图片"**，descCh 进一步说明"首次配置时使用，仅更新主图"。
   这是 App 首次配网时选择产品渲染图用的**配置项，不是电机运行参数**，
   改动它不会影响窗帘行为，故不映射。

以上三项如真机证明有实际控制效果，可再补充。

=====================================================================
开合度方向
=====================================================================
Profile 对 opener.target 的描述明确：
  "下发100时，窗帘全开（全透光）；下发0时，窗帘全关（全遮光）"
这与 HA cover 的约定（0=关、100=开）**一致**，因此不需取反。
（对比 2AOQ 的适配器里保留了 _POS_REVERSED 开关以防方向相反；
 本机 Profile 文字已明确方向，故不加该开关，保持简单。）

若真机实测方向相反，只需在 _POSITION_REVERSED 处改为 True。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"1"``），
但 characteristicType 是 bool/enum/int，真机只接受**数值**。
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
[ ] 控制命令：开/关/暂停、指定开合度、速度、常用位置均未实测。
[ ] **action.action 与 opener.target 的优先级未验证**：
    "开"（action=1）与"设置开合度"（target=N）是否互相覆盖？
    例如先 action=1 全开、再 target=50，窗帘最终停在哪里？
    本适配器如实分别下发，不做组合推断；真机验证后如有需要
    可在 open/close 时同时下发 target。
[ ] 暂停（action=2）在电机已停止时的行为未验证（是否报错）。
[ ] 开合度方向：Profile 文字说明与 HA 约定一致，但未实测。
    若真机相反，改 _POSITION_REVERSED = True。
[ ] favorate.setFavorate 写入后是否立即生效、putFavorate 是否
    需要先设置过常用位置才能运行，均未验证。
[ ] 故障码 code 与 status 的一致性未验证：当前以 status 为主、
    code 作描述；若真机出现 status=0 但 code!=0，需改为以 code 为准。
[ ] code=2（无行程）是"需要用户开合一次以设置行程"的提示态，
    不是硬件故障。当前仍按 problem=on 上报（因为它确实需要用户处理），
    若你认为该提示不应触发告警，可据此调整。
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


_POS_MIN = 0
_POS_MAX = 100

# Profile 明确：100=全开（全透光）、0=全关（全遮光），与 HA 约定一致。
# 若真机实测方向相反，改为 True。
_POSITION_REVERSED = False

# action.action 枚举（本机 Profile，不与 2AOQ 的 mode.mode 混用）
_ACTION_CLOSE = 0
_ACTION_OPEN = 1
_ACTION_STOP = 2

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}


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


def _position(value: Any) -> int | None:
    """Decode a 0~100 opening percentage into HA's cover position."""

    position = _int(value)
    if position is None:
        return None
    position = min(max(position, _POS_MIN), _POS_MAX)
    return _POS_MAX - position if _POSITION_REVERSED else position


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


def _enum_options(
    field: Mapping[str, Any] | None,
) -> tuple[tuple[str, Any], ...]:
    """Return ``(label, raw_enum_value)`` pairs from a Profile enum list."""

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


def _clamp_position(value: Any, field: Mapping[str, Any] | None) -> Any:
    """Clamp a target opening to the Profile range and align to its step."""

    number = _number(value)
    if number is None:
        return None
    minimum = _number((field or {}).get("min"))
    maximum = _number((field or {}).get("max"))
    lo = minimum if minimum is not None else float(_POS_MIN)
    hi = maximum if maximum is not None else float(_POS_MAX)
    if hi < lo:
        lo, hi = hi, lo
    number = min(max(number, lo), hi)
    step = _number((field or {}).get("step"))
    if step is None or step <= 0:
        data_type = str((field or {}).get("characteristicType") or "").casefold()
        step = 1.0 if data_type in {"int", "integer", "enum", "bool"} else None
    if step:
        number = lo + round((number - lo) / step) * step
        number = min(max(number, lo), hi)
    return _coerce(round(number, 4), field)


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
    decoder = decode or (lambda value: _int(value))

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


class Product2QCQAdapter:
    """Keep all 2QCQ entity and command choices in this file."""

    prod_id = "2QCQ"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []
        has_opener = context.has_service("opener")
        action_field = _field(profile, "action", "action")

        # --- cover ----------------------------------------------------
        if has_opener:
            target_field = _field(profile, "opener", "target")

            def cover_state(device: DeviceContext) -> Mapping[str, Any]:
                position = _position(device.value("opener", "current"))
                return {
                    "current_position": position,
                    # 只有拿到位置才能判定开关；未知时返回 None 而非猜测。
                    "is_closed": None if position is None else position == 0,
                }

            async def _send_action(device: DeviceContext, value: int) -> None:
                await device.async_send_service(
                    "action",
                    {"action": _enum_value(action_field, value, value)},
                )

            async def open_cover(
                device: DeviceContext, _data: Mapping[str, Any]
            ) -> None:
                await _send_action(device, _ACTION_OPEN)

            async def close_cover(
                device: DeviceContext, _data: Mapping[str, Any]
            ) -> None:
                await _send_action(device, _ACTION_CLOSE)

            async def stop_cover(
                device: DeviceContext, _data: Mapping[str, Any]
            ) -> None:
                await _send_action(device, _ACTION_STOP)

            async def set_position(
                device: DeviceContext, data: Mapping[str, Any]
            ) -> None:
                raw = _number(data.get("position"))
                if raw is None:
                    raise ValueError("position is required")
                position = min(max(int(round(raw)), _POS_MIN), _POS_MAX)
                device_value = (
                    _POS_MAX - position if _POSITION_REVERSED else position
                )
                await device.async_send_service(
                    "opener",
                    {"target": _clamp_position(device_value, target_field)},
                )

            actions: dict[str, Any] = {"set_position": set_position}
            # 只有 action 服务可写时才暴露 open/close/stop。
            if context.has_service("action") and _is_writable(action_field):
                actions["open"] = open_cover
                actions["close"] = close_cover
                actions["stop"] = stop_cover

            entities.append(
                EntitySpec(
                    platform="cover",
                    key="curtain",
                    name=None,
                    state=cover_state,
                    metadata={"device_class": "curtain"},
                    actions=actions,
                )
            )

        # --- 开合速度（select） ---------------------------------------
        if context.has_service("switchSpeed"):
            speed_field = _field(profile, "switchSpeed", "action")
            options = _enum_options(speed_field)
            if options and _is_writable(speed_field):
                labels = tuple(label for label, _ in options)
                by_label = {label: raw for label, raw in options}
                by_raw = {str(raw): label for label, raw in options}

                def speed_state(device: DeviceContext) -> Mapping[str, Any]:
                    raw = device.value("switchSpeed", "action")
                    if raw is None:
                        return {"current_option": None}
                    return {"current_option": by_raw.get(str(_int(raw)))}

                async def select_speed(
                    device: DeviceContext, data: Mapping[str, Any]
                ) -> None:
                    wanted = str(data.get("option"))
                    raw = by_label.get(wanted)
                    if raw is None:
                        raise ValueError(f"unsupported speed: {wanted}")
                    await device.async_send_service(
                        "switchSpeed",
                        {"action": _enum_value(speed_field, raw, raw)},
                    )

                entities.append(
                    EntitySpec(
                        platform="select",
                        key="speed",
                        name="开合速度",
                        state=speed_state,
                        metadata={"options": labels},
                        actions={"select_option": select_speed},
                    )
                )

        # --- 常用位置 -------------------------------------------------
        if context.has_service("favorate"):
            set_field = _field(profile, "favorate", "setFavorate")
            put_field = _field(profile, "favorate", "putFavorate")

            if set_field is not None and _is_writable(set_field):
                minimum = _number(set_field.get("min"))
                maximum = _number(set_field.get("max"))
                step = _number(set_field.get("step"))
                low = minimum if minimum is not None else float(_POS_MIN)
                high = maximum if maximum is not None else float(_POS_MAX)

                async def set_favorite(
                    device: DeviceContext, data: Mapping[str, Any]
                ) -> None:
                    value = _clamp_position(data.get("value"), set_field)
                    if value is None:
                        return
                    await device.async_send_service(
                        "favorate", {"setFavorate": value}
                    )

                def favorite_state(device: DeviceContext) -> Mapping[str, Any]:
                    return {
                        "native_value": _number(
                            device.value("favorate", "setFavorate")
                        )
                    }

                entities.append(
                    EntitySpec(
                        platform="number",
                        key="favorite_position",
                        name="常用位置",
                        state=favorite_state,
                        metadata={
                            "min": low,
                            "max": high,
                            "step": step if step and step > 0 else 1,
                            "unit": "%",
                        },
                        actions={"set_value": set_favorite},
                    )
                )

            if put_field is not None and _is_writable(put_field):
                run_value = _enum_value(put_field, 0, 0)

                async def run_favorite(
                    device: DeviceContext, _data: Mapping[str, Any]
                ) -> None:
                    await device.async_send_service(
                        "favorate", {"putFavorate": run_value}
                    )

                entities.append(
                    EntitySpec(
                        platform="button",
                        key="run_favorite",
                        name="运行到常用位置",
                        state=lambda device: {},
                        actions={"press": run_favorite},
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

ADAPTER = Product2QCQAdapter()
