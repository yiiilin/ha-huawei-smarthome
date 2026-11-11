"""Generic Home Assistant notify entities for product adapters."""

from __future__ import annotations

from typing import Any

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity_helpers import AdapterEntityMixin, iter_specs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up adapter-declared notify entities."""

    del hass
    async_add_entities(
        HuaweiAdapterNotify(context, spec)
        for context, spec in iter_specs(entry.runtime_data, "notify")
    )


class HuaweiAdapterNotify(AdapterEntityMixin, NotifyEntity):
    """A notify entity that dispatches one adapter action."""

    def __init__(self, context: Any, spec: Any) -> None:
        self._init_adapter_entity(context, spec)

    async def async_send_message(
        self,
        message: str,
        title: str | None = None,
    ) -> None:
        """Send a message through the adapter-declared action."""

        del title
        if not message:
            raise ValueError("notify message must not be empty")
        await self._run_action("send_message", {"message": message})
