"""User-contributed protocol for Huawei product KW5N (华为智能门锁 2 Ultra).

产品: 华为智能门锁 2 Ultra
厂商: 华为 (HUAWEI)
型号: AGS-X25 (deviceTypeId A0B, 智能门锁, WiFi, uiType PLUGIN / PART_ARKUIX)

本适配器遵循项目规范：单品协议行为全部硬编码在本文件内，
**不跨产品复用**。KW5N 与仓库既有 KW02/KW59/KW5L 等同系列门锁共享
lockStatus / event 的枚举空间，但本机 Profile 有明显差异（见下表），
故独立实现。

  差异点                 KW59 (E211)            KW5N (2 Ultra)
   --------------------  ---------------------  ----------------------
   lockStatus.status      RW                     RW（同）
   人脸识别               faces(只读列表)         securitySetting.faceIdentifySwitch
   布防 / 双重验证        无                     deploymentSwitch / doubleCheckSwitch
   身高/传感器开门          无                     enableSenserOpenSwitch
   猫眼设置               部分                   12 项（含逗留抓拍/实时视频/畸变校正/
                                                拍摄间隔/拍摄时长/呼叫有效期/侦测距离）
   告警事件订阅开关        无                     10 个 alarmEventSetting 开关
   音量设置               无                     volumeSetting（铃声/按键/语音/夜间）
   用户名单               users                  users（同）

=====================================================================
实体范围（只读适配器）
=====================================================================
本适配器**不向门锁发送任何控制指令**。共 11 个实体：

  # 基础状态
  binary_sensor  door                门（开 / 关）
  sensor         lock_status         门锁状态（文字）
  binary_sensor  low_battery         低电量告警

  # 电池电量（Profile 服务优先，回退未声明的 batteryManager）
  sensor         battery             门锁电量 %      doorBattery.level
  sensor         cat_eye_battery     猫眼电量 %      catEyeBattery.level

  # 门告警（逐码，便于按类型分别自动化）
  binary_sensor  door_not_closed     门未关告警            das=1（或 status=1 兜底）
  binary_sensor  door_ajar           门虚掩告警            das=2
  binary_sensor  door_unlocked_fault 门未锁(故障)告警       das=3
  binary_sensor  door_long_closed    长时间未开门           das=15
  binary_sensor  door_open_problem   门未关/虚掩/未锁告警   上述 1+2+3 的汇总

  # 事件（每次开锁 / 上锁 / 告警都 fire）
  event          lock_event          门锁事件（event_types: unlock/lock/alarm）

数据来源：
  lockStatus.status     int R 1=门未关异常上锁 2=已开锁 3=已上锁
                           4=已关门 6=已反锁        -> door + lock_status
                                                     + door_not_closed 的兜底
  lockAlarm.alarm       int R 1=故障 2=低电量 3=长期未上线
                                                    -> low_battery（低电量=2）
  doorBattery.level / catEyeBattery.level
                        int R -1~100    -> battery / cat_eye_battery
                           读不到时回退 batteryManager.lithiumBatteryLevel /
                           accumulatorBatteryLevel（Profile 未声明的服务）
  event.doorAlarmState  int R 1=门未关 2=门虚掩 3=门未锁(故障) 4=低电
                           15=长时间未开门 等 15 档 -> 逐码门告警

★ 关于"最近开锁 / 开门方向 / 最近告警"这几个实体：
  上一版曾按事件流做过，但真机反馈**始终为空**（事件链路拿不到数据），
  故**已全部移除**，避免在 PR 中留下永远不更新的实体。
  门锁事件 ``event.lock_event`` 仍保留——它是"每次触发都响应"的通道，
  自动化应基于它而不是基于状态实体。

★★ 事件数据靠 `device.service_state()` 读取 ★★
  `event` 服务的 serviceType 是 "event"，字段 report=None / perm=None——
  它属于**一次性推送**，由框架交给 ``event_decoder`` 转成 HA 事件，
  **不会写进 ``device.value()`` 的状态存储**。
  同时解码器每次推送也会自己落盘一份（``_EVENT_LATCH``），两条来源合并读取。
  注意线上字段是**短名**：``up``=userOperation、``das``=doorAlarmState、
  ``un``=userName、``et``=eventTime；本文件两者都读，谁有值用谁。

⚠️ 两套告警码不要混用：
  ``lockAlarm.alarm=2`` 是**低电量**，而 ``event.doorAlarmState=2`` 是
  **门虚掩告警**。它们是两个不同的枚举空间，故分别用
  ``_ALARM_LOW_BATTERY`` 与 ``_EVENT_ALARM_LOW_BATTERY`` 两个常量。

**告警语义**：门锁对每次事件只推一次、**从不推"已清除"**，因此这些
binary_sensor 表达的是"**该告警最近发生过**"，而不是"此刻正在发生"。
每次置位时属性里带 ``last_triggered``，要判断"多久之前"请看它。
这是设备行为决定的，不是适配器的取舍。需要"每次触发都响应"的自动化，
请用 ``event.lock_event``。

**刻意不暴露的项**（真机验证后收敛，理由见下）：
  * securitySetting 6 个开关、alarmEventSetting 10 开关 + 2 时长、
    catEyeSetting 5 开关 + 5 枚举、volumeSetting.nightModeSwitch
    —— 全部为控制项，已移除。
  * 诊断实体 —— 已移除：netInfo（信号/RSSI/IP/SSID/BSSID）与
    update.version 在真机上**全部长期为 unknown**，设备不上报；
    networkConnectState（连接状态 / 网络状态）也不再暴露。
  * temporaryCipher.periodicCiper（临时密码）与
    users/ciphers/faces/fingers/keyCards/watchs/walletKeys
    （7 类凭据名单）—— 不映射，见下方说明。
  * update.*（OTA 全流程）、supportedRing（能力位图）、各时段字段
    （startTime / endTime / messagePushTime）—— 不映射。

=====================================================================
为什么不提供 lock（上锁 / 开锁）实体
=====================================================================
本机 Profile 把 ``lockStatus.status`` 声明为 RW，因此适配器**有资格**
注册 lock / unlock 动作。但同系列门锁（KW02，见仓库既有适配器说明）
的固件行为是：**接受写入后回 errcode=0，然后立刻重新上报未改变的
状态**——即"假成功"。华为智慧生活 App 也**不提供**该系列的远程开锁。

早先的版本保留了一个 lock 实体、但把动作做成"显式拒绝"（按下报错、
不发报文）。作者真机实测后确认：**这个实体没有任何用处**——它既不
能上锁也不能开锁，只是给用户多了一个点了就报错的按钮。

因此**直接不注册 lock 实体**：设备页上没有上锁/解锁入口，锁的真实
状态由只读的 ``sensor.lock_status`` 表达。若日后确认该型号支持远程
开锁，再新增 lock 实体并实现真实写入。

=====================================================================
电池电量的两个来源
=====================================================================
Profile 声明 ``doorBattery.level`` / ``catEyeBattery.level``，但同系列机型
（AGS-E211 / KW02）实测**从不上报**这两个服务，真实电量走 Profile
**未声明**的 ``batteryManager``：
  ``lithiumBatteryLevel``     -> 锁体电量
  ``accumulatorBatteryLevel`` -> 猫眼电量
故本适配器**先读 Profile 服务、读不到再回退 batteryManager**；
两处都没有就显示 unknown，且 ``level=-1`` 是占位值、不是真实百分比。
（来源：上游 ``prod_KW59.py`` 的真机记录。）

=====================================================================
为什么不映射 temporaryCipher（临时密码）
=====================================================================
``temporaryCipher.periodicCiper`` 是 object（max 1024），properties 为
id / nm / ct / rd / st / et / act —— 其中 **ct 极可能是密码明文本身**，
且 object 里没有任何字段说明各 property 的具体格式（如 ct 的长度与
字符集、st/et 的时间格式）。

本集成没有"读-改-写"该结构的能力，而**临时密码是开门凭据**：
一旦格式构造错误，轻则失效，重则可能写入一个非预期的可用密码。
按失败关闭原则**不映射**。请在华为智慧生活 App 中管理临时密码。

=====================================================================
为什么不映射凭据名单（users/ciphers/faces/fingers/keyCards/watchs/walletKeys）
=====================================================================
这 7 个服务的 characteristic 都是 ``object``，承载"用户及其全部凭据"
的**名单**（每个元素含 uid / cp（凭据载荷）/ hj（指纹模板）等）。
它们是**凭据本体**而非状态：
  * cp / hj 是加密或模板载荷，在 HA 状态机里暴露没有用户价值；
  * 名单可能很长，逐条投影会产生大量实体并泄露家庭成员信息；
  * Profile 未声明这些 object 是单条还是数组、更新语义为何。
因此按失败关闭原则**不映射为实体**。门锁的凭据管理请使用官方 App。

=====================================================================
为什么不映射音量数值 / 时段 / 能力位图
=====================================================================
1. volumeSetting.ringVolume / keyVolume / voiceVolume / currentRing：
   Profile **只声明 int，没有 min/max/step，也没有枚举或单位**。
   取值域未知，做成 number 需要凭空假设范围（写错可能静音或爆响）。
   故不映射，仅映射语义明确的 nightModeSwitch（0/1 枚举）。
2. supportedRing：只读 int，是"支持的铃声音色"**位图/集合**，无枚举
   说明，原样输出不可读。
3. 各服务的 startTime / endTime（生效时段）与 messagePushTime
   （全天/自定义）：它们是**成组生效的时段配置**，单独暴露会产生
   "改了开始时间但结束时间没同步"这类不一致状态；且 Profile 未给
   时间串格式（maxLength 8/无说明）。按失败关闭原则不映射。
4. securitySetting.isAuth / auth：auth 是管理员密码载荷（max 400），
   isAuth 表示"是否要求携带该密码"。属于**凭据校验通道**，
   且与拒绝远程开锁的设计互相印证——不应暴露，故不映射。

=====================================================================
报文类型（沿用 2MZN 的实测教训）
=====================================================================
本机 Profile 的 ``enumList.enumVal`` 类型**不统一**：多数是 int
（如 lockStatus 的 1/2/3/4/6），但 ``update.action`` 是字符串
（"0"/"1"）。真机对 bool/enum/int 类字段只接受**数值**，直接把
枚举字符串当报文值发送会被云端拒绝（errcode=16001）。
因此本文件所有写命令都经 _coerce() 按 characteristicType 数值化。

注意本机 Profile **完全没有 permission 字段**，故不能用
_is_writable() 判断可写性，改为按 ``method`` 是否含 "W" 判断。

=====================================================================
真机实测：以下诊断字段**全部长期为 unknown** —— 设备不上报这些读取
字段，集成侧也没有别的读取路径可以拿到：
  * `netInfo`（Wi-Fi 信号格数 / RSSI / IP / SSID / BSSID）
  * `update.version`（固件版本）
  * `networkConnectState.state`（连接状态 / 网络状态）

它们已**从本文件移除**（此前是默认不创建、代码保留在
``_make_diagnostic_entities()``）。移除而非隐藏，是因为它们对用户
没有任何可读信息，保留代码只会让后续维护者以为"打开开关就能用"。

=====================================================================
真机实测记录
=====================================================================
验证环境：真实设备（华为智能门锁 2 Ultra / AGS-X25）+ 智慧生活 App 对照。

[已实测] 实体创建与状态读取：**通过**。
[已实测] `door`（门）/ `lock_status`（门锁状态文字）：**与 App 一致**，
    上锁 / 开锁 / 反锁 各测一次均正确。
[已实测] `low_battery`（低电量告警）：正常时为 off。
[已实测] `battery` / `cat_eye_battery`（门锁 / 猫眼电量）：**有真实读数**。
[已实测] `door_not_closed`（门未关告警）：**通过**——由
    `lockStatus.status=1`（门未关异常上锁）判定，不依赖事件推送。
[已实测·已删除] 以下几项在真机上**始终为空**，已从适配器中移除，
    以免 PR 里留下永远不更新的实体：
      * `last_unlock`（最近开锁）、`last_unlock_time`（最近开锁时间）
      * `open_direction`（开门方向）
      * `last_alarm`（最近门锁告警）
      * `event_raw`（诊断用，随上面几项一并撤掉）
    根因：`event` 服务是**一次性推送**（serviceType="event"，
    字段 report/perm 均为 None），本机始终没能取到它的数据；
    即使同时用 `service_state()` 与解码器落盘两条来源，也没能读到。

[ ] 仍然保留、但**未在真机确认**的 event 依赖项：
    `door_ajar`（das=2）、`door_unlocked_fault`（das=3）、
    `door_long_closed`（das=15）、`door_open_problem`（三者汇总）、
    `event.lock_event`（门锁事件）。它们与上面被删的几项共用同一条
    event 数据来源，**很可能同样不会更新**。若真机确认它们也是空的，
    应一并删除，让适配器只保留 lockStatus / lockAlarm 能支撑的实体。
[ ] `lockStatus` 的过渡值：同系列固件会上报 Profile 未声明的值
    （KW02 观察到 7）。本适配器沿用"保留最后一个已声明状态"的做法。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


_LOGGER = logging.getLogger(__name__)

# --- 服务/字段常量 ---------------------------------------------------
_LOCK_STATUS_SID = "lockStatus"
_LOCK_STATUS_FIELD = "status"

_NET_STATE_SID = "networkConnectState"
_NET_STATE_FIELD = "state"

_DOOR_BATTERY_SID = "doorBattery"
_CAT_EYE_BATTERY_SID = "catEyeBattery"
_BATTERY_LEVEL_FIELD = "level"

_LOCK_ALARM_SID = "lockAlarm"
_LOCK_ALARM_FIELD = "alarm"

_EVENT_SID = "event"

# --- lockStatus/status 取值（本机 Profile） --------------------------
_STATUS_DOOR_AJAR_LOCKED = 1  # 门未关异常上锁
_STATUS_UNLOCKED = 2  # 已开锁
_STATUS_LOCKED = 3  # 已上锁
_STATUS_DOOR_CLOSED = 4  # 已关门
_STATUS_DEADBOLTED = 6  # 已反锁

_LOCKED_STATUSES = frozenset(
    {_STATUS_DOOR_AJAR_LOCKED, _STATUS_LOCKED, _STATUS_DEADBOLTED}
)
_UNLOCKED_STATUSES = frozenset({_STATUS_UNLOCKED, _STATUS_DOOR_CLOSED})
# 门扇本身只在语义明确的状态下判定。
_DOOR_OPEN_STATUSES = frozenset({_STATUS_DOOR_AJAR_LOCKED, _STATUS_UNLOCKED})
_DOOR_CLOSED_STATUSES = frozenset(
    {_STATUS_LOCKED, _STATUS_DOOR_CLOSED, _STATUS_DEADBOLTED}
)
# Profile 声明的全部状态值；未声明的过渡值被挡下，保持上一个已知状态。
_DECLARED_STATUSES = _LOCKED_STATUSES | _UNLOCKED_STATUSES

# --- 网络连通状态 ----------------------------------------------------
_NET_STATE_ONLINE = 2  # 在线（1=休眠 不视为连通）

# --- 电量 ------------------------------------------------------------
# doorBattery/catEyeBattery 声明 min=-1，不是真实百分比。
_BATTERY_UNKNOWN = -1

# --- 告警 ------------------------------------------------------------
_ALARM_LOW_BATTERY = 2  # lockAlarm.alarm=2 低电量告警
# event.doorAlarmState 是**另一套**码：2 在那里是「门虚掩告警」，
# 低电在 event 里是 4。两者绝不能共用一个常量。
_EVENT_ALARM_LOW_BATTERY = 4
_NO_ALARM = "无告警"
# lockAlarm 一旦置位不会自动清除；超过该窗口的读数不再当作"当前"告警。
_ALARM_PULSE_WINDOW = timedelta(hours=12)

# --- 事件字段（本机 event 服务的扁平字段名） -------------------------
_EVENT_TYPE_FIELD = "eventType"          # 1=记录 2=告警
_EVENT_USER_NAME_FIELD = "userName"
_EVENT_OPERATION_FIELD = "userOperation"
_EVENT_DOOR_ALARM_FIELD = "doorAlarmState"
_EVENT_ALARM_ID_FIELD = "alarmId"
_EVENT_TIME_FIELD = "eventTime"

# --- 门告警只读传感器 -------------------------------------------------
# (key, 名称, event.das 触发码集合, lockStatus.status 兜底码集合)
#   * 主要来源是 event 推送的 das（1=门未关 2=门虚掩 3=门未锁(故障) 15=长时间未开门）
#   * `door_not_closed` 额外支持从 **lockStatus.status=1（门未关异常上锁）**
#     判定——那是一个持久服务，可作为 event 读不到时的兜底。
#   * status 码表：1=门未关异常上锁 2=已开锁 3=已上锁 4=已关门 6=已反锁
_DOOR_ALARM_SENSORS = (
    ("door_not_closed", "门未关告警", (1,), (1,)),
    ("door_ajar", "门虚掩告警", (2,), ()),
    ("door_unlocked_fault", "门未锁(故障)告警", (3,), ()),
    ("door_long_closed", "长时间未开门", (15,), ()),
)

_DOOR_GROUP_SENSORS = (
    (
        "door_open_problem",
        "门未关/虚掩/未锁告警",
        ("door_not_closed", "door_ajar", "door_unlocked_fault"),
    ),
)

_DOOR_GROUP_SENSORS = (
    (
        "door_open_problem",
        "门未关/虚掩/未锁告警",
        ("door_not_closed", "door_ajar", "door_unlocked_fault"),
    ),
)

_EVENT_RECORD = 1
_EVENT_ALARM = 2

# userOperation 中代表"开锁"的取值（本机 Profile 明文列出）。
# 0=指纹 1=密码 2=人脸 3=门卡 4=手表手环 5=钱包 6=临时密码 7=物理钥匙
_UNLOCK_OPERATIONS = frozenset({0, 1, 2, 3, 4, 5, 6, 7})
# 24=门内开锁，25=反锁，26=解除反锁
_OPERATION_INDOOR_UNLOCK = 24
_INDOOR_UNLOCK_OPERATIONS = frozenset({_OPERATION_INDOOR_UNLOCK})

# --- 需要暴露为 switch 的设置项 --------------------------------------
# (sid, 字段名, key, 名称)  —— 均为 0/1 枚举
_SECURITY_SWITCHES = (
    ("securitySetting", "deploymentSwitch", "deployment", "布防"),
    ("securitySetting", "doubleCheckSwitch", "double_check", "双重验证"),
    (
        "securitySetting",
        "passwordVerificationSwitch",
        "password_verification",
        "密码验证",
    ),
    ("securitySetting", "enableLockoutSwitch", "enable_lockout", "锁定开关"),
    ("securitySetting", "faceIdentifySwitch", "face_identify", "人脸识别"),
    (
        "securitySetting",
        "enableSenserOpenSwitch",
        "sensor_open",
        "传感器开门",
    ),
)

_ALARM_EVENT_SWITCHES = (
    ("doorNotCLoseSwitch", "alarm_door_not_close", "门未关告警"),
    ("unlockSwitch", "alarm_unlock", "开锁告警"),
    ("lockBrokenSwitch", "alarm_lock_broken", "锁被破坏告警"),
    ("forceUnlockedSwitch", "alarm_force_unlocked", "强制开锁告警"),
    ("alertModeUnlockedSwitch", "alarm_alert_mode", "布防告警"),
    ("lowBatterySwitch", "alarm_low_battery", "低电量告警推送"),
    ("takeSnapshotSwitch", "alarm_snapshot", "告警抓拍"),
    ("doorOpenSwitch", "alarm_door_open", "门开告警"),
    ("messagePushSwitch", "alarm_message_push", "消息推送"),
)

_CAT_EYE_SWITCHES = (
    ("staySnapshotSwitch", "cateye_stay_snapshot", "逗留抓拍"),
    ("liveVideoSwitch", "cateye_live_video", "实时视频"),
    (
        "distortionCorrectionSwitch",
        "cateye_distortion_correction",
        "畸变校正",
    ),
    ("takeSnapshotSwitch", "cateye_snapshot", "抓拍"),
    ("shimmerFullColorSwitch", "cateye_full_color", "全彩微光"),
)

# --- 需要暴露为 select 的枚举项 --------------------------------------
# (sid, 字段名, key, 名称, 顺序)
_SELECT_SPECS = (
    ("alarmEventSetting", "outAlarmTime", "alarm_out_time", "室外告警时长",
     ("0", "1", "2")),
    ("alarmEventSetting", "inAlarmTime", "alarm_in_time", "室内告警时长",
     ("0", "1", "2")),
    ("catEyeSetting", "stayDuration", "cateye_stay_duration", "逗留时长",
     tuple(str(v) for v in range(13))),
    ("catEyeSetting", "shootingInterval", "cateye_interval", "抓拍间隔",
     ("0", "1", "2", "3", "4", "5")),
    ("catEyeSetting", "shootingDuration", "cateye_duration", "抓拍时长",
     ("0", "1", "2")),
    ("catEyeSetting", "callValidPeriod", "cateye_call_period", "呼叫有效期",
     ("0", "1", "2", "3", "4")),
    ("catEyeSetting", "detectDistance", "cateye_distance", "侦测距离",
     ("0", "1", "2")),
)

# netInfo.intensity：Profile 声明 0~100 整数（非 20/40/60/80/100 编码）。
# 但同系列其它机型用 20/40/60/80/100 五档；本机是连续 0~100，
# 因此直接按原始数值输出，不做格数换算。


# ---------------------------------------------------------------------
# 取值解码
# ---------------------------------------------------------------------
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
    """本机 Profile 没有 permission 字段，故按 method 判断可写性。"""

    if not isinstance(field, Mapping):
        return False
    return "W" in str(field.get("method") or "")


def _coerce(value: Any, field: Mapping[str, Any] | None) -> Any:
    """按 Profile 声明的 characteristicType 数值化命令取值。

    本机 enumVal 类型不统一（多为 int，update.action 是 str），
    真机对 int/enum 类字段只接受数值，故统一数值化。
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
    """只按 enumVal 精确匹配，不做 descCh/descEn 文本回退。

    文本回退会在枚举文案互相包含时命中错误档位
    （2QWL 适配中踩过的真实 bug：descEn "110" 与另一档混淆）。
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


# ---------------------------------------------------------------------
# 拒绝动作（安全关键）
# ---------------------------------------------------------------------


def _status_reader() -> Callable[[DeviceContext], Any]:
    """返回一个"只接受已声明值"的 lockStatus 读取器。

    固件可能上报 Profile 未声明的过渡值（同系列观察到 7）。若直接照原样
    返回，一个过渡值会同时把「门 / 门锁状态 / door_not_closed 的兜底」
    一起变空。故只接受已声明的值，否则沿用上一个已知值。
    """

    cache: dict[str, Any] = {"status": None}

    def read(device: DeviceContext) -> Any:
        status = _int(device.value(_LOCK_STATUS_SID, _LOCK_STATUS_FIELD))
        if status in _DECLARED_STATUSES:
            cache["status"] = status
        return cache["status"]

    return read


def _make_select(
    context: DeviceContext,
    sid: str,
    field_name: str,
    key: str,
    name: str,
    order: tuple[str, ...] | None,
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


def _battery_spec(sid: str, key: str, name: str) -> EntitySpec:
    def state(device: DeviceContext) -> Mapping[str, Any]:
        value = _number(device.value(sid, _BATTERY_LEVEL_FIELD))
        # -1 是 Profile 的占位值，不是真实百分比。
        if value is not None and value <= _BATTERY_UNKNOWN:
            value = None
        return {"native_value": value}

    return EntitySpec(
        platform="sensor",
        key=key,
        name=name,
        state=state,
        metadata={
            "device_class": "battery",
            "state_class": "measurement",
            "unit": "%",
        },
    )






# ---------------------------------------------------------------------
# 事件读取（与 prod_KW59.py 同系列做法）
# ---------------------------------------------------------------------
# 关键事实（取自上游 prod_KW59.py，同厂同系列门锁，已在真机验证）：
#   * ``device.service_state(sid)`` 返回该服务**最后一次推送**的完整报文，
#     集成自己保存了它 —— 不需要我们另建缓存；
#   * 门锁在**线上用短字段名**推送，而 Profile 里叫长名：
#         userOperation -> "up"      doorAlarmState -> "das"
#         userName      -> "un"      eventTime      -> "et"
#     两者都读、谁有值用谁，这样换固件也不会失配。
#   * 一次推送只描述"刚刚发生的事"，所以"最近开锁"要用闭包缓存保住
#     最后一个**开锁**记录，避免后续关门类记录把它覆盖。
_WIRE_OPERATION = "up"
_WIRE_ALARM = "das"
_WIRE_USER = "un"
_WIRE_TIME = "et"

# 电池在部分同系列机型上走 Profile **未声明**的 batteryManager。
# 这里作为回退源：读不到就不显示，不做任何猜测。
_BATTERY_MANAGER_SID = "batteryManager"
_BATTERY_LPM_FIELD = "lpmStatus"
# batteryManager 上这两项对应锁体 / 猫眼的电量（同系列实测）
_LITHIUM_BATTERY_FIELD = "lithiumBatteryLevel"
_DRY_BATTERY_FIELD = "accumulatorBatteryLevel"
_LPM_ACTIVE = 1


# ---------------------------------------------------------------------
# 事件数据的两个来源（关键）
# ---------------------------------------------------------------------
# 为什么要有两条：
#   * 集成若提供 ``device.service_state(sid)``，它保存该服务**最后一次推送**；
#   * 但较早的集成版本没有这个方法 —— 此时只能靠**解码器自己落盘**。
# 真机反馈"最近开锁 / 开门方向全空"，说明单靠其中一条在本机拿不到数据，
# 因此这里同时读两条：解码器落盘的（本次推送，更新）优先，service_state 兜底。
_EVENT_LATCH: dict[str, dict[str, Any]] = {}


def _latch_key(device: DeviceContext) -> str:
    """一个稳定的 per-device 键，用于把推送按设备分开存放。"""

    for attr in ("unique_id", "entity_id", "device_id", "id", "name"):
        value = getattr(device, attr, None)
        if isinstance(value, str) and value:
            return value
    return "default"


def _service_state_record(device: DeviceContext) -> Mapping[str, Any]:
    """集成保存的最后一次推送（旧集成没有该方法时返回空）。"""

    getter = getattr(device, "service_state", None)
    if not callable(getter):
        return {}
    try:
        state = getter(_EVENT_SID)
    except Exception:  # noqa: BLE001 - a bad read must not break the entity
        return {}
    return dict(state) if isinstance(state, Mapping) else {}


def _event_record(device: DeviceContext) -> Mapping[str, Any]:
    """合并「集成保存的最后一次推送」与「解码器落盘的推送」。

    两条都是同一条推送的不同副本，字段应当一致；合并只是为了让**任意一条
    可用**时实体就能工作（合并顺序不影响结果）。
    """

    merged: dict[str, Any] = dict(_service_state_record(device))
    merged.update(_EVENT_LATCH.get(_latch_key(device), {}))
    return merged


def _remember_event(device: DeviceContext, data: Mapping[str, Any]) -> None:
    """解码器每收到一次推送就落盘，供只读实体读取。"""

    if len(_EVENT_LATCH) > 64:
        _EVENT_LATCH.clear()
    entry = _EVENT_LATCH.setdefault(_latch_key(device), {})
    for key, value in data.items():
        if value is not None:
            entry[key] = value


def _record_value(record: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            value = record.get(name)
            if value is not None:
                return value
    return None


def _record_operation(record: Mapping[str, Any]) -> int | None:
    """userOperation, as the wire calls it ``up``."""

    return _int(_record_value(record, _WIRE_OPERATION, _EVENT_OPERATION_FIELD))


def _record_alarm(record: Mapping[str, Any]) -> int | None:
    """doorAlarmState, as the wire calls it ``das``."""

    return _int(_record_value(record, _WIRE_ALARM, _EVENT_DOOR_ALARM_FIELD))


def _record_user(record: Mapping[str, Any]) -> str | None:
    return _text(_record_value(record, _WIRE_USER, _EVENT_USER_NAME_FIELD))


def _parse_stamp(value: Any) -> datetime | None:
    """Parse a SmartHome stamp such as ``20260915T232350Z`` (tolerating ns).

    ``service_updated_at`` / ``parse_remote_timestamp`` reject the fractional
    ns form the live MQTT push carries, so it is handled here.  Anything
    unparsable returns None -- never a guessed time.
    """

    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1]
    if "T" not in text:
        return None
    whole, _, fraction = text.partition("T")
    if not whole.isdigit():
        return None
    if "." in fraction:
        try:
            return datetime.strptime(
                f"{whole}T{fraction}", "%Y%m%dT%H%M%S.%f"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if not fraction.isdigit() or len(fraction) < 6:
        return None
    micros = (fraction[6:] + "000000")[:6]
    try:
        return datetime.strptime(
            f"{whole}T{fraction[:6]}.{micros}", "%Y%m%dT%H%M%S.%f"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _event_time(device: DeviceContext, record: Mapping[str, Any]) -> datetime | None:
    """When this record happened: its own ``et`` first, else the push time."""

    parsed = _parse_stamp(_record_value(record, _WIRE_TIME, _EVENT_TIME_FIELD))
    if parsed is not None:
        return parsed
    return _reported_at(device, _EVENT_SID)




def _lock_alarm_is_stale(device: DeviceContext) -> bool:
    when = device.service_updated_at(_LOCK_ALARM_SID)
    if when is None:
        return False
    return datetime.now(timezone.utc) - when > _ALARM_PULSE_WINDOW


def _reported_at(device: DeviceContext, sid: str) -> datetime | None:
    """Return when service ``sid`` last reported, tolerating ns-without-dot.

    ``device.service_updated_at()`` 内部走 ``parse_remote_timestamp``，只接受
    ``%Y%m%dT%H%M%S``（整秒）和**带小数点**的 ``...%H%M%S.%f``；而实时 MQTT
    推送携带的时间戳是**不带小数点**的 9 位纳秒（形如
    ``20260914T222156103Z``），会被判为不可解析而返回 None。

    对"最近一次告警是什么时候"这个需求而言，None 恰好出现在**告警刚发生**
    的时刻，正是最需要的时刻。因此这里补一条兜底：遇
    ``YYYYMMDDTHHMMSS<多余数字>Z`` 时取前 6 位多余数字当微秒
    （毫秒级排序足够表达"x 分钟前"）。解析失败一律返回 None，**绝不猜时间**。

    （做法与 2MZN / 2LC9 的 ``_reported_at()`` 保持一致；KW02/KW38/KW4X
    的文件头记录了同一 ts 形态现象。）
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
    # 例：whole=20260914, fraction=222156103 -> 22:21:56.103000
    micros = (fraction[6:] + "000000")[:6]
    try:
        return datetime.strptime(
            f"{whole}T{fraction[:6]}.{micros}", "%Y%m%dT%H%M%S.%f"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None






def _make_door_alarm_sensor(
    context: DeviceContext,
    key: str,
    name: str,
    codes: tuple[int, ...],
    status_codes: tuple[int, ...] = (),
    read_status: Callable[[DeviceContext], Any] | None = None,
) -> EntitySpec:
    """One read-only door-alarm sensor.

    主来源是 event 推送的 `das`；`status_codes` 非空时，若 event 读不到，
    再回退到 `lockStatus.status`（持久服务，更可靠）。
    """

    wanted = frozenset(codes)
    status_wanted = frozenset(status_codes)

    def state(device: DeviceContext) -> Mapping[str, Any]:
        record = _event_record(device)
        code = _record_alarm(record)
        if code is not None and code in wanted:
            attributes: dict[str, Any] = {"raw": code, "source": "event"}
            when = _event_time(device, record)
            if when is not None:
                attributes["last_triggered"] = when
            return {"is_on": True, "extra_state_attributes": attributes}

        # 兜底：从 lockStatus.status 判定（只有 door_not_closed 用得上）
        if status_wanted and read_status is not None:
            status = read_status(device)
            if status in status_wanted:
                return {
                    "is_on": True,
                    "extra_state_attributes": {
                        "raw_status": status,
                        "source": "lockStatus",
                    },
                }
        return {"is_on": False}

    return EntitySpec(
        platform="binary_sensor",
        key=key,
        name=name,
        state=state,
        metadata={"device_class": "problem"},
    )


def _make_group_alarm_sensor(
    name: str,
    specs: list[EntitySpec],
) -> EntitySpec:
    """汇总传感器：任一成员告警为真即 ``is_on``。

    用于"一条自动化覆盖门未关/虚掩/未锁三者"；成员传感器仍可单独使用。
    """

    def state(device: DeviceContext) -> Mapping[str, Any]:
        triggered: list[str] = []
        latest: datetime | None = None
        for spec in specs:
            result = spec.state(device) or {}
            if result.get("is_on"):
                triggered.append(spec.key)
                when = (result.get("extra_state_attributes") or {}).get("last_triggered")
                if isinstance(when, datetime) and (latest is None or when > latest):
                    latest = when
        if not triggered:
            return {"is_on": False}
        attributes: dict[str, Any] = {"triggered": triggered}
        if latest is not None:
            attributes["last_triggered"] = latest
        return {"is_on": True, "extra_state_attributes": attributes}

    return EntitySpec(
        platform="binary_sensor",
        key="door_open_problem",
        name=name,
        state=state,
        metadata={"device_class": "problem"},
    )








def _operation_direction(operation: Any) -> str | None:
    """Classify an operation code as indoor / outdoor unlock, else None."""

    number = _int(operation)
    if number is None:
        return None
    if number in _INDOOR_UNLOCK_OPERATIONS:
        return "indoor"
    if number in _UNLOCK_OPERATIONS:
        return "outdoor"
    return None


def _event_kind(record: Mapping[str, Any]) -> str | None:
    """把一个事件记录分类为 unlock / lock / alarm。

    兼容线上短名（up / das / un）与 Profile 长名，分类顺序与本适配器
    自身状态实体保持一致，避免事件与传感器对"发生了什么"给出矛盾说法。
    """

    alarm = _record_alarm(record)
    if alarm is not None and alarm >= 1:
        return "alarm"
    operation = _record_operation(record)
    if operation == 25:  # 反锁
        return "lock"
    if operation is not None and (
        operation in _UNLOCK_OPERATIONS
        or operation in _INDOOR_UNLOCK_OPERATIONS
    ):
        return "unlock"
    # 未描述的操作码 + 有用户名，视为凭据开锁记录。
    if _record_user(record) is not None:
        return "unlock"
    return None


def _lock_event_decoder(
    device: DeviceContext,
    sid: str,
    data: Mapping[str, Any],
    timestamp: str | None,
) -> list[tuple[str, Mapping[str, Any]]]:
    """把一次 event 推送转成 HA 事件。

    门锁对每次操作只推一次、从不推"已清除"，因此状态实体只能描述
    "最近发生过什么"。本解码器补上另一半：每次被接受的推送都触发一次
    事件，自动化应基于它，并可读 alarm_id 区分不同事件。
    """

    if sid != _EVENT_SID:
        return []

    # 关键：先落盘，这样即使集成没有 service_state，只读实体也能拿到数据。
    _remember_event(device, data)

    # 本次推送优先；缺失字段用该服务最后一次推送补齐（与 KW59 同做法）。
    record: dict[str, Any] = dict(_event_record(device))
    record.update(dict(data))

    kind = _event_kind(record)
    if kind is None:
        # 凭据管理、布防、门铃等记录不产生事件。
        return []

    operation = _record_operation(record)
    operation_field = _field(
        device.profile or {}, _EVENT_SID, _EVENT_OPERATION_FIELD
    )
    alarm_field = _field(
        device.profile or {}, _EVENT_SID, _EVENT_DOOR_ALARM_FIELD
    )

    payload: dict[str, Any] = {
        "alarm_id": _text(_record_value(record, "alarmId", "aid", "eid")),
        "user": _record_user(record),
        "occurred_at": _record_value(record, _WIRE_TIME, _EVENT_TIME_FIELD) or timestamp,
        "method": _enum_label(operation_field, operation) if operation is not None else None,
        "direction": _operation_direction(operation) if operation is not None else None,
    }
    alarm_code = _record_alarm(record)
    if kind == "alarm" and alarm_code is not None:
        payload["alarm"] = _enum_label(alarm_field, alarm_code)
    return [(kind, {k: v for k, v in payload.items() if v is not None})]




def _battery_value(device: DeviceContext, sid: str) -> Any:
    """Read one battery from its Profile service, ignoring the -1 placeholder."""

    value = _number(device.value(sid, _BATTERY_LEVEL_FIELD))
    if value is not None and value > _BATTERY_UNKNOWN:
        return value
    return None


def _make_battery_sensor(
    sid: str,
    manager_field: str,
    key: str,
    name: str,
) -> EntitySpec:
    """电池电量（只读）。

    先读 Profile 声明的服务（doorBattery / catEyeBattery），读不到再回退到
    **Profile 未声明**的 ``batteryManager``——同系列机型实测就是这样上报的。
    两处都读不到就显示 unknown，绝不猜一个数字。
    """

    def state(device: DeviceContext) -> Mapping[str, Any]:
        value = _battery_value(device, sid)
        if value is None:
            value = _number(device.value(_BATTERY_MANAGER_SID, manager_field))
            if value is not None and value <= _BATTERY_UNKNOWN:
                value = None
        return {"native_value": value}

    return EntitySpec(
        platform="sensor",
        key=key,
        name=name,
        state=state,
        metadata={
            "device_class": "battery",
            "unit": "%",
            "state_class": "measurement",
        },
    )




class ProductKW5NAdapter:
    """Keep all KW5N entity and command choices in this file."""

    prod_id = "KW5N"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        profile = context.profile
        if profile is None:
            return ()

        entities: list[EntitySpec] = []
        read_status = _status_reader()

        # 本适配器**只做只读感知**：门、门锁状态、低电量告警。
        # 所有控制项（lock / switch / select）、事件实体与诊断实体均已移除，
        # 见文件头「实体范围」一节。
        if context.has_service(_LOCK_STATUS_SID):

            # 门扇（只在语义明确的状态下判定）
            def door_state(device: DeviceContext) -> Mapping[str, Any]:
                status = read_status(device)
                if status in _DOOR_OPEN_STATUSES:
                    return {"is_on": True}
                if status in _DOOR_CLOSED_STATUSES:
                    return {"is_on": False}
                return {"is_on": None}

            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="door",
                    name="门",
                    state=door_state,
                    metadata={"device_class": "door"},
                )
            )

            # 门锁状态文字
            status_field = (
                _field(profile, _LOCK_STATUS_SID, _LOCK_STATUS_FIELD) or {}
            )

            def lock_status_state(device: DeviceContext) -> Mapping[str, Any]:
                value = read_status(device)
                if value is None:
                    return {"native_value": None}
                return {"native_value": _enum_label(status_field, value) or str(value)}

            entities.append(
                EntitySpec(
                    platform="sensor",
                    key="lock_status",
                    name="门锁状态",
                    state=lock_status_state,
                )
            )

        # --- 电池电量（只读） -----------------------------------------
        # Profile 声明了 doorBattery / catEyeBattery；同系列机型实际可能
        # 只通过未声明的 batteryManager 上报，故两者都查。
        if context.has_service(_DOOR_BATTERY_SID) or context.has_service(
            _BATTERY_MANAGER_SID
        ):
            entities.append(
                _make_battery_sensor(
                    _DOOR_BATTERY_SID,
                    _LITHIUM_BATTERY_FIELD,
                    "battery",
                    "门锁电量",
                )
            )
        if context.has_service(_CAT_EYE_BATTERY_SID) or context.has_service(
            _BATTERY_MANAGER_SID
        ):
            entities.append(
                _make_battery_sensor(
                    _CAT_EYE_BATTERY_SID,
                    _DRY_BATTERY_FIELD,
                    "cat_eye_battery",
                    "猫眼电量",
                )
            )

        # --- 低电量告警（只读） ---------------------------------------
        if context.has_service(_LOCK_ALARM_SID):

            def low_battery_state(device: DeviceContext) -> Mapping[str, Any]:
                # 1) lockAlarm.alarm=2（Profile 声明；同系列机型常不上报）
                value = _int(device.value(_LOCK_ALARM_SID, _LOCK_ALARM_FIELD))
                if (
                    value is not None
                    and value >= 1
                    and not _lock_alarm_is_stale(device)
                ):
                    return {"is_on": value == _ALARM_LOW_BATTERY}
                # 2) batteryManager.lpmStatus=1（Profile 未声明，但同系列机型
                #    的实际低电来源；读不到就不猜）
                lpm = _int(device.value(_BATTERY_MANAGER_SID, _BATTERY_LPM_FIELD))
                if lpm is not None:
                    return {"is_on": lpm == _LPM_ACTIVE}
                # 3) 最后回退到事件里的低电告警码（event.das=4）
                alarm = _record_alarm(_event_record(device))
                return {
                    "is_on": alarm is not None and alarm == _EVENT_ALARM_LOW_BATTERY
                }

            entities.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="low_battery",
                    name="低电量告警",
                    state=low_battery_state,
                    metadata={"device_class": "battery"},
                )
            )

        # --- 门告警只读传感器 -----------------------------------------
        # 逐码传感器：1 门未关 / 2 门虚掩 / 3 门未锁(故障) / 15 长时间未开门
        # 数据来自 event 推送的缓存（见上方"事件缓存"说明）。
        if context.has_service(_EVENT_SID):
            door_alarm_specs: dict[str, EntitySpec] = {}
            for key, name, codes, status_codes in _DOOR_ALARM_SENSORS:
                spec = _make_door_alarm_sensor(
                    context, key, name, codes, status_codes, read_status
                )
                door_alarm_specs[key] = spec
                entities.append(spec)

            for key, name, members in _DOOR_GROUP_SENSORS:
                specs = [door_alarm_specs[m] for m in members if m in door_alarm_specs]
                if specs:
                    entities.append(_make_group_alarm_sensor(name, specs))

            # --- 事件实体（每次开锁 / 上锁 / 告警都 fire 一次） --------
            # 状态实体只能表达"最近一次"，自动化请基于这个事件实体。
            entities.append(
                EntitySpec(
                    platform="event",
                    key="lock_event",
                    name="门锁事件",
                    state=lambda device: {},
                    metadata={
                        "event_types": ["unlock", "lock", "alarm"],
                        "icon": "mdi:door-open",
                    },
                    event_decoder=_lock_event_decoder,
                )
            )

        return tuple(entities)


ADAPTER = ProductKW5NAdapter()
