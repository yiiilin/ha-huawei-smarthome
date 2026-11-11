"""User-contributed protocol for Huawei product 2LC9 (鸿蒙智选 小豚当家室外摄像头 4G版).

产品: 鸿蒙智选 小豚当家室外摄像头 4G版
厂商: 智多豚 (dophigo)
型号: XT-H32 (deviceTypeId 008, 网络摄像头, WiFi, uiType PLUGIN)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
**不跨产品复用**。2LC9 与 2MZN 虽同厂商同设备类型，但服务集合不同
（本机有 4G 流量服务、无云台预置点；2MZN 有 6 个预置点、无 4G），
因此各自独立实现，不提取公共基类，也不共享映射表。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  switch.on              bool  RW 1=开 0=关(待机)  摄像头开关 -> camera_switch
  shootSwitch.on         bool  RW 抓拍照开关          -> shoot_switch
  videoSwitch.on         bool  RW 摄像开关            -> video_switch

  alarmEvent.animalAlarm       bool RW 动物检测       -> animal_alarm
  alarmEvent.humanBodyAlarm    bool RW 人形检测       -> human_body_alarm
  alarmEvent.videoAlarm        bool R  视频检测       -> video_alarm
  alarmEvent.audioAlarm        bool R  声音检测       -> audio_alarm
  alarmEvent.babyCryAlarm      bool R  婴儿哭声检测   -> baby_cry_alarm
  alarmEvent.auxiliaryFireAlarm bool R 火焰检测       -> fire_alarm
  alarmEvent.alarmId           string RW 告警信息     不映射为实体，见下方说明
  告警字段本身做成**只读 sensor**（显示 Profile 文案"有告警/无告警"），
  不是 binary_sensor —— 原因见下方"告警实体形态"专节。
  另有一个 alarm 事件实体（event 平台），每次告警推送触发一次。
  每个告警通道另配一个「最近触发」sensor（device_class=timestamp），
  形如 <字段名>_last_triggered，HA 会渲染成"3 分钟前"。

  lteService.expireDays        int  R 0~30           默认不创建，见下节
  lteService.expireStatus      int  R 0~30           默认不创建，见下节
  lteService.alarmId           string R PUSH消息id   不映射（无用户语义）

  netInfo.intensity      enum  R 20/40/60/80/100     默认不创建，见下节
  netInfo.RSSI           int   R -100~0 dB           默认不创建，见下节
  netInfo.IP/SSID/BSSID  string R                    默认不创建，见下节

  update.version         string R 固件版本            默认不创建，见下节
  update.progress/bootTime/introduction/action       不映射（OTA 流程）

  deviceInfo.id / verifyId   string R                不映射（厂商云端凭据）
  pushStatus.status          int    RW               不映射（见下方说明）

=====================================================================
告警实体形态（真机实测后从 binary_sensor 改为 sensor）
=====================================================================
**真机实测结论：告警字段是一次性信号，不会自行恢复。**

现象（用户实测）：触发后一直显示"已触发"，从不回到 off。

原因：Profile 的 enumList 虽然定义了 ``1=有告警 / 0=无告警``，
但设备只在检测到目标时推送 ``1``，**从不推送 ``0``**。
也就是说这些字段是"事件通知"，不是"实时电平"。

若做成 binary_sensor，HA 会按实时电平处理，于是首次触发后永久停在 on：
  * 界面长期显示"有人"，与事实不符；
  * 后续同类告警因为状态没变化（有告警→有告警）而**无法再次触发
    自动化**，静默失效——这比没有实体更糟。

因此本适配器按仓库既有摄像头适配器 ``prod_2gaf.py`` 的做法，
把告警字段做成**只读 sensor**，显示 Profile 枚举文案（"有告警 / 无告警"）。
它诚实表达"最近一次上报的告警状态"，而不是声称"此刻正在告警"。

因此本适配器提供：
  1. sensor        ：描述"最近一次上报的告警是什么"（文案，非布尔）；
  2. 最近触发 sensor：device_class=timestamp，最近一次收到该告警的时间；
  3. event 实体     ：每次被接受的告警推送都触发一次事件。
     **需要"每次触发都响应"的自动化应基于它**，并可读取 alarm_id
     区分不同事件，因为 sensor 在同类告警重复发生时不会变化。

注意：animalAlarm 与 humanBodyAlarm 在本 Profile 是 RW（可写），
说明它们兼具"检测使能开关"语义；但 Profile 的 attrName 写的是
"动物检测/人形检测"且 descCh 明确"仅做IFTTT条件"，无法确定写入
1/0 是"使能检测"还是"模拟告警"。**在缺乏真机证据的情况下不暴露写
命令**，只做只读告警呈现（符合 Skill 的失败关闭原则）。

=====================================================================
「最近触发」传感器（相对时间显示）
=====================================================================
实现：每个告警通道增加一个 sensor，metadata 为
``device_class=timestamp``，native_value 给一个 aware datetime。
HA 对 timestamp 传感器原生渲染相对时间（"3 分钟前"），无需自定义。

语义是"最近一次收到告警推送的时间"，**不是**"该告警正在发生的时长"。
因为字段锁存（见上节），若把时间理解成"已持续多久"，会得出
"有人已经在那里待了两小时"这种错误结论。

一个关键实现细节（否则会一直显示 unknown）：

**不能直接用 device.service_updated_at()**。
它内部走 ``parse_remote_timestamp``，只接受整秒或**带小数点**的形态；
而实时 MQTT 推送是**不带小数点**的 9 位纳秒
（``20260914T222103156Z``），会被判为不可解析 → 返回 None。
而 None 恰好出现在告警刚发生的时刻——正是最需要时间的时刻。
   故本文件用 ``_reported_at()`` 对该形态补一条解析兜底。

与 event 实体属性 ``detected_at`` 的区别：
  * ``detected_at`` 来自 alarmId 的 ``<id>::<时间>`` 后缀，**每次推送**携带，
    是设备侧的事件时间；但它随事件结束而消失，不适合做常驻展示。
  * 本 sensor 反映"最近一次收到该告警的时间"，可长期停留在实体上，
    更适合"多久之前"这类展示需求。两者互为补充，未做合并。

已知局限（未实测，需真机确认）：
  * 若设备的 ts 语义是"服务级最后写入"而非"字段级变化时刻"，
    则同一服务内其他字段的上报可能把时间推后（本机 6 个告警字段共用
    同一个 alarmEvent 服务，此风险比 2MZN 更需留意）。
    真机验证建议：触发人形检测后等 1~2 分钟，再触发另一个告警通道，
    看两个通道的时间是否会互相影响。
  * 时间取自设备上报的 UTC ts，与 HA 主机时钟无关；显示按本地时区换算。

=====================================================================
为什么不映射 alarmId / deviceInfo / pushStatus
=====================================================================
1. alarmEvent.alarmId 与 lteService.alarmId：Profile 说明该 ID 由设备
   上报后**随 PUSH 消息交给华为智慧生活 App 插件**，由插件向厂商云端
   换取图片/视频 URL。本集成不消费华为 PUSH 通道，也没有该厂商的取图
   接口，做成 sensor 只会暴露一串无意义字符串。
   它仍会作为 event 实体的属性（alarm_id）供自动化关联使用。

2. deviceInfo.id / verifyId：厂商云端的设备注册 ID 与插件校验码，
   属于凭据类信息，暴露到 HA 状态机没有用户价值且有泄露风险。

3. pushStatus.status：Profile 中该服务**未声明 permission，
   也未声明 method 之外的任何元数据**（无 attrName/descCh/enumList），
   取值域 0~65535 无枚举说明。含义未知，按失败关闭原则不映射。

4. lteService.expireStatus 同样是纯 int（0~30）且无枚举说明，
   仅作为原始数值输出；若真机确认为状态码枚举，后续可改为 select。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
Profile 的 enumList 里 ``enumVal`` 一律是**字符串**（如 ``"1"``），
但 characteristicType 是 bool/enum/int，真机只接受**数值**。
直接把枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化，
取值本身从 Profile 的 enumList 读取，不硬编码。

注：本机 alarmEvent 下有若干字段 permission 为空字符串（供应商资料
填写不完整），本适配器一律按"只读"处理，绝不尝试写入。

=====================================================================
没有 camera 平台实体（硬限制，非漏适配）
=====================================================================
本仓库未注册 camera 平台（见 const.PLATFORMS），且本 Profile 也**没有**
任何快照 URL / 视频流地址特征。因此无法在 HA 中呈现实时画面或抓拍图。
按仓库"避免错误状态映射"的原则，本适配器把云端真实可读/可写的控制与
侦测能力映射到受支持的平台：switch / binary_sensor / event / sensor。

=====================================================================
为什么诊断实体默认不创建
=====================================================================
真机实测：以下 8 个实体**全部长期为 unknown** —— 设备根本不上报这些
读取字段，集成侧也没有别的读取路径可以拿到：

  * ``lteService``：4G 流量剩余天数 / 4G 流量状态（本机为 4G 版特有）
  * ``netInfo``   ：信号格数 / RSSI / IP / SSID / BSSID
  * ``update``    ：固件版本

保留它们只会让设备页被一堆永远没有值的实体占满，用户还会以为是集成坏了。
因此**默认不创建**。

代码并未删除，而是收进 ``_make_diagnostic_entities()``，由模块级开关
``_ENABLE_DIAGNOSTIC_ENTITIES``（当前 False）控制。
若日后在真机上确认这些字段**确实会上报**（例如固件升级后行为改变），
把该开关改为 True 即可全部恢复，无需重新实现。

注意：开关打开后取值逻辑仍是原样——按 Profile 字段读取，不做任何猜测；
设备不上报时依然显示 unknown。这是刻意的：宁可显示 unknown，
也不给一个编造出来的网络/流量状态。

另注：``lteService.expireDays`` / ``expireStatus`` 的单位与语义**本来就未知**
（Profile 未给 attrName/unit），这独立于"是否上报"的问题。
即使日后恢复创建，也应先确认语义再决定如何呈现。

=====================================================================
真机实测记录
=====================================================================
[已实测] 实体创建与状态读取：**通过**。摄像头/摄像/拍照开关状态、
    6 项告警检测、告警 sensor 与 event 实体的显示均已确认。
[已实测] 控制命令：**通过**。switch / shootSwitch / videoSwitch 的
    on 写入均已确认生效。
=====================================================================
尚未覆盖的细节（如需可再确认）
=====================================================================
以下为**尚未覆盖的细节**，与上表不冲突（它们不是"没验过"，
而是当时没有专门做实验去区分）：

[ ] 告警事件：event 实体依赖 deviceDataChanged 推送，需真机确认
    设备上报 alarmEvent 的字段形态（本机 videoAlarm 等为只读 R，
    animalAlarm/humanBodyAlarm 为 RW）。
[已实测] lteService（4G 流量两项）、netInfo（5 项）、update.version 全部为
    unknown：设备不上报这些读取字段。已按实测结果默认不创建对应实体
    （见上方"为什么诊断实体默认不创建"）。若日后确认会上报，
    把 _ENABLE_DIAGNOSTIC_ENTITIES 改为 True 即可恢复。
[ ] 4G 流量：lteService.expireDays / expireStatus 的单位与语义**本来就未知**
    （Profile 未给 attrName/单位）。这一点独立于"是否上报"：
    即使日后恢复创建实体，也应先确认语义再决定呈现方式。
    expireDays 推测为"剩余天数"，expireStatus 推测为状态码，均未验证。
[ ] humanBodyAlarm / animalAlarm 的写入语义未验证，故未暴露写命令。
    若真机确认写 1/0 是"检测使能开关"，可新增对应 switch 实体。
[已实测] 告警字段的复位行为：**不会自行恢复**。设备只推 1 不推 0，
    触发后一直显示已触发。据此不再映射为 binary_sensor，
    改为只读 sensor（显示 Profile 文案）+ 最近触发时间 + event。
[ ] 「最近触发」传感器未实测。需确认为相对时间（而不是 unknown）；
    若是 unknown，说明设备 ts 格式与本文件的兜底解析不符，
    需按真机实际格式调整 _reported_at()。
[ ] 6 个通道共用同一 alarmEvent 服务，其他字段上报是否会推后时间
    （见上方"已知局限"）。
[ ] event 实体的 event_types 是否与设备实际上报的字段组合一致
    （一次推送可能同时置位多个字段，届时会同时触发多个事件类型）。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_ALARM_SID = "alarmEvent"

# 「最近触发」传感器的 key 后缀：<告警字段名>_last_triggered
_TRIGGERED_SUFFIX = "_last_triggered"

# 诊断实体（lteService / netInfo / update）总开关。
# 真机实测：这些实体全部为 unknown，设备不上报对应字段。
# 默认关闭以免污染界面；若日后确认真机会上报，改为 True 即可恢复。
_ENABLE_DIAGNOSTIC_ENTITIES = False

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {20: 0, 40: 1, 60: 2, 80: 3, 100: 4}

# alarmEvent 中需要以只读 sensor + event 暴露的告警字段。
# (characteristicName, event_type, 中文名, device_class)
# 实体 key 直接用 characteristicName（保持与 Profile 一致的可读性）。
# device_class 仅作分类参考：这些字段做成 sensor（不设 device_class），
# 因为设备从不推送清除值，binary_sensor 会永久锁存。
_ALARM_FIELDS = (
    ("humanBodyAlarm", "human_body", "人形检测", "motion"),
    ("animalAlarm", "animal", "动物检测", "motion"),
    ("videoAlarm", "video", "视频检测", "motion"),
    ("audioAlarm", "audio", "声音检测", "sound"),
    ("babyCryAlarm", "baby_cry", "婴儿哭声检测", "sound"),
    ("auxiliaryFireAlarm", "fire", "火焰检测", "smoke"),
)

# 需要以 switch 实体暴露的服务（sid, key, 名称）
_SWITCH_SPECS = (
    ("switch", "camera", "摄像头开关"),
    ("videoSwitch", "video", "摄像开关"),
    ("shootSwitch", "shoot", "拍照开关"),
)

# alarmId 中分隔"事件标识"与"时间戳"的分隔符（沿用 prod_2gaf.py 的约定）。
_ALARM_ID_SEPARATOR = "::"


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


def _enum_label(
    field: Mapping[str, Any] | None,
    value: Any,
) -> str | None:
    """Resolve one reported value to its Profile enum label.

    ``alarmEvent`` fields are declared as ``0/1`` enums whose ``descCh``
    already carries the user-facing wording ("有告警" / "无告警"), so the
    label is read from the Profile rather than hardcoded here.
    """

    if field is None:
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


def _reported_at(device: DeviceContext, sid: str) -> datetime | None:
    """Return when service ``sid`` last reported, tolerating ns-without-dot.

    为什么不用 ``device.service_updated_at()`` 直接了事：
    该接口内部走 ``parse_remote_timestamp``，后者只接受两种形态——
    整秒 ``%Y%m%dT%H%M%S``，或**带小数点**的 ``...%H%M%S.%f``。
    而实时 MQTT 推送携带的时间戳是**不带小数点**的 9 位纳秒
    （形如 ``20260914T222103156Z``），会被判为不可解析而返回 None。
    该现象在 KW02 / KW38 / KW4X / KW59 的文件头均有记录。

    对"多久之前触发"这个需求而言，None 恰好出现在**告警刚发生**的时刻，
    正是最需要的时刻——直接调 service_updated_at 会得到 unknown。

    因此这里补一条兜底：遇 ``YYYYMMDDTHHMMSS<多余数字>Z`` 时，
    取前 6 位多余数字当微秒。解析失败一律返回 None，**绝不猜时间**。
    """

    when = device.service_updated_at(sid)
    if when is not None:
        return when

    raw = getattr(device, "_timestamps", None)
    if not isinstance(raw, Mapping):
        return None
    value = raw.get(sid)
    if not isinstance(value, str) or not value.endswith("Z"):
        return None

    body = value[:-1]
    if "." in body or "T" not in body:
        return None
    whole, _, fraction = body.partition("T")
    if not whole.isdigit() or not fraction.isdigit() or len(fraction) <= 6:
        return None
    micros = (fraction[6:] + "000000")[:6]
    try:
        return datetime.strptime(
            f"{whole}T{fraction[:6]}.{micros}", "%Y%m%dT%H%M%S.%f"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _make_alarm_triggered_sensor(
    field: str,
    key: str,
    name: str,
) -> EntitySpec:
    """Report **when this alarm was last received**, as a ``timestamp`` sensor.

    语义是"最近一次收到该告警推送的时间"，**不是**"该告警正在发生的时长"。
    这一点很关键：设备从不推送清除值（见 ``_make_alarm_sensor``），
    所以字段会一直停在 1。若把时间理解成"已持续多久"，就会得出
    "有人已经在那里待了两小时"这种错误结论。

    为什么可以直接给时间（不再判断"当前是否触发"）：
    既然字段锁存，"当前是否触发"永远为真，判断等于没判断；
    而我们要表达的本来就是"最近一次告警是什么时候"——只要设备上报过
    告警（字段为 1），那个上报时刻就是答案。

    HA 对 ``device_class=timestamp`` 的传感器自动渲染相对时间（"3 分钟前"），
    这正是本需求要的展示形式。
    """

    def state(device: DeviceContext) -> Mapping[str, Any]:
        if _bool(device.value(_ALARM_SID, field)) is not True:
            # 从未上报过告警：没有"最近一次"可言。
            return {"native_value": None}
        return {"native_value": _reported_at(device, _ALARM_SID)}

    return EntitySpec(
        platform="sensor",
        key=f"{key}{_TRIGGERED_SUFFIX}",
        name=f"{name}（最近触发）",
        state=state,
        metadata={"device_class": "timestamp"},
    )


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


# ---------------------------------------------------------------------
# 告警事件解码
# ---------------------------------------------------------------------
def _alarm_event_decoder(
    device: DeviceContext,
    sid: str,
    data: Mapping[str, Any],
    timestamp: str | None,
) -> list[tuple[str, Mapping[str, Any]]]:
    """Turn one ``alarmEvent`` push into Home Assistant events.

    ``alarmEvent`` is a one-shot signal: the device pushes it when something
    is detected and never sends the cleared value.  The read-only sensors
    declared beside this decoder therefore only describe *what was last
    reported* and cannot drive an automation that must run on every
    detection -- a later detection that sets the same field produces no
    state change at all.

    This decoder supplies the missing half: each accepted push is reported as
    an event, so an automation can trigger on every occurrence and read
    ``alarm_id`` to tell them apart.
    """

    if sid != _ALARM_SID:
        return []

    alarm_id = data.get("alarmId")
    alarm_ref = str(alarm_id) if alarm_id is not None else None
    detected_at = None
    if isinstance(alarm_id, str) and _ALARM_ID_SEPARATOR in alarm_id:
        detected_at = alarm_id.rsplit(_ALARM_ID_SEPARATOR, 1)[-1] or None

    events: list[tuple[str, Mapping[str, Any]]] = []
    for field_name, event_type, _name, _device_class in _ALARM_FIELDS:
        # Any field the Profile declares as 0/1 may arrive as a bool, an int
        # or a numeric string, so ``_bool`` is used rather than a truthiness
        # test that would treat the string "0" as raised.
        if _bool(data.get(field_name)) is not True:
            continue
        # A single push can carry several raised fields, so every raised one
        # is reported; the shared alarm id keeps them recognisable as one
        # occurrence.
        events.append(
            (
                event_type,
                {
                    "alarm_id": alarm_ref,
                    "detected_at": detected_at,
                    "received_at": timestamp,
                    "camera": device.name,
                },
            )
        )
    return events


# ---------------------------------------------------------------------
# 实体构建
# ---------------------------------------------------------------------
def _make_switch(
    context: DeviceContext,
    sid: str,
    key: str,
    name: str,
) -> EntitySpec | None:
    """One switch backed by an RW ``on`` characteristic."""

    field = _field(context.profile, sid, "on")
    if not _is_writable(field):
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


def _make_alarm_sensor(
    sid: str,
    field_name: str,
    key: str,
    name: str,
    profile: Mapping[str, Any] | None,
) -> EntitySpec:
    """One read-only alarm **sensor** showing the Profile enum label.

    为什么不是 binary_sensor（真机实测结论）：

    本机的告警字段是**一次性信号**。Profile 的 enumList 定义了
    ``1=有告警 / 0=无告警`` 两个取值，但设备只在检测到目标时推送 ``1``，
    **从不推送 ``0``**（真机观察：触发后一直显示已触发，不会自行恢复）。

    若做成 binary_sensor，HA 会把它当作"实时电平"，于是首次触发后
    永久停在 on：
      * 界面长期显示"有人"，与事实不符；
      * 后续同类告警因为状态没变化（有告警→有告警）而**无法再次触发
        自动化**，静默失效。

    因此按仓库既有摄像头适配器 ``prod_2gaf.py`` 的做法，改为显示
    Profile 枚举文案的 sensor（"有告警 / 无告警"）。它诚实表达
    "最近一次上报的告警状态"，而不是声称"此刻正在告警"。

    需要"每次触发都响应"的自动化，请使用 event 实体 告警事件。
    """

    field_def = _field(profile, sid, field_name)

    def state(device: DeviceContext) -> Mapping[str, Any]:
        raw = device.value(sid, field_name)
        if raw is None:
            return {"native_value": None}
        label = _enum_label(field_def, raw)
        if label is not None:
            return {"native_value": label}
        number = _int(raw)
        return {"native_value": number if number is not None else raw}

    return EntitySpec(
        platform="sensor",
        key=key,
        name=name,
        state=state,
    )


def _make_online_sensor() -> EntitySpec:
    """在线状态——由集成侧的可用性直接合成，不依赖任何 Profile 字段。

    与上游 ``prod_2gaf.py`` 的 ``_online_spec`` 一致：本机是 **4G 版**，
    断网/断流时最需要这个实体，而 Profile 里没有对应的在线字段。
    """

    def state(device: DeviceContext) -> Mapping[str, Any]:
        return {"is_on": bool(device.available)}

    return EntitySpec(
        platform="binary_sensor",
        key="online",
        name="在线状态",
        state=state,
        metadata={"device_class": "connectivity"},
    )


def _make_alarm_event() -> EntitySpec:
    """One ``event`` entity firing on every accepted alarm push."""

    return EntitySpec(
        platform="event",
        key="alarm",
        name="告警事件",
        state=lambda device: {},
        metadata={
            "event_types": [event_type for _, event_type, _, _ in _ALARM_FIELDS]
        },
        event_decoder=_alarm_event_decoder,
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


class Product2LC9Adapter:
    """Keep all 2LC9 entity and command choices in this file."""

    prod_id = "2LC9"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = [_make_online_sensor()]

        # --- 控制开关 -------------------------------------------------
        for sid, key, name in _SWITCH_SPECS:
            if not context.has_service(sid):
                continue
            spec = _make_switch(context, sid, key, name)
            if spec is not None:
                entities.append(spec)

        # --- 告警：只读 sensor（最近状态） + event（每次触发） --------
        # 不做 binary_sensor：设备从不推送清除值，会永久锁存。
        # 详见 _make_alarm_sensor 的说明。
        if context.has_service(_ALARM_SID):
            for field_name, _event_type, name, _device_class in _ALARM_FIELDS:
                field = _field(profile, _ALARM_SID, field_name)
                if field is None:
                    continue
                entities.append(
                    _make_alarm_sensor(
                        _ALARM_SID,
                        field_name,
                        f"{field_name}",
                        name,
                        profile,
                    )
                )
                entities.append(
                    _make_alarm_triggered_sensor(
                        field_name, f"{field_name}", name
                    )
                )
            entities.append(_make_alarm_event())

        # --- 诊断实体（默认关闭，见文件头"为什么诊断实体默认不创建"） ---
        # 这些实体在真机上**全部为 unknown**：设备不上报 lteService /
        # netInfo / update 的读取字段，也没有可用的读取路径。
        # 长期 unknown 的实体只会污染界面，因此默认不创建。
        # 把下面的开关改为 True 即可恢复（真机确认上报后）。
        if _ENABLE_DIAGNOSTIC_ENTITIES:
            entities.extend(_make_diagnostic_entities(context, profile))

        return tuple(entities)


def _make_diagnostic_entities(
    context: DeviceContext,
    profile: Mapping[str, Any] | None,
) -> tuple[EntitySpec, ...]:
    """Build the lteService / netInfo / firmware diagnostic entities.

    默认不创建（见 ``_ENABLE_DIAGNOSTIC_ENTITIES``）。代码保留是为了：
    若日后在真机上确认这些字段**确实会上报**，把开关打开即可恢复，
    无需重新实现。取值逻辑未做任何猜测，仍是按 Profile 的字段读取。
    """

    entities: list[EntitySpec] = []

    if context.has_service("lteService"):
        # Profile 未给出 attrName/unit，按原始数值输出并标注为诊断。
        for field_name, key, name in (
            ("expireDays", "lte_expire_days", "4G 流量剩余天数"),
            ("expireStatus", "lte_expire_status", "4G 流量状态"),
        ):
            if _field(profile, "lteService", field_name) is None:
                continue
            entities.append(
                _make_sensor(
                    "lteService", field_name, key, name,
                    state_class="measurement",
                    entity_category="diagnostic",
                    decode=_int,
                )
            )

    if context.has_service("netInfo"):
        entities.append(
            _make_sensor(
                "netInfo", "intensity", "wifi_signal_level",
                "Wi-Fi 信号格数",
                state_class="measurement", entity_category="diagnostic",
                decode=lambda value: _SIGNAL_LEVELS.get(_int(value) or -1),
            )
        )
        entities.append(
            _make_sensor(
                "netInfo", "RSSI", "wifi_rssi", "Wi-Fi 信号强度",
                unit="dB", device_class="signal_strength",
                state_class="measurement", entity_category="diagnostic",
                decode=_int,
            )
        )
        entities.append(
            _make_sensor(
                "netInfo", "IP", "ip_address", "IP 地址",
                entity_category="diagnostic", decode=_text,
            )
        )
        entities.append(
            _make_sensor(
                "netInfo", "SSID", "wifi_ssid", "Wi-Fi SSID",
                entity_category="diagnostic", decode=_text,
            )
        )
        entities.append(
            _make_sensor(
                "netInfo", "BSSID", "bssid", "路由器 BSSID",
                entity_category="diagnostic", decode=_text,
            )
        )

    if context.has_service("update"):
        entities.append(
            _make_sensor(
                "update", "version", "firmware_version", "固件版本",
                entity_category="diagnostic", decode=_text,
            )
        )

    return tuple(entities)


ADAPTER = Product2LC9Adapter()
