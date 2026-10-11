"""Profile-aware helpers for narrowly scoped product adapters."""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any


def matches_product(context: Any, prod_id: str) -> bool:
    """Require both the discovered product and downloaded Profile to agree."""

    profile = getattr(context, "profile", None)
    actual = getattr(context, "prod_id", None)
    if not isinstance(profile, Mapping) or not isinstance(actual, str):
        return False
    if actual.casefold() != prod_id.casefold():
        return False
    profile_id = profile.get("prodId")
    return isinstance(profile_id, str) and profile_id.casefold() == prod_id.casefold()


def profile_field(context: Any, sid: str, name: str) -> Mapping[str, Any] | None:
    """Return one characteristic only when its structure is valid."""

    profile = getattr(context, "profile", None)
    services = profile.get("services") if isinstance(profile, Mapping) else None
    if not isinstance(services, list):
        return None
    for service in services:
        if not isinstance(service, Mapping) or service.get("serviceId") != sid:
            continue
        characteristics = service.get("characteristics")
        if not isinstance(characteristics, list):
            return None
        for characteristic in characteristics:
            if (
                isinstance(characteristic, Mapping)
                and characteristic.get("characteristicName") == name
            ):
                return characteristic
    return None


def can_read(context: Any, sid: str, name: str) -> bool:
    field = profile_field(context, sid, name)
    method = field.get("method") if field else None
    return isinstance(method, str) and "R" in method.upper()


def can_write(context: Any, sid: str, name: str) -> bool:
    field = profile_field(context, sid, name)
    method = field.get("method") if field else None
    return isinstance(method, str) and "W" in method.upper()


def bool_value(value: Any) -> bool | None:
    """Decode common Huawei boolean wire representations without guessing."""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in (0, 1):
            return bool(value)
        return None
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "on", "open"}:
            return True
        if normalized in {"0", "false", "off", "close"}:
            return False
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def read_number(
    context: Any,
    sid: str,
    name: str,
    *,
    display_scale: float = 1.0,
) -> float | None:
    """Read a numeric state, scale it, then validate logical Profile bounds."""

    field = profile_field(context, sid, name)
    if field is None or not can_read(context, sid, name):
        return None
    scale = _number(display_scale)
    raw = _number(context.value(sid, name))
    if scale is None or scale <= 0 or raw is None:
        return None
    value = raw * scale
    minimum = _number(field.get("min"))
    maximum = _number(field.get("max"))
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return round(value, 6)


def enum_entries(context: Any, sid: str, name: str) -> tuple[Mapping[str, Any], ...]:
    field = profile_field(context, sid, name)
    values = field.get("enumList") if field else None
    if not isinstance(values, list):
        return ()
    return tuple(item for item in values if isinstance(item, Mapping) and "enumVal" in item)


def enum_label(context: Any, sid: str, name: str, value: Any) -> str | None:
    if value is None:
        return None
    for item in enum_entries(context, sid, name):
        if str(item.get("enumVal")) == str(value):
            label = item.get("descCh")
            return label if isinstance(label, str) else None
    return None


def enum_value_for_label(
    context: Any,
    sid: str,
    name: str,
    label: str,
) -> Any | None:
    for item in enum_entries(context, sid, name):
        if item.get("descCh") == label:
            return item.get("enumVal")
    return None


def number_metadata(context: Any, sid: str, name: str) -> dict[str, float | int] | None:
    """Build HA numeric bounds from a writable numeric Profile field."""

    field = profile_field(context, sid, name)
    if field is None or not can_write(context, sid, name):
        return None
    minimum = _number(field.get("min"))
    maximum = _number(field.get("max"))
    if minimum is None or maximum is None or minimum > maximum:
        return None
    step = _number(field.get("step"))
    if step is None:
        kind = str(field.get("characteristicType", "")).casefold()
        step = 1.0 if kind == "int" else 0.1
    if step <= 0:
        return None
    return {
        "min": _integer_if_whole(minimum),
        "max": _integer_if_whole(maximum),
        "step": _integer_if_whole(step),
    }


def _integer_if_whole(value: float) -> float | int:
    return int(value) if value.is_integer() else value


def _canonical_enum(field: Mapping[str, Any], value: Any) -> Any:
    values = field.get("enumList")
    if not isinstance(values, list):
        raise ValueError("Profile enum has no allowed values")
    for item in values:
        if isinstance(item, Mapping) and str(item.get("enumVal")) == str(value):
            return _canonical_wire_value(field, item.get("enumVal"))
    raise ValueError(f"value is not allowed by Profile enum: {value!r}")


def _canonical_wire_value(field: Mapping[str, Any], value: Any) -> Any:
    kind = str(field.get("characteristicType", "")).casefold()
    if kind in {"bool", "enum", "int"}:
        numeric = _number(value)
        if numeric is not None and numeric.is_integer():
            return int(numeric)
    return value


def _validate_logical_number(
    field: Mapping[str, Any],
    value: float,
    *,
    step_override: float | None = None,
) -> None:
    minimum = _number(field.get("min"))
    maximum = _number(field.get("max"))
    if minimum is not None and value < minimum:
        raise ValueError(f"value {value} is below Profile minimum {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"value {value} is above Profile maximum {maximum}")
    step = _number(step_override) if step_override is not None else _number(field.get("step"))
    if step is None and str(field.get("characteristicType", "")).casefold() == "int":
        step = 1.0
    if step is not None and step > 0:
        origin = minimum or 0.0
        steps = (value - origin) / step
        if not math.isclose(steps, round(steps), abs_tol=1e-6):
            raise ValueError(f"value {value} does not match Profile step {step}")


async def send_profile_value(
    context: Any,
    sid: str,
    name: str,
    value: Any,
    *,
    wire_multiplier: float = 1.0,
    step_override: float | None = None,
) -> None:
    """Validate a command against Profile permissions, range, step and enum."""

    field = profile_field(context, sid, name)
    if field is None or not can_write(context, sid, name):
        raise ValueError(f"Profile does not permit writing {sid}.{name}")
    multiplier = _number(wire_multiplier)
    if multiplier is None or multiplier <= 0:
        raise ValueError("wire_multiplier must be a positive finite number")
    kind = str(field.get("characteristicType", "")).casefold()

    if kind == "bool":
        boolean = bool_value(value)
        if boolean is None:
            raise ValueError(f"invalid boolean value: {value!r}")
        canonical = _canonical_enum(field, int(boolean)) if field.get("enumList") else int(boolean)
        wire_value = canonical
    elif kind == "enum":
        wire_value = _canonical_enum(field, value)
    elif kind in {"int", "float", "double", "number"}:
        logical = _number(value)
        if logical is None:
            raise ValueError(f"invalid numeric value: {value!r}")
        _validate_logical_number(field, logical, step_override=step_override)
        raw = logical * multiplier
        if kind == "int":
            if not math.isclose(raw, round(raw), abs_tol=1e-6):
                raise ValueError(f"encoded value {raw} is not an integer")
            wire_value = int(round(raw))
        else:
            wire_value = round(raw, 6)
    elif kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"invalid string value: {value!r}")
        wire_value = _canonical_enum(field, value) if field.get("enumList") else value
    else:
        raise ValueError(f"unsupported Profile characteristic type: {kind!r}")

    await context.async_send_service(sid, {name: wire_value})
