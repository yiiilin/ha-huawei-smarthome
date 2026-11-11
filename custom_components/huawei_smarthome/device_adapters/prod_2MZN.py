"""User-contributed protocol for Huawei product 2MZN (小豚当家室外摄像头T5 3K双摄版).

产品: 小豚当家室外摄像头 T5 3K 双摄版
厂商: 智多豚 (dophigo)
型号: XT-H40 (deviceTypeId 008, 网络摄像头, WiFi, uiType PLUGIN)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
不跨产品复用，不做未经 Profile/真机证据支持的推断。

=====================================================================
Profile 服务一览（含未映射项）
=====================================================================
  switch.on              bool   RW  1=开 0=关  摄像头开关(0=待机)  -> camera_switch
  videoSwitch.on         bool   RW  1=开 0=关  摄像/录像开关       -> video_switch
  shootSwitch.on         bool   RW  1=开 0=关  拍照(抓拍)开关      -> shoot_switch

  以下告警字段全部做成**只读 sensor**（显示 Profile 文案）+ 同名
  「（最近触发）」时间 sensor。原因见下方"告警实体形态"专节。
  （device_class 列仅作分类参考，不再用于 binary_sensor。）
  alarmEvent.alarm         bool R 1=有告警 0=无告警               -> alarm
  alarmEvent.videoAlarm    bool R 视频检测                        -> video_alarm
  alarmEvent.humanBodyAlarm bool R 人形检测                       -> human_body_alarm
  alarmEvent.babyCryAlarm  bool R 婴儿哭声                        -> baby_cry_alarm
  alarmEvent.auxiliaryFireAlarm bool R 辅助火焰检测               -> fire_alarm
  alarmEvent.carAlarm      bool R 车辆检测                        -> vehicle_alarm
  alarmEvent.audioAlarm    bool R 声音检测                        -> audio_alarm
  alarmEvent.animalAlarm   bool R 动物检测                        -> animal_alarm
  alarmEvent.alarmId       string RW 事件抓拍ID                   参见下方"alarmId 怎么用"
  alarmEvent.id            string RW 标识                         不映射（无用户语义）

  另有一个 event 实体 告警事件（key=alarm_event），每次告警推送触发一次。

  familiarFaceAlarm.alarm              bool R 熟悉人脸告警        -> familiar_face_alarm
  familiarFaceAlarm.familiarFaceAlarmEvent bool R 告警判断        不映射（与 alarm 重复表达同一事件）
  familiarFaceAlarm.faceName           string R 熟悉人脸名称      -> 作为事件属性
  familiarFaceAlarm.alarmId            string RW 抓拍ID           参见下方"alarmId 怎么用"

  strangerFaceAlarm.alarm                 bool R 陌生人脸告警     -> stranger_face_alarm
  strangerFaceAlarm.strangerFaceAlarmEvent bool R 告警判断        不映射（同上）
  strangerFaceAlarm.alarmId               string RW 抓拍ID        参见下方"alarmId 怎么用"

  netInfo.intensity      enum   R  20/40/60/80/100 = 0~4 格信号   默认不创建，见下节
  netInfo.RSSI           int    R  -100..0 dBm                    默认不创建，见下节
  netInfo.IP             string R  设备 IP                        默认不创建，见下节
  netInfo.BSSID          string R  路由器 MAC                     默认不创建，见下节
  netInfo.SSID           string RW 路由器 SSID                    默认不创建，见下节

  update.version         string R  固件版本                       默认不创建，见下节
  update.progress        int    R  升级进度 %                     不映射（仅升级过程中有意义）
  update.status          enum   R  0..4 升级状态                  不映射
  update.autoUpdateOn    int    RW 自动升级开关                   不映射（低频运维开关）
  update.bootTime / action / centercapability / matchstatus /
  introduction / checkmatch / on                                  不映射（中枢 OTA 流程，无用户价值）

  visitPoint1..6.move    bool   RW 1=移到该预置点 0=无动作        -> 6 个 button
  visitPoint1..6.enable  bool   RW 1=已配置 0=未配置              -> 作为按钮可用性判断
  visitPoint1..6.name    string RW 预置点名称                     -> 作为按钮名称
  visitPoint1..6.id      string RW 预置点ID                       不映射（插件内部标识）

  logReport.*            4 个字段  R/W 故障上报                  不映射（内部日志通道，无用户价值）
  pushStatus.status      int    W(仅P) 推送配置                  不映射（无 R 权限，读不到）

=====================================================================
alarmId 怎么用（不取图，但要能区分"哪一次"）
=====================================================================
Profile 对 alarmId 的描述是：设备触发抓拍/录像后上报该 ID，
**该 ID 会随后续 PUSH 消息携带给华为智慧生活 App 插件**，
由插件再向厂商云端换取图片/视频 URL。

本集成不消费华为的 PUSH 通道，也没有该厂商的云端取图接口，所以
**不打算用它取图**，也不会把它单独做成 sensor（那只是一串无意义 ID）。

但它的格式是 ``<摄像头 id>::<epoch 毫秒>``：前半每次相同、后半每次不同。
**后半正是"这是哪一次触发"的判别依据**，因此本适配器把它拆出来作为
event 实体的 ``detected_at`` 属性（并连同完整的 ``alarm_id`` 一起给出），
让自动化能区分同一天里两次人形告警。分隔符约定与 ``prod_2gaf.py`` /
``prod_2LC9.py`` 保持一致。

同理，本集成**没有 camera 平台**（见 const.PLATFORMS），
无法提供实时画面；摄像头接入以开关 + 告警只读传感器形式呈现，
这与仓库既有摄像头适配器（prod_2gaf.py / prod_2LOY.py）保持一致。

=====================================================================
为什么不映射 visitPoint*.id
=====================================================================
该 ID 由 App 插件自行分配，仅用于匹配 App 内的 IFTTT 规则。
集成侧按 sid（visitPoint1..6）区分预置点即可，无需该值。

=====================================================================
告警实体形态（真机实测后从 binary_sensor 改为 sensor）
=====================================================================
**真机实测结论：告警字段是一次性信号，不会自行恢复。**

现象（用户实测）：触发后一直显示"已触发"，从不回到 off。

原因：Profile 的 enumList 虽然定义了 ``1=开 / 0=关``，但设备只在检测到
目标时推送 ``1``，**从不推送 ``0``**。也就是说这些字段是"事件通知"，
不是"实时电平"。

若做成 binary_sensor，HA 会按实时电平处理，于是首次触发后永久停在 on：
  * 界面长期显示"有人"，与事实不符；
  * 后续同类告警因为状态没变化（on→on）而**无法再次触发自动化**，
    静默失效——这比没有实体更糟。

因此本适配器按仓库既有摄像头适配器 ``prod_2gaf.py`` 的做法，
把告警字段做成**只读 sensor**，显示 Profile 枚举文案
（本机为"开 / 关"）。它诚实表达"最近一次上报的告警状态"，
而不是声称"此刻正在告警"。

配合的两个实体：
  * ``<告警>（最近触发）``：sensor，device_class=timestamp，
    表示"最近一次收到该告警的时间"，HA 渲染为"3 分钟前"。
    注意语义——它不是"已持续多久"。
  * ``告警事件``：event 实体，每次被接受的告警推送触发一次。
    **需要"每次触发都响应"的自动化请用这个**，因为 sensor 在同类
    告警重复发生时不会产生状态变化。

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
（``20260914T222156103Z``），会被判为不可解析 → 返回 None。
而 None 恰好出现在告警刚发生的时刻——正是最需要时间的时刻。
故本文件用 ``_reported_at()`` 对该形态补一条解析兜底。
参考：KW02 / KW38 / KW4X / KW59 的文件头都记录了同一现象。

已知局限（未实测，需真机确认）：
  * 若设备的 ts 语义是"服务级最后写入"而非"字段级变化时刻"，
    则同一服务内其他字段的上报可能把时间推后。此点无法由 Profile 判定。
    真机验证建议：触发人形检测后等 1~2 分钟，再触发另一个告警通道，
    看两个通道的时间是否会互相影响。
  * 时间取自设备上报的 UTC ts，与 HA 主机时钟无关；显示按本地时区换算。

=====================================================================
为什么诊断实体默认不创建
=====================================================================
真机实测：``netInfo``（信号格数/RSSI/IP/SSID/BSSID）与 ``update.version``
（固件版本）这 6 个实体**全部长期为 unknown** —— 设备根本不上报这些
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
[已实测] 预置点按钮的报文类型必须为数值 1，不能是字符串 "1"。
    现象（修复前）：按下"预置点2"按钮报
        SmartHome command rejected: sid=visitPoint2 errcode=16001
    原因：Profile 的 visitPoint*.move 虽然带 enumList（enumVal 为字符串
        "1"），但 characteristicType 是 bool，真机/云端只接受数值。
        修复前直接把枚举标签字符串 "1" 当报文值发出，被云端拒绝。
    修复：新增 _coerce_payload_value()，按 characteristicType 做数值化
        （bool/int/integer/enum → 数字），与 prod_2g4n.py 的处理一致。
        同一处理也应用到 switch / videoSwitch / shootSwitch 的 on 字段。
    参考：仓库内所有已接入的摄像头适配器（22Q4 / 2C60 / 2NPA / 2poo）
        均发送整数 1。

[已实测] 告警字段是一次性信号，设备只推 1 不推 0，**不会自行恢复**。
    现象：触发后一直显示"已触发"。据此把告警从 binary_sensor 改为
    只读 sensor + "最近触发"时间 + event 实体（见上方专节）。

=====================================================================
已确认与待确认项
=====================================================================
[已实测] 实体创建与状态读取：**通过**。摄像头/摄像/拍照开关状态、
    8 项告警检测、预置点按钮与诊断实体的显示均已确认。
[已实测] 控制命令：**通过**。switch / videoSwitch / shootSwitch 的
    on 写入，以及 visitPoint*.move（报文类型修复后）均已确认生效。
[ ] 预置点 move 的自复位行为：Profile 说 move 默认 0、=1 时开始移动。
    本适配器按"一次性动作"处理（写成 button），
    若真机上 move 写入 1 后会保持 1，则该按钮会重复触发，
    此时应改为 switch + turn_off 复位，需真机验证后调整。
[ ] 预置点 enable 的语义：按 Profile 解读为"是否已配置该预置点"。
    命令层未把 enable 作为前置校验（避免误判导致按钮不可用），
    仅在 UI 上作为可用性参考。若真机要求先 enable=1 才能 move，
    需要在此文件补充前置写入步骤。
    注意：若 16001 在修复报文类型后仍然出现，则很可能是"该预置点
    未配置（enable=0）"导致的业务拒绝，需据此调整。
[已实测] 告警类字段（humanBodyAlarm 等）的复位行为：**不会自行恢复**。
    设备只推 1 不推 0，因此不再映射为 binary_sensor 的瞬时状态，
    改为只读 sensor（显示 Profile 文案）+ 最近触发时间 + event。
[ ] 「最近触发」传感器未实测。需确认为相对时间（而不是 unknown）；
    若是 unknown，说明设备 ts 格式与本文件的兜底解析不符，
    需按真机抓到的实际格式调整 _reported_at()。
[ ] 同一服务内其他字段上报是否会推后「最近触发」时间（见上方"已知局限"）。
[ ] event 实体的 event_types 是否与设备实际上报的字段组合一致
    （一次推送可能同时置位多个字段，届时会同时触发多个事件类型）。
[已实测] netInfo（信号格数/RSSI/IP/SSID/BSSID）与 update.version 全部为
    unknown：设备不上报这些读取字段。已按实测结果默认不创建对应实体
    （见上方"为什么诊断实体默认不创建"）。若日后确认会上报，
    把 _ENABLE_DIAGNOSTIC_ENTITIES 改为 True 即可恢复。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

# visitPoint1..6：Profile 固定提供 6 个预置点服务。
_VISIT_POINTS = (1, 2, 3, 4, 5, 6)

# 触发时间传感器的 key 后缀：<告警 key>_last_triggered
_TRIGGERED_SUFFIX = "_last_triggered"

# 诊断实体（netInfo / update）总开关。
# 真机实测：这些实体全部为 unknown，设备不上报对应字段。
# 默认关闭以免污染界面；若日后确认真机会上报，改为 True 即可恢复。
_ENABLE_DIAGNOSTIC_ENTITIES = False

# netInfo.intensity：Profile 把信号格数编码为 20/40/60/80/100。
_SIGNAL_LEVELS = {
    20: 0,
    40: 1,
    60: 2,
    80: 3,
    100: 4,
}

# alarmEvent 中所有 report=1 的布尔告警字段。
# (characteristicName, 实体 key, 中文名, device_class)
# device_class 保留在表内仅供分类参考：这些字段现在做成 sensor（不设
# device_class），因为设备从不推送清除值，binary_sensor 会永久锁存。
_ALARM_FIELDS = (
    ("videoAlarm", "video_alarm", "视频检测", "motion"),
    ("humanBodyAlarm", "human_body_alarm", "人形检测", "motion"),
    ("babyCryAlarm", "baby_cry_alarm", "婴儿哭声", "sound"),
    ("auxiliaryFireAlarm", "fire_alarm", "辅助火焰检测", "smoke"),
    ("carAlarm", "vehicle_alarm", "车辆检测", "motion"),
    ("audioAlarm", "audio_alarm", "声音检测", "sound"),
    ("animalAlarm", "animal_alarm", "动物检测", "motion"),
)

# event 实体使用的事件类型（HA 要求稳定的 snake_case token）。
# (characteristicName, event_type)
# alarmId 里分隔「事件标识」与「时刻」的分隔符（沿用 prod_2gaf.py 的约定）
_ALARM_ID_SEPARATOR = "::"

_ALARM_EVENT_FIELDS = (
    ("videoAlarm", "video"),
    ("humanBodyAlarm", "human_body"),
    ("babyCryAlarm", "baby_cry"),
    ("auxiliaryFireAlarm", "fire"),
    ("carAlarm", "vehicle"),
    ("audioAlarm", "audio"),
    ("animalAlarm", "animal"),
)


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


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _text(value: Any) -> str | None:
    """Return a non-empty string, otherwise ``None``."""

    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _reported_at(device: DeviceContext, sid: str) -> datetime | None:
    """Return when service ``sid`` last reported, tolerating ns-without-dot.

    为什么不用 ``device.service_updated_at()`` 直接了事：
    该接口内部走 ``parse_remote_timestamp``，后者只接受两种形态——
    ``%Y%m%dT%H%M%S``（整秒）和**带小数点**的 ``...%H%M%S.%f``。
    而实时 MQTT 推送携带的时间戳是**不带小数点**的 9 位纳秒
    （形如 ``20260914T222103156Z``），会被判为不可解析而返回 None
    （KW02/KW38/KW4X 的文件头都记录了同一现象）。

    对"多久之前触发"这个需求而言，None 恰好出现在**告警刚发生**的时刻，
    正是最需要的时刻——直接调 service_updated_at 会得到 unknown。

    因此这里补一条兜底：遇 ``YYYYMMDDTHHMMSS<多余数字>Z`` 时，
    取前 6 位多余数字当微秒（保留毫秒级排序即可，秒级已足够表达"x 分钟前"）。
    解析失败一律返回 None，**绝不猜时间**。
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
    # 仅处理无小数点的形态；带小数点的已由 service_updated_at 覆盖。
    if "." in body or "T" not in body:
        return None
    whole, _, fraction = body.partition("T")
    if not whole.isdigit() or not fraction.isdigit() or len(fraction) <= 6:
        return None
    # 例：whole=20260914, fraction=222103156 -> 22:21:03.156000
    micros = (fraction[6:] + "000000")[:6]
    try:
        return datetime.strptime(
            f"{whole}T{fraction[:6]}.{micros}", "%Y%m%dT%H%M%S.%f"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _make_alarm_triggered_sensor(
    sid: str,
    field: str,
    key: str,
    name: str,
) -> EntitySpec:
    """Report **when this alarm was last received**, as a ``timestamp`` sensor.

    语义是"最近一次收到该告警推送的时间"，**不是**"该告警正在发生的时长"。
    这一点很关键：设备从不推送清除值（见 ``_make_alarm_sensor`` 的说明），
    所以字段会一直停在 1。若把时间理解成"已持续多久"，就会得出
    "有人已经在那里待了两小时"这种错误结论。

    为什么可以直接给时间（不再判断"当前是否触发"）：
    既然字段锁存，"当前是否触发"永远为真，判断等于没判断；
    而我们要表达的本来就是"最近一次告警是什么时候"——只要设备上报过
    告警（字段为 1），那个上报时刻就是答案。

    HA 对 ``device_class=timestamp`` 的传感器会自动渲染成相对时间
    （"3 分钟前"），这正是本需求想要的展示。
    """

    def state(device: DeviceContext) -> Mapping[str, Any]:
        if _bool(device.value(sid, field)) is not True:
            # 从未上报过告警：没有"最近一次"可言。
            return {"native_value": None}
        return {"native_value": _reported_at(device, sid)}

    return EntitySpec(
        platform="sensor",
        key=f"{key}{_TRIGGERED_SUFFIX}",
        name=f"{name}（最近触发）",
        state=state,
        metadata={"device_class": "timestamp"},
    )


def _make_online_sensor() -> EntitySpec:
    """在线状态——由集成侧的可用性直接合成，不依赖任何 Profile 字段。

    与上游 ``prod_2gaf.py`` 的 ``_online_spec`` 一致：室外摄像头（尤其
    4G 版）断线时最需要这个实体，而 Profile 里没有对应的在线字段。
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
    """One ``event`` entity firing on every accepted alarm push.

    为什么同时需要 event 实体：
    告警 sensor 只表达"最近一次上报的状态"，设备从不推送清除值，
    因此后续同类告警不会产生状态变化（有告警→有告警），
    **无法再次驱动自动化**。event 实体补上这一半：每次被接受的推送
    都触发一次事件，自动化应基于它构建。
    """

    return EntitySpec(
        platform="event",
        key="alarm_event",
        name="告警事件",
        state=lambda device: {},
        metadata={
            "event_types": [event_type for _, event_type in _ALARM_EVENT_FIELDS]
        },
        event_decoder=_alarm_event_decoder,
    )


def _alarm_event_decoder(
    device: DeviceContext,
    sid: str,
    data: Mapping[str, Any],
    timestamp: str | None,
) -> list[tuple[str, Mapping[str, Any]]]:
    """Turn one alarm push into Home Assistant events.

    A single push can carry several raised fields, so every raised one is
    reported as its own event type.

    ``alarmId`` 形如 ``<摄像头 id>::<epoch 毫秒>``（约定沿用 ``prod_2gaf.py``
    / ``prod_2LC9.py``）。前半是设备标识、每次相同，**后半的 epoch 才是区分
    「这是哪一次触发」的部分**，故作为 ``detected_at`` 暴露。注意这只让事件
    可区分，**不等于**能拿到抓拍图——取图仍需华为 PUSH + 厂商云端接口。
    """

    def _identity(payload: Mapping[str, Any]) -> dict[str, Any]:
        alarm_id = payload.get("alarmId")
        detected_at = None
        if isinstance(alarm_id, str) and _ALARM_ID_SEPARATOR in alarm_id:
            detected_at = alarm_id.rsplit(_ALARM_ID_SEPARATOR, 1)[-1] or None
        return {
            "alarm_id": str(alarm_id) if alarm_id is not None else None,
            "detected_at": detected_at,
            "received_at": timestamp,
            "camera": device.name,
        }

    if sid in ("familiarFaceAlarm", "strangerFaceAlarm"):
        if _bool(data.get("alarm")) is not True:
            return []
        event_type = (
            "familiar_face" if sid == "familiarFaceAlarm" else "stranger_face"
        )
        attrs = _identity(data)
        face_name = _text(data.get("faceName"))
        if face_name is not None:
            attrs["face_name"] = face_name
        return [(event_type, attrs)]

    if sid != "alarmEvent":
        return []

    events: list[tuple[str, Mapping[str, Any]]] = []
    for field_name, event_type in _ALARM_EVENT_FIELDS:
        # Any field the Profile declares as 0/1 may arrive as a bool, an int
        # or a numeric string, so ``_bool`` is used rather than a truthiness
        # test that would treat the string "0" as raised.
        if _bool(data.get(field_name)) is not True:
            continue
        events.append((event_type, _identity(data)))
    return events


def _make_alarm_sensor(
    sid: str,
    field: str,
    key: str,
    name: str,
    profile: Mapping[str, Any] | None,
) -> EntitySpec:
    """把一路告警字段暴露为**只读 sensor**，显示 Profile 的枚举文案。

    为什么是 sensor 而不是 binary_sensor（真机实测结论）：

    2MZN 的告警字段是**一次性信号**。Profile 的 enumList 虽然定义了
    ``1=开 / 0=关`` 两个取值，但设备只在检测到目标时推送 ``1``，
    **从不推送 ``0``**（真机观察：触发后一直显示已触发，不会自行恢复）。

    若做成 binary_sensor，HA 会把它当作"实时电平"，于是首次触发后
    永久停在 on：
      * 界面长期显示"有人"，与事实不符；
      * 更糟的是后续同类告警因为状态没变化（on→on）而**无法再次触发
        自动化**，静默失效。

    因此按仓库既有摄像头适配器 ``prod_2gaf.py`` 的做法，改为显示
    Profile 枚举文案的 sensor（"有告警 / 无告警"）。它诚实表达
    "最近一次上报的告警状态"，而不是声称"此刻正在告警"。

    需要"每次触发都响应"的自动化，请使用 event 实体，而不是本 sensor。
    """

    field_def = _field(profile, sid, field)

    def state(device: DeviceContext) -> Mapping[str, Any]:
        raw = device.value(sid, field)
        if raw is None:
            return {"native_value": None}
        label = _enum_label(field_def, raw)
        if label is not None:
            return {"native_value": label}
        number = _number(raw)
        return {"native_value": number if number is not None else raw}

    return EntitySpec(
        platform="sensor",
        key=key,
        name=name,
        state=state,
    )


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


def _coerce_payload_value(value: Any, field: Mapping[str, Any] | None) -> Any:
    """Encode a command value using the Profile-declared characteristic type.

    2MZN 的 ``visitPoint*.move`` 虽然带 enumList，但 ``characteristicType``
    是 ``bool``，真机只接受**数值** 1。Profile 的 ``enumVal`` 是字符串
    ``"1"``，若原样发送会被云端拒绝：

        HuaweiCommandRejectedError: sid=visitPoint2 errcode=16001

    因此按 characteristicType 做数值化（与 prod_2g4n.py 的处理一致），
    bool/int/integer/enum 一律转成数字；string 及未知类型保持原值。
    """

    if not isinstance(field, Mapping):
        return value
    data_type = str(field.get("characteristicType") or "").casefold()
    if data_type in {"bool", "int", "integer", "enum"}:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return value
        return int(number) if number.is_integer() else number
    return value


def _enum_label(
    field: Mapping[str, Any] | None,
    value: Any,
) -> str | None:
    """Resolve one **reported** value to its Profile enum label。

    与 ``_profile_enum_value`` 的区别：后者是"写命令编码"（把我们要发的
    值按 characteristicType 数值化），本函数是"读状态解码"（把设备上报的
    值翻译成 Profile 的文案），方向相反，不要混用。

    descCh 优先（中文界面），回退 descEn。
    """

    if not isinstance(field, Mapping):
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


def _profile_enum_value(
    field: Mapping[str, Any] | None,
    fallback: Any,
) -> Any:
    """Return the Profile-declared enum value matching ``fallback``.

    按 characteristicType 编码后返回，保证发出的报文类型与 Profile 一致。
    """

    raw: Any = fallback
    if isinstance(field, Mapping):
        for option in field.get("enumList", ()):
            if not isinstance(option, Mapping):
                continue
            candidate = option.get("enumVal")
            if candidate is not None and str(candidate) == str(fallback):
                raw = candidate
                break
    return _coerce_payload_value(raw, field)


def _alarm_state(context: DeviceContext) -> Mapping[str, Any]:
    """Expose the aggregated alarm flag plus any capturable metadata.

    注意：与各分路告警一样，这个字段同样是**一次性信号**（只推 1 不推 0），
    因此这里用 sensor 呈现 Profile 文案，而不是 binary_sensor。
    """

    attributes: dict[str, Any] = {}
    face_name = _text(context.value("familiarFaceAlarm", "faceName"))
    if face_name is not None:
        # Only meaningful while a familiar-face alarm is present.
        if _bool(context.value("familiarFaceAlarm", "alarm")) is True:
            attributes["face_name"] = face_name
    return {
        "is_on": _bool(context.value("alarmEvent", "alarm")),
        "extra_state_attributes": attributes or None,
    }


def _make_visit_point_button(
    context: DeviceContext,
    index: int,
) -> EntitySpec:
    """One 预置点 action button writing ``visitPointN.move = 1``."""

    sid = f"visitPoint{index}"
    field = _field(context.profile, sid, "move")
    # Profile 声明 move 的枚举 1=移到该预置点。优先取 Profile 的枚举值，
    # 字段缺失时才回退到 1（与 prod_2g4n.py 的处理方式一致）。
    move_value = _profile_enum_value(field, "1")

    async def move(device: DeviceContext, _data: Mapping[str, Any]) -> None:
        await device.async_send_service(sid, {"move": move_value})

    def availability(device: DeviceContext) -> bool:
        # enable=1 表示用户已配置该预置点；未配置时按钮仍可见但不可用。
        if not device.available:
            return False
        return _bool(device.value(sid, "enable")) is not False

    def state(device: DeviceContext) -> Mapping[str, Any]:
        # button 平台不使用 state 的取值，只要求可调用；
        # 预置点名称与配置状态通过 extra_state_attributes 呈现。
        name = _text(device.value(sid, "name"))
        enabled = _bool(device.value(sid, "enable"))
        attributes: dict[str, Any] = {}
        if name is not None:
            attributes["preset_name"] = name
        if enabled is not None:
            attributes["configured"] = enabled
        return {"extra_state_attributes": attributes or None}

    return EntitySpec(
        platform="button",
        key=f"visit_point_{index}",
        name=f"预置点{index}",
        state=state,
        actions={"press": move},
        availability=availability,
    )


def _signal_level(context: DeviceContext) -> int | None:
    """Map the Profile's 20/40/60/80/100 encoding to a 0..4 level."""

    value = _number(context.value("netInfo", "intensity"))
    if value is None:
        return None
    return _SIGNAL_LEVELS.get(int(value))


def _make_switch(
    context: DeviceContext,
    sid: str,
    key: str,
    name: str,
) -> EntitySpec:
    # on 字段同样是 bool + enumList，取值经 Profile 类型编码，
    # 避免把枚举标签字符串直接当报文值发出。
    field = _field(context.profile, sid, "on")
    on_value = _profile_enum_value(field, 1)
    off_value = _profile_enum_value(field, 0)

    def state(device: DeviceContext) -> Mapping[str, Any]:
        return {"is_on": _bool(device.value(sid, "on"))}

    async def turn_on(device: DeviceContext, _data: Mapping[str, Any]) -> None:
        await device.async_send_service(sid, {"on": on_value})

    async def turn_off(device: DeviceContext, _data: Mapping[str, Any]) -> None:
        await device.async_send_service(sid, {"on": off_value})

    return EntitySpec(
        platform="switch",
        key=key,
        name=name,
        state=state,
        actions={"turn_on": turn_on, "turn_off": turn_off},
    )


class Product2MZNAdapter:
    """Keep all 2MZN entity and command choices in this file."""

    prod_id = "2MZN"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = [_make_online_sensor()]

        # --- 主控开关 -------------------------------------------------
        if context.has_service("switch"):
            entities.append(
                _make_switch(context, "switch", "camera", "摄像头开关")
            )
        if context.has_service("videoSwitch"):
            entities.append(
                _make_switch(context, "videoSwitch", "video", "摄像开关")
            )
        if context.has_service("shootSwitch"):
            entities.append(
                _make_switch(context, "shootSwitch", "shoot", "拍照开关")
            )

        # --- 告警 -----------------------------------------------------
        # 全部做成只读 sensor（显示 Profile 文案）+ 最近触发时间，
        # 不做 binary_sensor：设备从不推送清除值，binary_sensor 会永久锁存。
        # 详见 _make_alarm_sensor 的说明。
        if context.has_service("alarmEvent"):
            entities.append(
                _make_alarm_sensor(
                    "alarmEvent",
                    "alarm",
                    "alarm",
                    "告警",
                    profile,
                )
            )
            entities.append(
                _make_alarm_triggered_sensor(
                    "alarmEvent", "alarm", "alarm", "告警"
                )
            )
            for field, key, name, _device_class in _ALARM_FIELDS:
                entities.append(
                    _make_alarm_sensor(
                        "alarmEvent",
                        field,
                        key,
                        name,
                        profile,
                    )
                )
                entities.append(
                    _make_alarm_triggered_sensor(
                        "alarmEvent", field, key, name
                    )
                )

        if context.has_service("familiarFaceAlarm"):
            entities.append(
                _make_alarm_sensor(
                    "familiarFaceAlarm",
                    "alarm",
                    "familiar_face_alarm",
                    "熟悉人脸告警",
                    profile,
                )
            )
            entities.append(
                _make_alarm_triggered_sensor(
                    "familiarFaceAlarm",
                    "alarm",
                    "familiar_face_alarm",
                    "熟悉人脸告警",
                )
            )
        if context.has_service("strangerFaceAlarm"):
            entities.append(
                _make_alarm_sensor(
                    "strangerFaceAlarm",
                    "alarm",
                    "stranger_face_alarm",
                    "陌生人脸告警",
                    profile,
                )
            )
            entities.append(
                _make_alarm_triggered_sensor(
                    "strangerFaceAlarm",
                    "alarm",
                    "stranger_face_alarm",
                    "陌生人脸告警",
                )
            )

        # 每次告警推送触发一次事件：自动化应基于 event 而不是上面的 sensor，
        # 因为 sensor 在同类告警重复发生时不会变化（见 _make_alarm_sensor）。
        if (
            context.has_service("alarmEvent")
            or context.has_service("familiarFaceAlarm")
            or context.has_service("strangerFaceAlarm")
        ):
            entities.append(_make_alarm_event())

        # --- 预置点（最多 6 个，按 Profile 实际提供的服务创建） --------
        for index in _VISIT_POINTS:
            if context.has_service(f"visitPoint{index}"):
                entities.append(_make_visit_point_button(context, index))

        # --- 诊断实体（默认关闭，见文件头"为什么诊断实体默认不创建"） ---
        # 这些实体在真机上**全部为 unknown**：设备不上报 netInfo / update 的
        # 读取字段，也没有可用的读取路径。长期 unknown 的实体只会污染界面，
        # 因此默认不创建。把下面的开关改为 True 即可恢复（真机确认上报后）。
        if _ENABLE_DIAGNOSTIC_ENTITIES:
            entities.extend(_make_diagnostic_entities(context))

        return tuple(entities)


def _make_diagnostic_entities(
    context: DeviceContext,
) -> tuple[EntitySpec, ...]:
    """Build the netInfo / firmware diagnostic entities.

    默认不创建（见 ``_ENABLE_DIAGNOSTIC_ENTITIES``）。代码保留是为了：
    若日后在真机上确认这些字段**确实会上报**，把开关打开即可恢复，
    无需重新实现。取值逻辑未做任何猜测，仍是按 Profile 的字段读取。
    """

    entities: list[EntitySpec] = []

    if context.has_service("netInfo"):
        entities.append(
            EntitySpec(
                platform="sensor",
                key="wifi_signal_level",
                name="Wi-Fi 信号格数",
                state=lambda device: {"native_value": _signal_level(device)},
                metadata={
                    "state_class": "measurement",
                    "entity_category": "diagnostic",
                },
            )
        )
        entities.append(
            EntitySpec(
                platform="sensor",
                key="wifi_rssi",
                name="Wi-Fi 信号强度",
                state=lambda device: {
                    "native_value": _number(device.value("netInfo", "RSSI"))
                },
                metadata={
                    "device_class": "signal_strength",
                    "unit": "dBm",
                    "state_class": "measurement",
                    "entity_category": "diagnostic",
                },
            )
        )
        entities.append(
            EntitySpec(
                platform="sensor",
                key="ip_address",
                name="IP 地址",
                state=lambda device: {
                    "native_value": _text(device.value("netInfo", "IP"))
                },
                metadata={"entity_category": "diagnostic"},
            )
        )
        entities.append(
            EntitySpec(
                platform="sensor",
                key="wifi_ssid",
                name="Wi-Fi SSID",
                state=lambda device: {
                    "native_value": _text(device.value("netInfo", "SSID"))
                },
                metadata={"entity_category": "diagnostic"},
            )
        )
        entities.append(
            EntitySpec(
                platform="sensor",
                key="bssid",
                name="路由器 BSSID",
                state=lambda device: {
                    "native_value": _text(device.value("netInfo", "BSSID"))
                },
                metadata={"entity_category": "diagnostic"},
            )
        )

    if context.has_service("update"):
        entities.append(
            EntitySpec(
                platform="sensor",
                key="firmware_version",
                name="固件版本",
                state=lambda device: {
                    "native_value": _text(device.value("update", "version"))
                },
                metadata={"entity_category": "diagnostic"},
            )
        )

    return tuple(entities)


ADAPTER = Product2MZNAdapter()
