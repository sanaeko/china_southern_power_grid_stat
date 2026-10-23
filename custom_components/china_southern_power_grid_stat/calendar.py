"""Calendar entity exposing daily electricity usage.

Each day with a reading becomes an all-day calendar event, so the history can
be browsed in Home Assistant's Calendar panel / dashboard alongside other
events. Events are rendered from the coordinator's persisted history and do
not require any extra API calls.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ELE_ACCOUNTS, DOMAIN

_LOGGER = logging.getLogger(__name__)

#: Calendar events are generated for at most this many past days per request,
#: to keep a very wide dashboard range from producing huge responses.
MAX_EVENT_DAYS = 400


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the usage calendar entities."""
    if not config_entry.data.get(CONF_ELE_ACCOUNTS):
        _LOGGER.debug("No ele accounts in config, skipping calendar setup")
        return

    from .sensor import async_get_coordinator  # noqa: PLC0415 - avoid circular import

    coordinator = await async_get_coordinator(hass, config_entry)
    entities = [
        CSGDailyUsageCalendar(coordinator, account_number)
        for account_number in config_entry.data[CONF_ELE_ACCOUNTS]
    ]
    async_add_entities(entities)


class CSGDailyUsageCalendar(CoordinatorEntity, CalendarEntity):
    """A calendar where each day's electricity usage is one all-day event."""

    _attr_icon = "mdi:calendar-chart"

    def __init__(self, coordinator, account_number: str) -> None:
        super().__init__(coordinator)
        self._account_number = account_number
        self._attr_unique_id = f"{DOMAIN}.{account_number}.usage_calendar"
        self._attr_name = f"{account_number}-usage_calendar"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._account_number)},
            name=f"CSGAccount-{self._account_number}",
            manufacturer="CSG",
            model="CSG Virtual Electricity Meter",
        )

    def _history(self):
        history = getattr(self.coordinator, "_history", None)
        if history is None:
            return None
        return history.get(self._account_number)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the most recent usage day as the current event."""
        history = self._history()
        if history is None:
            return None
        latest = history.latest_day()
        if latest is None:
            return None
        day_key, record = latest
        return self._event_for(day_key, record)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return one all-day event per day with usage in the range."""
        history = self._history()
        if history is None:
            return []

        start = start_date.date()
        end = end_date.date()
        # The calendar view passes an exclusive end; treat it inclusively here
        # so a request covering exactly one day still returns that day.
        if (end - start).days > MAX_EVENT_DAYS:
            start = end - datetime.timedelta(days=MAX_EVENT_DAYS)

        events: list[CalendarEvent] = []
        for day_key, record in sorted(history.days.items()):
            day = datetime.date.fromisoformat(day_key)
            if day < start or day > end:
                continue
            if record.kwh is None:
                continue
            events.append(self._event_for(day_key, record))
        return events

    def _event_for(self, day_key: str, record: Any) -> CalendarEvent:
        """Build the all-day event describing one day's usage."""
        day = datetime.date.fromisoformat(day_key)
        summary = f"用电 {record.kwh:g} kWh"
        parts = [f"用电量: {record.kwh:g} kWh"]
        if record.cost is not None:
            parts.append(f"电费: {record.cost:g} 元")
        return CalendarEvent(
            start=day,
            end=day,
            summary=summary,
            description="\n".join(parts),
            uid=f"csg-{self._account_number}-{day_key}",
        )
