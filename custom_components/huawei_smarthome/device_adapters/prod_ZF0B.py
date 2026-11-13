"""Whole-home host adapter for Huawei product ZF0B (LDN-C00 智能主机SE).

主机本体没有灯/插座类可控对象，云端真正能下发的只有「手动场景」：
``clickedScene {id: <sceneId>, ctrlSrc: 6}``（同族 zf0c 适配器注释里的协议），
外加自动扫描子设备开关。

场景列表跟着用户配置变（当前 4 条里 2 条启用），所以按钮在构建实体时
按 ``manualScene.scene`` 现场生成，只取 enable=1 的手动场景；改过场景后
重载集成即可同步，不会留下指向已删场景的死按钮。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec, HuaweiProductAdapter

# 云端 H5 点场景就是带这个来源位，缺了会被判成非法请求。
_SCENE_CTRL_SRC = 6


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_sensor(
    context: Any,
    sid: str,
    key: str,
    name: str,
    *,
    icon: str | None = None,
) -> EntitySpec | None:
    if not context.has_service(sid):
        return None
    if _text(context.value(sid, key)) is None:
        return None
    metadata: dict[str, Any] = {}
    if icon:
        metadata["icon"] = icon
    return EntitySpec(
        platform="sensor",
        key=f"{sid}_{key}",
        name=name,
        state=lambda ctx: {"native_value": _text(ctx.value(sid, key))},
        metadata=metadata,
    )


def _scene_buttons(context: Any) -> list[EntitySpec]:
    scenes = context.value("manualScene", "scene")
    if not isinstance(scenes, list):
        return []
    specs: list[EntitySpec] = []
    seen: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, Mapping):
            continue
        if int(scene.get("enable") or 0) != 1:
            continue
        if int(scene.get("triggerType") or 1) != 1:
            continue
        scene_id = scene.get("id")
        if scene_id is None:
            continue
        label = _text(scene.get("name")) or f"场景 {scene_id}"
        key = f"scene_{scene_id}"
        if key in seen:
            continue
        seen.add(key)

        async def press(ctx: Any, _data: Mapping[str, Any], scene_id=scene_id) -> None:
            await ctx.async_send_service(
                "clickedScene", {"id": scene_id, "ctrlSrc": _SCENE_CTRL_SRC}
            )

        specs.append(
            EntitySpec(
                platform="button",
                key=key,
                name=label,
                state=lambda _ctx: {},
                metadata={"icon": "mdi:play-circle-outline"},
                actions={"press": press},
            )
        )
    return specs


def _mesh_sensor(context: Any) -> EntitySpec | None:
    data = context.value("stsSession", "data")
    if not isinstance(data, Mapping):
        return None
    total = data.get("devSum")
    online = data.get("successNum")
    if total is None and online is None:
        return None

    def state(ctx: Any) -> dict[str, Any]:
        raw = ctx.value("stsSession", "data") or {}
        total_now = raw.get("devSum")
        online_now = raw.get("successNum")
        if online_now is None and total_now is None:
            return {}
        return {"native_value": f"{online_now}/{total_now}"}

    return EntitySpec(
        platform="sensor",
        key="stsSession_data",
        name="组网设备",
        state=state,
        metadata={"icon": "mdi:lan"},
    )


def _firmware_sensor(context: Any) -> EntitySpec | None:
    """devOta 的 version 常为空、只有 searchversion 有值，所以直接给一句人话状态。"""

    if not context.has_service("devOta"):
        return None

    def state(ctx: Any) -> dict[str, Any]:
        info = ctx.service_state("devOta")
        latest = _text(
            info.get("searchversion") or info.get("checkmatch") or info.get("updatedVersion")
        )
        current = _text(ctx.value("solutionUpdate", "version"))
        if latest is None:
            return {"native_value": f"已安装 {current}" if current else "未知"}
        if current and latest.split("(")[0] == current:
            return {"native_value": f"已是最新 {current}"}
        return {"native_value": f"{current or '?'} → {latest}"}

    return EntitySpec(
        platform="sensor",
        key="firmware_status",
        name="固件状态",
        state=state,
        metadata={"icon": "mdi:update"},
    )


class ProductZF0BAdapter:
    prod_id = "ZF0B"

    def entities(self, context: Any) -> tuple[EntitySpec, ...]:
        if (context.prod_id or "").casefold() != self.prod_id.casefold():
            return ()
        specs: list[EntitySpec] = []
        specs.extend(_scene_buttons(context))
        for spec in (
            _text_sensor(context, "os", "version", "系统版本", icon="mdi:chip"),
            _text_sensor(
                context, "solutionUpdate", "version", "解决方案版本", icon="mdi:package-variant"
            ),
            _mesh_sensor(context),
            _firmware_sensor(context),
        ):
            if spec is not None:
                specs.append(spec)
        return tuple(specs)


ADAPTER: HuaweiProductAdapter = ProductZF0BAdapter()
