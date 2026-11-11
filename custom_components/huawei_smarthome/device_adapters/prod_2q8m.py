"""Read-only MH3 Pro (2Q8M) presence, light and battery reporting.

Mappings follow this product's Profile. Light levels use its Chinese enum
labels, which differ from BER-SE11. No unit is assumed for the raw light
reading. Configuration, self-check and reset commands are not exposed.
"""
from .api import EntitySpec

_LEVELS = {1: "暗光", 2: "微光", 3: "弱光", 4: "适中", 5: "较强", 6: "很强"}


def _flag(sid, field):
    def state(context):
        value = context.value(sid, field)
        valid = type(value) in (bool, int) and value in (0, 1)
        return {"is_on": bool(value) if valid else None}
    return state


def _integer(sid, field, minimum, maximum):
    def state(context):
        value = context.value(sid, field)
        valid = type(value) is int and minimum <= value <= maximum
        return {"native_value": value if valid else None}
    return state


def _level(context):
    value = context.value("luminance", "level")
    return {"native_value": _LEVELS.get(value) if type(value) is int else None}


class ProductAdapter:
    prod_id = "2Q8M"

    def entities(self, context):
        if (context.prod_id or "").casefold() != self.prod_id.casefold():
            return ()
        return (
            EntitySpec(
                platform="binary_sensor", key="presence", name="人员存在",
                state=_flag("pir", "status"),
                metadata={"device_class": "occupancy"},
            ),
            EntitySpec(
                platform="sensor", key="illuminance", name="光照读数",
                state=_integer("luminance", "current", 0, 65535),
                metadata={"state_class": "measurement"},
            ),
            EntitySpec(
                platform="sensor", key="illuminance_level", name="光照度等级",
                state=_level,
            ),
            EntitySpec(
                platform="sensor", key="battery", name="电池电量",
                state=_integer("battery", "level", 1, 100),
                metadata={"device_class": "battery", "unit": "%",
                          "state_class": "measurement", "entity_category": "diagnostic"},
            ),
            EntitySpec(
                platform="binary_sensor", key="battery_low", name="低电量告警",
                state=_flag("battery", "alarm"),
                metadata={"device_class": "battery", "entity_category": "diagnostic"},
            ),
        )


ADAPTER = ProductAdapter()
