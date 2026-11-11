"""User-contributed protocol for Huawei product V0D0 (华为智慧屏 S3 Pro).

设备型号 AJMD-360S (HUAWEI Vision S3 Pro), deviceTypeId 09C。
Profile: https://smarthome-drcn.dbankcdn.com/device/guide/V0D0/V0D0.json

公开 Profile 只声明 6 个服务(messageboard/remotecontrol/autoconfig/devicestate/
generalcommand/logreport), 实机实际上报 45 个服务(与 V0EM/V0DL 同代架构)。
本适配器完全按实机上报的字段构建, 每个实体都以对应服务真实存在为前提。

实机上报(2026-10-14 集成状态快照, 与实体相关的部分):

    devicestate    screenState=0, screenSwitch=0      0 熄屏 / 1 在线 / 2 离线
    switch         on="1"                             (服务实为 screenSwitch)
    screen         on=false, mode=MASTER, brightness=83
    speaker        volume=10, mute=false, equalizer=MOVIE
    inputSource    name=HDMI1, defaultSource=HDMI1
    systemMode     mode=STANDARD_MODE
    pictureMode / voiceMode (裸数字, 未标定标签)
    remotecontrol  ip_addr=192.168.6.79, switchState="1"
    devMsg         devMac=98:2F:F8:0F:88:77
    videoPlayer / audioPlayer (state / progress / metadata)

写入说明(沿用同代 V0EM/V0A2 实机实测结论, V0D0 服务与字段结构完全一致):

    - 开机(亮屏): screen 服务 on=True 云端实测有效, ~5s 内亮屏。
      switch.on=1 / devicestate.screenState 等字段在息屏状态会被设备侧
      拒绝(errcode=-1) —— 熄屏时设备只认 screen.on 通道。故 _power_on 把
      screen.on 放在首位, 其余通道依次兜底。
    - 关机(息屏): screen.on=False 或 switch.on=0 均有效。"关机"实为熄屏,
      网络保持在线(华为官方: 熄屏状态仅遥控器/语音键可用, App 开机走
      模拟遥控器私有通道)。
    - "switch" 服务实为 screenSwitch, on 为字符串且息屏后仍报 "1",
      不能作为电源状态来源; 电源状态以 devicestate.screenState 为准。
    - speaker.volume 云端假 ACK(V0DL 实测设备不执行), volume 服务直接拒绝;
      因此音量只做只读展示, 不做可写控件。
    - generalCommand 为华为私有字符串通道, 不暴露。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .api import EntitySpec
from .context import DeviceContext

try:  # 保留引用以兼容旧环境; 适配器内已不再依赖它翻译报错。
    from ..mqtt.commands import HuaweiCommandRejectedError  # noqa: F401
except Exception:  # pragma: no cover
    HuaweiCommandRejectedError = None


# ---------------------------------------------------------------- 服务 / 字段

# 电源控制走 devicestate(实机实测): 息屏后设备上报 screenState=0/screenSwitch=0,
# 开机写回 1 云端有效。"switch" 服务实为 screenSwitch 且息屏后仍报 on="1",
# 重复写同值会被云端拒绝, 因此只读不写。
_SCREEN_STATE_SID = "devicestate"
_SCREEN_STATE_FIELD = "screenState"
_SCREEN_SWITCH_FIELD = "screenSwitch"

_LEGACY_SWITCH_SID = "switch"
_LEGACY_SWITCH_FIELD = "on"

_SCREEN_SID = "screen"

_DIS_SID = "dis"
_DIS_CMD_FIELD = "cmd"

_SCREEN_BRIGHTNESS_FIELD = "brightness"
_SCREEN_MODE_FIELD = "mode"

_SPEAKER_SID = "speaker"
_SPEAKER_VOLUME_FIELD = "volume"
_SPEAKER_MUTE_FIELD = "mute"
_SPEAKER_EQUALIZER_FIELD = "equalizer"

_PICTURE_MODE_SID = "pictureMode"
_PICTURE_MODE_FIELD = "mode"

_VOICE_MODE_SID = "voiceMode"
_VOICE_MODE_FIELD = "mode"

_INPUT_SOURCE_SID = "inputSource"
_INPUT_SOURCE_FIELD = "defaultSource"

_SYSTEM_MODE_SID = "systemMode"
_SYSTEM_MODE_FIELD = "mode"

_SCREEN_SAVER_SID = "screenSaver"
_SCREEN_SAVER_FIELD = "switch"
_SCREEN_SAVER_ON = 1

_CHILD_MODE_SID = "childMode"
_CHILD_MODE_FIELD = "mode"
_CHILD_WATCH_TIME_FIELD = "watchTime"
_CHILD_MODE_OFF = "OFF"

_REMOTE_CONTROL_SID = "remotecontrol"
_REMOTE_CONTROL_IP_FIELD = "ip_addr"
_REMOTE_CONTROL_SWITCH_FIELD = "switchState"
_REMOTE_CONTROL_ON = 1

_VIDEO_PLAYER_SID = "videoPlayer"
_AUDIO_PLAYER_SID = "audioPlayer"

_SCREEN_STATE_LABELS = {0: "熄屏", 1: "在线", 2: "离线"}

_PLAYER_STATE_MAP = {
    "PLAYING": "playing",
    "PAUSED": "paused",
    "BUFFERING": "buffering",
    "PREPARING": "buffering",
    "STOPPED": "idle",
    "STOP": "idle",
    "FINISHED": "idle",
    "COMPLETED": "idle",
    "IDLE": "idle",
}

_ACTIVE_PLAYER_STATES = frozenset({"PLAYING", "PAUSED", "BUFFERING", "PREPARING"})

# 播放器上报超过这个时长就算陈旧: 电视断电后最后一次的剧名会一直留在云端。
_STALE_AFTER_SECONDS = 30 * 60

# 局域网唤醒 MAC: 来自实机 devMsg.devMac。
# 本机走 Wi-Fi(lin2333_5G)连接, 唤醒基本无效; 插网线才可靠, 留着零成本。
_WAKE_MAC = "98:2f:f8:0f:88:77"


# ------------------------------------------------------------------- 取值工具


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.casefold()
        if normalized in {"1", "true", "on"}:
            return True
        if normalized in {"0", "false", "off"}:
            return False
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _text(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return text or None
    return None


def _json(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        import json

        parsed = json.loads(value)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _seconds(value: Any) -> float | None:
    number = _number(value)
    return None if number is None else float(number)


# ------------------------------------------------------------------- 新鲜度


def _reported_at(device: DeviceContext, sid: str) -> datetime | None:
    getter = getattr(device, "reported_timestamp", None)
    stamp = getter(sid) if callable(getter) else None
    if not isinstance(stamp, str):
        timestamps = getattr(device, "_timestamps", None)
        if isinstance(timestamps, Mapping):
            stamp = timestamps.get(sid)
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_fresh(device: DeviceContext, sid: str) -> bool:
    stamp = _reported_at(device, sid)
    if stamp is None:
        return True
    return (datetime.now(timezone.utc) - stamp).total_seconds() <= _STALE_AFTER_SECONDS


def _wake_on_lan(mac: str) -> bool:
    try:
        payload = bytes.fromhex("ff" * 6) + bytes.fromhex(
            mac.replace(":", "").replace("-", "")
        ) * 16
    except ValueError:
        return False
    try:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(payload, ("255.255.255.255", 9))
    except OSError:
        return False
    return True


# ------------------------------------------------------------------- 播放器


def _active_player(device: DeviceContext) -> tuple[str, Mapping[str, Any]]:
    video = (
        device.service_state(_VIDEO_PLAYER_SID)
        if device.has_service(_VIDEO_PLAYER_SID)
        else {}
    )
    audio = (
        device.service_state(_AUDIO_PLAYER_SID)
        if device.has_service(_AUDIO_PLAYER_SID)
        else {}
    )
    for sid, state in ((_VIDEO_PLAYER_SID, video), (_AUDIO_PLAYER_SID, audio)):
        if str(state.get("state") or "").upper() in _ACTIVE_PLAYER_STATES and _is_fresh(
            device, sid
        ):
            return sid, state
    return (_VIDEO_PLAYER_SID, video) if video else (_AUDIO_PLAYER_SID, audio)


def _screen_is_on(device: DeviceContext) -> bool | None:
    """屏幕是否点亮: screenState 0=熄屏, 1=亮屏, 2=离线; 兜底 screenSwitch。"""

    state = _number(device.value(_SCREEN_STATE_SID, _SCREEN_STATE_FIELD))
    if state is not None:
        return state == 1
    switch = _number(device.value(_SCREEN_STATE_SID, _SCREEN_SWITCH_FIELD))
    if switch is not None:
        return switch == 1
    return None


def _player_state(device: DeviceContext) -> str | None:
    # 熄屏优先: 播放器残留状态在息屏后一律不算数。
    if _screen_is_on(device) is False:
        return "off"
    sid, state = _active_player(device)
    raw = str(state.get("state") or "").upper()
    mapped = _PLAYER_STATE_MAP.get(raw)
    if mapped == "playing":
        return mapped
    if mapped in {"paused", "buffering"}:
        return mapped if _is_fresh(device, sid) else "on"
    if _screen_is_on(device) is True:
        return "on"
    return mapped


# ------------------------------------------------------------------- 实体构造


def _sensor(
    key: str,
    name: str,
    read,
    metadata: Mapping[str, Any] | None = None,
) -> EntitySpec:
    def state(device: DeviceContext) -> Mapping[str, Any]:
        return {"native_value": read(device)}

    return EntitySpec(
        platform="sensor",
        key=key,
        name=name,
        state=state,
        metadata=dict(metadata or {}),
    )


def _binary(
    key: str,
    name: str,
    read,
    device_class: str | None = None,
) -> EntitySpec:
    def state(device: DeviceContext) -> Mapping[str, Any]:
        return {"is_on": read(device)}

    return EntitySpec(
        platform="binary_sensor",
        key=key,
        name=name,
        state=state,
        metadata={"device_class": device_class} if device_class else {},
    )


def _media_player() -> EntitySpec:
    def state(device: DeviceContext) -> Mapping[str, Any]:
        sid, player = _active_player(device)
        is_video = sid == _VIDEO_PLAYER_SID
        playing = _player_state(device) in {"playing", "paused", "buffering"}
        metadata = _json(player.get("metadata")) if playing else {}

        volume = _number(device.value(_SPEAKER_SID, _SPEAKER_VOLUME_FIELD))
        progress = _number(player.get("progress")) if playing else None
        duration = (
            _seconds(
                metadata.get("totalTime") if is_video else metadata.get("duration")
            )
            if playing
            else None
        )

        return {
            "state": _player_state(device),
            "volume_level": (
                None if volume is None else max(0.0, min(1.0, volume / 100.0))
            ),
            "is_volume_muted": _bool(device.value(_SPEAKER_SID, _SPEAKER_MUTE_FIELD)),
            "media_title": _text(metadata.get("vodName") or metadata.get("title")),
            "media_artist": _text(metadata.get("artist")) if not is_video else None,
            "media_album_name": _text(metadata.get("album")) if not is_video else None,
            "media_series_title": _text(metadata.get("vodName")) if is_video else None,
            "media_episode": _number(metadata.get("volumeIndex")) if is_video else None,
            # progress 单位是毫秒, duration/totalTime 是秒。
            "media_position": None if progress is None else progress / 1000.0,
            "media_duration": duration,
            "media_image_url": _text(metadata.get("titlePicture")) if is_video else None,
            "source": _text(device.value(_INPUT_SOURCE_SID, _INPUT_SOURCE_FIELD)),
            "source_list": None,
        }

    async def turn_on(device: DeviceContext, data: Mapping[str, Any]) -> None:
        del data
        await _power_on(device)

    async def turn_off(device: DeviceContext, data: Mapping[str, Any]) -> None:
        del data
        await _power_off(device)

    return EntitySpec(
        platform="media_player",
        key="player",
        name="播放",
        state=state,
        metadata={},
        # 音量故意不做可写控件: V0DL 实测 speaker.volume 假 ACK, volume 服务拒写。
        actions={"turn_on": turn_on, "turn_off": turn_off},
    )


async def _power_on(device: DeviceContext) -> None:
    """亮屏/开机: 依次尝试所有可写候选, 任一成功即止。

    V0EM/V0A2 实测: 息屏后网络仍在线, 但设备侧对 switch.on=1 回 errcode=-1;
    官方文档称熄屏状态仅遥控器/语音可用 —— App 的开机走的是模拟遥控器
    的私有通道。此处按成本从低到高把未验证的云端写入通道全部试一遍。
    """

    attempts = (
        (_SCREEN_SID, {"on": True}),
        (_SCREEN_SID, {"on": 1}),
        (_SCREEN_STATE_SID, {_SCREEN_STATE_FIELD: 1}),
        (_SCREEN_STATE_SID, {_SCREEN_SWITCH_FIELD: 1}),
        (_DIS_SID, {_DIS_CMD_FIELD: 1}),
        (_LEGACY_SWITCH_SID, {_LEGACY_SWITCH_FIELD: 1}),
    )
    last_err: Exception | None = None
    for sid, payload in attempts:
        try:
            await device.async_send_service(sid, payload)
            return
        except Exception as err:  # noqa: BLE001
            last_err = err
    if last_err is not None:
        if _WAKE_MAC:
            _wake_on_lan(_WAKE_MAC)
        raise last_err


async def _power_off(device: DeviceContext) -> None:
    """息屏/关机: switch.on=0 为实机验证有效的通道, 其余作兜底。"""

    attempts = (
        (_LEGACY_SWITCH_SID, {_LEGACY_SWITCH_FIELD: 0}),
        (_SCREEN_SID, {"on": False}),
        (_SCREEN_STATE_SID, {_SCREEN_STATE_FIELD: 0}),
    )
    last_err: Exception | None = None
    for sid, payload in attempts:
        try:
            await device.async_send_service(sid, payload)
            return
        except Exception as err:  # noqa: BLE001
            last_err = err
    if last_err is not None:
        raise last_err


def _power_switch() -> EntitySpec:
    """电源开关: 跟随 devicestate.screenState (1=亮屏, 0=熄屏/离线)。"""

    def is_on(device: DeviceContext) -> bool | None:
        return _screen_is_on(device)

    async def turn_on(device: DeviceContext, data: Mapping[str, Any]) -> None:
        del data
        await _power_on(device)

    async def turn_off(device: DeviceContext, data: Mapping[str, Any]) -> None:
        del data
        await _power_off(device)

    return EntitySpec(
        platform="switch",
        key="power_switch",
        name="电源",
        state=lambda device: {"is_on": is_on(device)},
        metadata={},
        actions={"turn_on": turn_on, "turn_off": turn_off},
    )


class ProductV0D0Adapter:
    """华为智慧屏 S3 Pro (AJMD-360S) 的实体定义。"""

    prod_id = "V0D0"

    def entities(self, context: DeviceContext) -> tuple[EntitySpec, ...]:
        if context.profile is None:
            return ()

        entities: list[EntitySpec] = []

        if context.has_service(_VIDEO_PLAYER_SID) or context.has_service(
            _AUDIO_PLAYER_SID
        ):
            entities.append(_media_player())

        if context.has_service(_SCREEN_STATE_SID):
            entities.append(_power_switch())

        if context.has_service(_SCREEN_STATE_SID):
            entities.append(
                _sensor(
                    "screen_state",
                    "屏幕状态",
                    lambda device: _SCREEN_STATE_LABELS.get(
                        _number(device.value(_SCREEN_STATE_SID, _SCREEN_STATE_FIELD))
                    ),
                    {"icon": "mdi:television-shimmer"},
                )
            )
            entities.append(
                _binary(
                    "screen_switch",
                    "屏幕点亮",
                    lambda device: (
                        _number(device.value(_SCREEN_STATE_SID, _SCREEN_SWITCH_FIELD))
                        == 1
                        if _number(
                            device.value(_SCREEN_STATE_SID, _SCREEN_SWITCH_FIELD)
                        )
                        is not None
                        else None
                    ),
                )
            )

        if context.has_service(_SPEAKER_SID):
            entities.append(
                _sensor(
                    "volume",
                    "音量",
                    lambda device: _number(
                        device.value(_SPEAKER_SID, _SPEAKER_VOLUME_FIELD)
                    ),
                    {"unit": "%", "state_class": "measurement"},
                )
            )
            entities.append(
                _binary(
                    "mute",
                    "静音",
                    lambda device: _bool(
                        device.value(_SPEAKER_SID, _SPEAKER_MUTE_FIELD)
                    ),
                    "sound",
                )
            )
            entities.append(
                _sensor(
                    "sound_mode",
                    "音效模式",
                    lambda device: _text(
                        device.value(_SPEAKER_SID, _SPEAKER_EQUALIZER_FIELD)
                    ),
                    {"icon": "mdi:equalizer"},
                )
            )

        if context.has_service(_SCREEN_SID):
            entities.append(
                _sensor(
                    "screen_brightness",
                    "屏幕亮度",
                    lambda device: _number(
                        device.value(_SCREEN_SID, _SCREEN_BRIGHTNESS_FIELD)
                    ),
                    {"unit": "%", "state_class": "measurement"},
                )
            )
            entities.append(
                _sensor(
                    "screen_mode",
                    "屏幕模式",
                    lambda device: _text(device.value(_SCREEN_SID, _SCREEN_MODE_FIELD)),
                    {"icon": "mdi:monitor"},
                )
            )

        if context.has_service(_PICTURE_MODE_SID):
            entities.append(
                _sensor(
                    "picture_mode",
                    "图像模式",
                    lambda device: _text(
                        device.value(_PICTURE_MODE_SID, _PICTURE_MODE_FIELD)
                    ),
                    {"icon": "mdi:image-filter-hdr"},
                )
            )

        if context.has_service(_VOICE_MODE_SID):
            entities.append(
                _sensor(
                    "voice_mode",
                    "语音模式",
                    lambda device: _text(
                        device.value(_VOICE_MODE_SID, _VOICE_MODE_FIELD)
                    ),
                    {"icon": "mdi:microphone-message"},
                )
            )

        if context.has_service(_INPUT_SOURCE_SID):
            entities.append(
                _sensor(
                    "input_source",
                    "信号源",
                    lambda device: _text(
                        device.value(_INPUT_SOURCE_SID, _INPUT_SOURCE_FIELD)
                    ),
                    {"icon": "mdi:video-input-hdmi"},
                )
            )

        if context.has_service(_SYSTEM_MODE_SID):
            entities.append(
                _sensor(
                    "system_mode",
                    "系统模式",
                    lambda device: _text(
                        device.value(_SYSTEM_MODE_SID, _SYSTEM_MODE_FIELD)
                    ),
                    {"icon": "mdi:television-classic"},
                )
            )

        if context.has_service(_SCREEN_SAVER_SID):
            entities.append(
                _binary(
                    "screen_saver",
                    "屏保",
                    lambda device: (
                        None
                        if _number(
                            device.value(_SCREEN_SAVER_SID, _SCREEN_SAVER_FIELD)
                        )
                        is None
                        else _number(
                            device.value(_SCREEN_SAVER_SID, _SCREEN_SAVER_FIELD)
                        )
                        == _SCREEN_SAVER_ON
                    ),
                )
            )

        if context.has_service(_CHILD_MODE_SID):
            entities.append(
                _binary(
                    "child_mode",
                    "儿童模式",
                    lambda device: (
                        None
                        if _text(device.value(_CHILD_MODE_SID, _CHILD_MODE_FIELD))
                        is None
                        else _text(
                            device.value(_CHILD_MODE_SID, _CHILD_MODE_FIELD)
                        ).upper()
                        != _CHILD_MODE_OFF
                    ),
                )
            )
            entities.append(
                _sensor(
                    "child_watch_time",
                    "儿童观看时长",
                    lambda device: _number(
                        device.value(_CHILD_MODE_SID, _CHILD_WATCH_TIME_FIELD)
                    ),
                    {"unit": "min", "state_class": "measurement"},
                )
            )

        if context.has_service(_REMOTE_CONTROL_SID):
            entities.append(
                _sensor(
                    "ip",
                    "IP 地址",
                    lambda device: _text(
                        device.value(_REMOTE_CONTROL_SID, _REMOTE_CONTROL_IP_FIELD)
                    ),
                    {"icon": "mdi:ip-network"},
                )
            )
            entities.append(
                _binary(
                    "remote_control",
                    "遥控开关",
                    lambda device: (
                        None
                        if _number(
                            device.value(
                                _REMOTE_CONTROL_SID, _REMOTE_CONTROL_SWITCH_FIELD
                            )
                        )
                        is None
                        else _number(
                            device.value(
                                _REMOTE_CONTROL_SID, _REMOTE_CONTROL_SWITCH_FIELD
                            )
                        )
                        == _REMOTE_CONTROL_ON
                    ),
                )
            )

        return tuple(entities)


ADAPTER = ProductV0D0Adapter()
