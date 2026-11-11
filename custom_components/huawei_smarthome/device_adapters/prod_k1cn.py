"""Profile-driven adapter for 华为凌霄子母路由 Q6 网线版 (K1CN).

云端只暴露路由自身的配置与统计服务，没有客户端列表：

* ``weekly``          — 上网统计：接入设备数 / 流量 / 最高速率（周维度）
* ``lingxiaoAbility`` — 子路由（灵霄）数量
* ``stsSession``      — 主 Wi-Fi 名称与开关状态
* ``routerConfig``    — IPv6、频宽、工作模式等；写 IPv6 时整包回写同一服务
* ``voiceReboot``     — 远程重启命令（无属性）

这些服务在 Profile 里大多只标了可读或压根没登记字段，所以可用性判断用
``has_service`` + 实际值是否存在，而不是 Profile 的读写标记。

流量字段 ``weekly.flow`` 的量纲云端未声明，这里按 MB 折算成 GB 展示；若与
华为智慧生活显示的数值不符，只需改 ``_FLOW_MB_TO_GB`` 的换算系数。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .api import EntitySpec, HuaweiProductAdapter
from .product_helpers import bool_value, matches_product

_FLOW_MB_TO_GB = 1.0 / 1024.0


def _raw(context: Any, sid: str, field: str) -> Any:
    try:
        return context.value(sid, field)
    except Exception:  # noqa: BLE001 - 云端字段缺失时降级为 unknown
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


async def _reboot(context: Any, _data: Mapping[str, Any]) -> None:
    await context.async_send_service("voiceReboot", {})


def _sensor(
    context: Any,
    sid: str,
    field: str,
    key: str,
    name: str,
    *,
    metadata: Mapping[str, Any] | None = None,
    scale: float = 1.0,
) -> EntitySpec | None:
    if not context.has_service(sid) or _raw(context, sid, field) is None:
        return None

    def state(ctx: Any, service_id: str = sid, field_name: str = field) -> Mapping[str, Any]:
        value = _number(_raw(ctx, service_id, field_name))
        return {"native_value": None if value is None else round(value * scale, 3)}

    return EntitySpec(
        platform="sensor",
        key=key,
        name=name,
        state=state,
        metadata=dict(metadata or {}),
    )


class ProductK1CNAdapter:
    prod_id = "K1CN"

    def entities(self, context: Any) -> tuple[EntitySpec, ...]:
        if not matches_product(context, self.prod_id):
            return ()

        specs: list[EntitySpec] = []

        for spec in (
            _sensor(
                context, "weekly", "deviceNum", "online_clients", "接入设备数",
                metadata={"icon": "mdi:devices", "state_class": "measurement"},
            ),
            _sensor(
                context, "weekly", "flow", "weekly_traffic", "本周流量",
                metadata={"icon": "mdi:chart-timeline-variant",
                          "unit": "GB", "state_class": "measurement"},
                scale=_FLOW_MB_TO_GB,
            ),
            _sensor(
                context, "weekly", "maxSpeed", "peak_speed", "最高速率",
                metadata={"icon": "mdi:speedometer", "unit": "Mbit/s"},
            ),
            _sensor(
                context, "lingxiaoAbility", "lingxiaoCount", "mesh_nodes", "子路由数量",
                metadata={"icon": "mdi:access-point-network"},
            ),
        ):
            if spec is not None:
                specs.append(spec)

        if context.has_service("stsSession") and _raw(context, "stsSession", "SSID"):
            specs.append(
                EntitySpec(
                    platform="sensor",
                    key="ssid",
                    name="Wi-Fi 名称",
                    state=lambda ctx: {"native_value": ctx.value("stsSession", "SSID")},
                    metadata={"icon": "mdi:wifi"},
                )
            )

        if context.has_service("stsSession") and _raw(context, "stsSession", "on") is not None:
            specs.append(
                EntitySpec(
                    platform="sensor",
                    key="ssid_enabled",
                    name="Wi-Fi 开启",
                    state=lambda ctx: {
                        "native_value": "开"
                        if bool_value(ctx.value("stsSession", "on"))
                        else "关"
                    },
                    metadata={"icon": "mdi:wifi-check"},
                )
            )

        # routerConfig 的写入会被云端回 200 但不落到设备（假 ACK，实测 IPv6 开关
        # 写后状态不变），因此只暴露只读状态，不提供开关控件。
        if context.has_service("routerConfig") and _raw(context, "routerConfig", "ipv6Switch") is not None:
            specs.append(
                EntitySpec(
                    platform="binary_sensor",
                    key="ipv6",
                    name="IPv6",
                    state=lambda ctx: {
                        "is_on": bool_value(ctx.value("routerConfig", "ipv6Switch"))
                    },
                    metadata={"icon": "mdi:ip-network"},
                )
            )

        if context.has_service("voiceReboot"):
            specs.append(
                EntitySpec(
                    platform="button",
                    key="reboot",
                    name="重启路由",
                    state=lambda _ctx: {},
                    metadata={"icon": "mdi:restart"},
                    actions={"press": _reboot},
                )
            )

        return tuple(specs)


ADAPTER: HuaweiProductAdapter = ProductK1CNAdapter()
