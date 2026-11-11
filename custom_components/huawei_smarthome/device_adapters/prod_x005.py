"""User-contributed protocol for Huawei product X005 (华为 AI 音箱 2 / 电池版).

设备类型: 华为 AI 音箱 2 (电池版) (AI Speaker 2 with Battery)
制造商: 华为, 型号 AIS-BW50-00
核心服务(播放控制):
   smartspeaker : playControl enum RW (0=停止播放, 1=启动播放, 2=上一首/下一首)
   audioplayer  : playState enum RW (0=暂停, 1=播放中, 2=停止)
   speakerState : State enum R (0=待机中, 1=拾音中, 2=等待响应, 3=语音播报)

本适配器暴露一个 Home Assistant ``media_player`` 实体, 提供 播放/暂停/停止 控制.
注: playControl=2 在设备资料中上一首与下一首共用同一值, 无法可靠区分,
    故不暴露 上一首/下一首 动作, 避免误操作.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..const import ATTR_COMMAND, ATTR_SILENT, SERVICE_VOICE_COMMAND
from .api import EntitySpec
from .context import DeviceContext

_STATE_PLAYING = "playing"
_STATE_PAUSED = "paused"
_STATE_IDLE = "idle"
_TTS_TONE_URL = "https://speaker-drcn.things.hicloud.com:9443/resource/silence.ogg"


def _as_int(value: Any) -> int | None:
    """容忍 int / 数字字符串 / bool。"""
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


async def _play(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("smartspeaker", {"playControl": 1})


async def _pause(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("audioplayer", {"playState": 0})


async def _stop(context: DeviceContext, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("smartspeaker", {"playControl": 0})


async def _speak(context: DeviceContext, data: Mapping[str, Any]) -> None:
    """Send the verified X005 text-to-speech service command."""

    message = data.get("message")
    if not isinstance(message, str) or not message:
        raise ValueError("notify message must be a non-empty string")
    directive = json.dumps(
        {
            "command": {
                "header": {
                    "messageId": "",
                    "name": "SetVoiceSpeech",
                    "namespace": "Notifications",
                },
                "payload": {
                    "asset": {"text": message, "tone": _TTS_TONE_URL},
                    "ledProfile": 1,
                    "loopCount": 1,
                },
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    await context.async_send_service("communication", {"directive": directive})


async def _voice_command(
    context: DeviceContext,
    data: Mapping[str, Any],
) -> None:
    """Send one natural-language command through the speaker assistant."""

    command = data.get(ATTR_COMMAND)
    if not isinstance(command, str) or not command.strip():
        raise ValueError("voice command must be a non-empty string")
    silent = data.get(ATTR_SILENT, True)
    if not isinstance(silent, bool):
        raise ValueError("voice command silent must be a boolean")
    content = json.dumps(
        {
            "asr": command.strip(),
            "source": "smarthome",
            "noVui": int(silent),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    await context.async_send_service("speakerIfttt", {"content": content})


class ProductX005Adapter:
    """X005 华为 AI 音箱 2 适配器。"""

    prod_id = "X005"

    def service_actions(self, context: DeviceContext) -> Mapping[str, Any]:
        """Declare integration services supported by this product."""

        if not context.has_service("speakerIfttt"):
            return {}
        return {SERVICE_VOICE_COMMAND: _voice_command}

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None:
            return ()

        entities: list[EntitySpec] = []

        def player_state(device: DeviceContext) -> Mapping[str, Any]:
            state_code = _as_int(device.value("audioplayer", "playState"))
            if state_code == 1:
                state = _STATE_PLAYING
            elif state_code == 0:
                state = _STATE_PAUSED
            else:
                state = _STATE_IDLE
            return {"state": state}

        if context.has_service("audioplayer"):
            entities.append(
                EntitySpec(
                    platform="media_player",
                    key="speaker",
                    name=None,
                    state=player_state,
                    actions={
                        "play": _play,
                        "pause": _pause,
                        "stop": _stop,
                    },
                )
            )
        if context.has_service("communication"):
            entities.append(
                EntitySpec(
                    platform="notify",
                    key="play_text",
                    name="播放指定文字",
                    state=lambda _ctx: {},
                    actions={"send_message": _speak},
                )
            )
        return tuple(entities)


ADAPTER = ProductX005Adapter()


