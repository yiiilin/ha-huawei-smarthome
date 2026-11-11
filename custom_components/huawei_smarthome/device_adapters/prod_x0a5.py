"""User-contributed protocol for Huawei product X0A5 (HUAWEI Sound SE).

设备类型: HUAWEI Sound SE, 型号 JSPH-00
制造商: 华为 (HUAWEI)

核心服务:
   hwaccount.activeState       enum R   激活状态(0=在线, 其余=未授权)
   speakerState.State          enum R   音箱状态(0=待机中,1=拾音中,2=等待响应,3=语音播报)
   smartspeaker.playControl    enum RW  播放控制(0=停止播放,1=启动播放,2=上一首/下一首 *值重复*)
   audioplayer.playState       enum R   播放状态(0=暂停,1=播放中,2=停止)
   BTIdle.BTIdle               enum R   蓝牙音频状态(0=空闲,1=音频,2=通话忙碌)

本适配器暴露:
   1.  sensor   音箱状态
   2.  sensor   播放状态
   3.  sensor   激活状态
   4.  sensor   蓝牙音频状态
   5.  select   播放控制 (仅"停止播放" / "启动播放"，值 2 因重复跳过)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec
from .context import DeviceContext


# ---- 枚举映射 ------------------------------------------------------------

_ACTIVE_STATE_TEXT = {
    0: "在线", -1: "未授权", 1: "未授权", 2: "未授权", 3: "未授权",
    4: "未授权", 5: "未授权", 6: "未授权", 7: "未授权",
}

_SPEAKER_STATE_TEXT = {0: "待机中", 1: "拾音中", 2: "等待响应", 3: "语音播报"}

_PLAY_STATE_TEXT = {0: "暂停", 1: "播放中", 2: "停止"}

_BT_IDLE_TEXT = {0: "空闲状态", 1: "音频状态", 2: "通话忙碌"}

_PLAY_CONTROL_OPTIONS = ["停止播放", "启动播放"]
_PLAY_CONTROL_NAME_TO_VAL = {"停止播放": 0, "启动播放": 1}


# ---- 工具函数 ------------------------------------------------------------

def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        try:
            return int(round(float(value.strip())))
        except (TypeError, ValueError):
            return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


# ---- 动作函数 ------------------------------------------------------------

async def _select_play_control(context: DeviceContext, data: Mapping[str, Any]) -> None:
    val = _PLAY_CONTROL_NAME_TO_VAL.get(str(data.get("option")))
    if val is None:
        raise ValueError(f"unsupported play control: {data.get('option')}")
    await context.async_send_service("smartspeaker", {"playControl": val})


async def _play(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("smartspeaker", {"playControl": 1})


async def _pause(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("smartspeaker", {"playControl": 0})


# ---- 适配器 --------------------------------------------------------------

class ProductX0A5Adapter:
    """X0A5 HUAWEI Sound SE 适配器。"""

    prod_id = "X0A5"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None or not context.has_service("speakerState"):
            return ()

        def active_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("hwaccount", "activeState"))
            return {"native_value": _ACTIVE_STATE_TEXT.get(val, "未知")}

        def speaker_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("speakerState", "State"))
            return {"native_value": _SPEAKER_STATE_TEXT.get(val, "未知")}

        def play_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("audioplayer", "playState"))
            return {"native_value": _PLAY_STATE_TEXT.get(val, "未知")}

        def bt_idle_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("BTIdle", "BTIdle"))
            return {"native_value": _BT_IDLE_TEXT.get(val, "未知")}

        def play_control_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("audioplayer", "playState"))
            if val == 1:
                return {"current_option": "启动播放"}
            return {"current_option": "停止播放"}

        def player_state(device: DeviceContext) -> Mapping[str, Any]:
            val = _as_int(device.value("audioplayer", "playState"))
            return {
                "state": (
                    "playing"
                    if val == 1
                    else "paused"
                    if val == 0
                    else "idle"
                    if val == 2
                    else None
                ),
            }

        return (
            EntitySpec(platform="media_player", key="player", name="播放",
                       state=player_state, metadata={},
                       actions={"play": _play, "pause": _pause, "stop": _pause}),
            EntitySpec(platform="sensor", key="speaker_state", name="音箱状态",
                       state=speaker_state, metadata={"icon": "mdi:speaker"}),
            EntitySpec(platform="sensor", key="play_state", name="播放状态",
                       state=play_state, metadata={"icon": "mdi:play-circle-outline"}),
            EntitySpec(platform="sensor", key="active_state", name="激活状态",
                       state=active_state, metadata={"icon": "mdi:account-check-outline"}),
            EntitySpec(platform="sensor", key="bt_idle", name="蓝牙音频状态",
                       state=bt_idle_state, metadata={"icon": "mdi:bluetooth-audio"}),
            EntitySpec(platform="select", key="play_control", name="播放控制",
                       state=play_control_state,
                       metadata={"options": _PLAY_CONTROL_OPTIONS},
                       actions={"select_option": _select_play_control}),
        )


ADAPTER = ProductX0A5Adapter()