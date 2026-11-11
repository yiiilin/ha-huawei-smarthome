"""User-contributed protocol for Huawei product 2983 (名豆之约智能插座16A).

设备类型: 智能插座 (Socket / deviceTypeId 01D), 型号 HPS001
制造商: 广州万烨 (wanyesw), protocolType=WiFi, uiType=H5

该 Profile 共 7 个服务:
    switch / timer / delay / electricity / powerElectricity / update / netInfo

已暴露实体:
   switch.on                          -> switch "电源"      (0 关 / 1 开)
   powerElectricity.power             -> sensor "实时功率"  (W)
   powerElectricity.TotalElectricity  -> sensor "累计电量"  (Wh ÷ 1000 -> kWh)
   delay.delay                        -> sensor "倒计时结束" (device_class timestamp)
   delay (write)                      -> number "倒计时"     (分钟, 写入即下发)
   delay.action=2                    -> button "取消倒计时"

未暴露的服务与原因:
   electricity.electricity  「阶段用电量」: Profile 只给出"阶段"这一说法，
       没有定义统计窗口（按天 / 按次通电 / 按结算周期均有可能），
       语义不确定时不猜投影，故不做实体。
   timer.timer  只做只读展示 (sensor "定时任务")，不提供写入，原因见下。
   update.*  OTA 升级动作与进度。
   netInfo.*  实测该设备 netInfo 恒为空对象（云端不下发 RSSI/SSID/IP），
       不做永远 unknown 的诊断实体。

倒计时的真实报文结构 (真机抓取, 2026-10-31):
   App 里设 30 分钟后，设备上报的 delay 服务为:

       {"delay": [{"para": "on", "paraValue": -1,
                   "end": "20261031T133510Z", "id": 1, "sid": "switch"}],
        "num": 1}

   与 Profile 的三处不一致（按 Profile 写必然失败）:
     1. end 不是 Profile 声称的 "HHmmssZ"，而是 "YYYYMMDDTHHMMSSZ" 全量 UTC；
     2. Profile 说 start/end 至少填一个，实际没有 start 字段，缺省即"立即生效"；
     3. paraValue 恒为 -1，而 switch.on 是 bool 字段（合法值只有 0/1）。
        因此 -1 不是"要写入的值"，而是"到点关闭"这个动作的编码：
        它永远不会等于 1，所以本设备的倒计时只能关、不能开。
   该结论与 App 行为一致（App 不提供"倒计时开启"），属于协议层限制，
   不是 UI 缺失。

   写入报文按上述结构反向构造，字段顺序无关；action=1 创建 / action=2 删除。
   两者均已真机验证通过（见文末验证记录 5、6）。

定时的真实报文结构 (真机抓取, 2026-10-31):
   App 里新增 "01:00 开启 / 02:00 关闭" 后，设备上报的 timer 服务为:

       {"timer": [{"week": 0, "para": "on", "enable": 1,
                   "start": "170056Z", "paraValue": -1,
                   "end": "180056Z", "id": 1, "sid": "switch"}],
        "num": 1}

   与 delay 的差异:
     * start/end 使用 "HHmmssZ"(UTC)，与 Profile 一致；而 delay 的 end 用的是
       "YYYYMMDDTHHMMSSZ"。两者格式不统一，不能互相套用。
     * 一次"开 + 关"在协议里是**一条**记录（start 开、end 关），不是两条；
       App 里看起来是两个任务，设备侧 num 只有 1。
     * week=0 表示单次；bit0~bit6 分别对应周一~周日。

   定时写入契约 (真机验证, 2026-10-31):
     * action=1 (create) + timer[] 是**追加**，不是整表替换:
       下发第 6 条后 num 由 5 变 6，原有 5 条全部保留；
       id 随报文下发并被设备原样保存，条目按其 start/end 真实执行
       （5 秒轮询观测：start 后 6~11 秒内通电，end 后 6~11 秒内断电）。
     * action=2 (delete) + timer[]（带 id）按 id 精确删除单条，其余不动。
     * 单次定时执行完不会自动删除，而是被置为 enable=0 留在表里，
       需要显式 delete 才会消失。

   为什么本适配器仍不提供定时写入:
     * 写入契约已经明确，缺的不是协议证据，而是 HA 侧的表达能力:
       一条定时 = 起止时刻 + 星期掩码，当前框架没有 time 平台，
       用 number/select 硬拼需要 4~6 个控件才能表达一条定时。
     * 按仓库规则，补齐 time 平台属于框架改动，必须与单品适配拆成两个 PR。
       因此本文件只做只读展示，写入留待框架 PR 合入后再补。

缩放依据:
   Profile 对 electricity / TotalElectricity 显式声明 unit=Wh，power 声明 unit=W，
   因此累计电量按 ÷1000 换算成 kWh；不按 Profile 的 max 做任何裁剪 ——
   ⚠️ Profile 给 TotalElectricity 的 max=65535，但设备实际已上报 359903 Wh，
   按 max 裁剪会把真实电量截断成 65535。

真机验证记录 (2026-10-31):
   1. switch.on 写命令: 已实测。HA 点按后设备实际通/断电，云端链路正常。
   2. powerElectricity.power: 已实测，读数与实际负载一致（带载时约 2323 W）。
   3. powerElectricity.TotalElectricity: 已实测数值正确（359.903 -> 359.920 kWh）。
      该字段由设备侧累计且上报有节流，短时间内不刷新属正常现象。
   4. App 侧倒计时: 已实测。设 1 分钟后设备自动断开，HA 侧同步收到 on=0；
      设 30 分钟后 delay 服务上报上述结构。
   5. 本适配器下发 action=1 创建倒计时: 已实测。下发 2 分钟后设备接受并回传
      end=2026-10-31T13:19:16Z，number 显示 2、倒计时结束传感器同步更新时间戳；
      到点后设备自动断开 (on=1 -> 0) 并清空 delay 数组。
   6. 本适配器下发 action=2 删除倒计时: 已实测。下发 5 分钟后按取消，
      设备立即清空 delay 数组，两个实体回到 unknown。
   7. 倒计时执行方向: 只能关不能开。paraValue 恒为 -1，与 App 行为一致，
      属于协议层限制而非 UI 缺失。
   8. 定时任务: 已抓取真实结构（见上）。App 里设 "01:00 开 / 02:00 关" 后，
      设备侧是单条记录 start=170056Z(即本地 01:00)、end=180056Z(本地 02:00)，
      num=1、week=0；本适配器按此渲染为 sensor "定时任务"（只读）。
   9. week 掩码: 用 5 组定时实测确认 bit0=周一 … bit6=周日：
      单次=0、工作日=31、周末=96、每天=127、周二四六=42，与 App 选项一一对应。
  10. 定时写入: 已实测 action=1 追加（num 5->6，原 5 条保留）、
      action=2 按 id 删除单条（其余不动）；由 HA 下发的定时在 start/end 后
      6~11 秒内真实通断电（5 秒轮询粒度）。单次执行后设备置 enable=0
      而不删除，需显式 delete。

待真机确认:
   1. 断电后累计值是否保持；若会归零，state_class 需从 total_increasing 改为 total。
   2. 上报截止值 (Profile max=65535) 被设备突破后是否回绕。
   3. number "倒计时" 的显示值取自最近一次上报的剩余分钟，设备中途不上报进度，
      因此两分钟倒计时期间会一直显示 2；精确剩余时间请以 timestamp 传感器为准。
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

_WH_PER_KWH = 1000.0
_DELAY_ACTION_CREATE = 1
_DELAY_ACTION_DELETE = 2
_DELAY_END_FORMAT = "%Y%m%dT%H%M%SZ"
_COUNTDOWN_MAX_MINUTES = 1440.0
_COUNTDOWN_DEFAULT_ENTRY_ID = 1


def _as_bool(value: Any) -> bool | None:
    """严格解析开关量: 只接受 0/1 及等价字符串，其它返回 None。"""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().casefold()
        if token in {"1", "true", "on"}:
            return True
        if token in {"0", "false", "off"}:
            return False
        return None
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _watts(value: Any) -> int | float | None:
    number = _number(value)
    if number is None:
        return None
    return int(number) if number.is_integer() else round(number, 3)


def _wh_to_kwh(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number / _WH_PER_KWH, 3)


def _delay_entries(context: DeviceContext) -> list[Mapping[str, Any]]:
    """返回设备当前上报的倒计时条目，结构异常时视作空。"""

    raw = context.value("delay", "delay")
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, Mapping)]


def _parse_delay_end(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.strptime(value, _DELAY_END_FORMAT).replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _format_delay_end(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(_DELAY_END_FORMAT)


def _countdown_deadline(context: DeviceContext) -> datetime | None:
    """取最晚的一个倒计时结束时间；设备同时只允许一条。"""

    deadlines = [
        deadline
        for deadline in (
            _parse_delay_end(entry.get("end"))
            for entry in _delay_entries(context)
        )
        if deadline is not None
    ]
    if not deadlines:
        return None
    return max(deadlines)


def _countdown_remaining(context: DeviceContext) -> int | None:
    """剩余分钟数；已过期或未设置返回 None（number 的 min 是 1）。"""

    deadline = _countdown_deadline(context)
    if deadline is None:
        return None
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds() / 60
    if remaining <= 0:
        return None
    # 向上取整：剩 50 秒也要显示 1 分钟，否则 number 会闪成 unknown。
    return max(1, math.ceil(remaining))


_TIMER_WEEK_LABELS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _timer_entries(context: DeviceContext) -> list[Mapping[str, Any]]:
    """返回设备当前上报的周期定时条目，结构异常时视作空。"""

    raw = context.value("timer", "timer")
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, Mapping)]


def _clock_from_utc(value: Any) -> str | None:
    """把定时器的 "HHmmssZ"(UTC) 换算成本地 HH:MM。"""

    if not isinstance(value, str) or len(value) < 6:
        return None
    try:
        hour = int(value[0:2])
        minute = int(value[2:4])
        second = int(value[4:6])
    except ValueError:
        return None
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        return None
    moment = datetime.now(timezone.utc).replace(
        hour=hour,
        minute=minute,
        second=second,
        microsecond=0,
    )
    return moment.astimezone().strftime("%H:%M")


def _week_label(value: Any) -> str:
    """week 是 7bit 掩码，bit0~bit6 对应周一~周日；0 表示单次。"""

    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return "单次"
    days = [
        label
        for bit, label in enumerate(_TIMER_WEEK_LABELS)
        if value & (1 << bit)
    ]
    if len(days) == len(_TIMER_WEEK_LABELS):
        return "每天"
    return "、".join(days) if days else "单次"


def _timer_enabled_count(context: DeviceContext) -> int:
    """已启用的定时条数，与 prod_2qq4 的读法保持一致（缺失不算启用）。"""

    return sum(
        1
        for entry in _timer_entries(context)
        if entry.get("enable") in (1, True)
    )


def _timer_summary(context: DeviceContext) -> str:
    timers = _timer_entries(context)
    if not timers:
        return "未设置"
    parts: list[str] = []
    for entry in timers:
        start = _clock_from_utc(entry.get("start"))
        end = _clock_from_utc(entry.get("end"))
        window = "–".join(part for part in (start, end) if part) or "时间未知"
        if entry.get("enable") in (0, False):
            window = f"{window}(停用)"
        parts.append(f"{window} {_week_label(entry.get('week'))}")
    return "；".join(parts)


async def _power_on(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("switch", {"on": 1})


async def _power_off(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("switch", {"on": 0})


async def _set_countdown(
    context: DeviceContext,
    data: Mapping[str, Any],
) -> None:
    """把 number 的取值当成"从现在起 N 分钟后关闭"，立即下发。"""

    minutes = _number(data.get("value"))
    if minutes is None or minutes < 1:
        raise ValueError("2983 countdown requires at least 1 minute")
    minutes = min(minutes, _COUNTDOWN_MAX_MINUTES)
    existing = _delay_entries(context)
    entry_id = existing[0].get("id") if existing else None
    if not isinstance(entry_id, int):
        entry_id = _COUNTDOWN_DEFAULT_ENTRY_ID
    endpoint = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    await context.async_send_service(
        "delay",
        {
            "action": _DELAY_ACTION_CREATE,
            "delay": [
                {
                    "id": entry_id,
                    "sid": "switch",
                    "para": "on",
                    # -1 是"到点关闭"的动作编码，不是合法的 on 值。
                    "paraValue": -1,
                    "end": _format_delay_end(endpoint),
                }
            ],
        },
    )


async def _cancel_countdown(
    context: DeviceContext,
    _data: Mapping[str, Any],
) -> None:
    """删除当前倒计时；没有可删条目时保持静默。"""

    entries = _delay_entries(context)
    if not entries:
        return
    payload: list[dict[str, Any]] = []
    for entry in entries:
        item: dict[str, Any] = {}
        if isinstance(entry.get("id"), int):
            item["id"] = entry["id"]
        if isinstance(entry.get("sid"), str):
            item["sid"] = entry["sid"]
        if isinstance(entry.get("end"), str):
            item["end"] = entry["end"]
        payload.append(item)
    if not payload:
        return
    await context.async_send_service(
        "delay",
        {"action": _DELAY_ACTION_DELETE, "delay": payload},
    )


class Product2983Adapter:
    """2983 名豆之约智能插座16A (HPS001) 适配器。"""

    prod_id = "2983"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None:
            return ()

        specs: list[EntitySpec] = []

        # --- switch.on (RW, 电源) --------------------------------------
        if context.has_service("switch"):
            specs.append(
                EntitySpec(
                    platform="switch",
                    key="power",
                    name="电源",
                    state=lambda ctx: {
                        "is_on": _as_bool(ctx.value("switch", "on"))
                    },
                    actions={"turn_on": _power_on, "turn_off": _power_off},
                )
            )

        # --- powerElectricity: 实时功率 + 累计电量 ----------------------
        if context.has_service("powerElectricity"):
            specs.append(
                EntitySpec(
                    platform="sensor",
                    key="real_power",
                    name="实时功率",
                    state=lambda ctx: {
                        "native_value": _watts(
                            ctx.value("powerElectricity", "power")
                        )
                    },
                    metadata={
                        "device_class": "power",
                        "state_class": "measurement",
                        "unit": "W",
                    },
                )
            )
            specs.append(
                EntitySpec(
                    platform="sensor",
                    key="total_energy",
                    name="累计电量",
                    state=lambda ctx: {
                        "native_value": _wh_to_kwh(
                            ctx.value("powerElectricity", "TotalElectricity")
                        )
                    },
                    metadata={
                        "device_class": "energy",
                        "state_class": "total_increasing",
                        "unit": "kWh",
                    },
                )
            )

        # --- delay: 倒计时（只能关，不能开） ----------------------------
        if context.has_service("delay"):
            specs.append(
                EntitySpec(
                    platform="sensor",
                    key="countdown_end",
                    name="倒计时结束",
                    state=lambda ctx: {
                        "native_value": _countdown_deadline(ctx)
                    },
                    metadata={
                        "device_class": "timestamp",
                    },
                )
            )
            specs.append(
                EntitySpec(
                    platform="number",
                    key="countdown",
                    name="倒计时",
                    state=lambda ctx: {
                        "native_value": _countdown_remaining(ctx)
                    },
                    metadata={
                        "min": 1,
                        "max": int(_COUNTDOWN_MAX_MINUTES),
                        "step": 1,
                        "unit": "min",
                    },
                    actions={"set_value": _set_countdown},
                )
            )
            specs.append(
                EntitySpec(
                    platform="button",
                    key="countdown_cancel",
                    name="取消倒计时",
                    state=lambda _ctx: {},
                    metadata={"entity_category": "config"},
                    actions={"press": _cancel_countdown},
                )
            )

        # --- timer: 周期定时（只读展示，写入见文件头说明） ---------------
        # 沿用 prod_2qq4 / prod_105m / prod_100z 的既有惯例:
        # native_value = 已启用的定时条数, 明细放在属性里。
        if context.has_service("timer"):
            specs.append(
                EntitySpec(
                    platform="sensor",
                    key="timer_schedules",
                    name="定时任务",
                    state=lambda ctx: {
                        "native_value": _timer_enabled_count(ctx),
                        "extra_state_attributes": {
                            "total": len(_timer_entries(ctx)),
                            "summary": _timer_summary(ctx),
                            "schedules": [
                                dict(entry) for entry in _timer_entries(ctx)
                            ],
                        },
                    },
                    metadata={"entity_category": "diagnostic"},
                )
            )

        return tuple(specs)


ADAPTER = Product2983Adapter()
