# -*- coding: utf-8 -*-
"""The China Southern Power Grid Statistics integration."""
from __future__ import annotations

import logging
import time

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    CARD_URL,
    CONF_AUTH_TOKEN,
    CONF_ELE_ACCOUNTS,
    CONF_LOGIN_TYPE,
    CONF_UPDATED_AT,
    DOMAIN,
    URL_BASE,
)
from .csg_client import (
    CSGClient,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up China Southern Power Grid Statistics from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # validate session, re-authenticate if needed
    client = CSGClient.load(
        {
            CONF_AUTH_TOKEN: entry.data[CONF_AUTH_TOKEN],
        }
    )
    if not await hass.async_add_executor_job(
        client.verify_login
    ):
        raise ConfigEntryAuthFailed(
            "Login expired"
        )

    await hass.async_add_executor_job(
        client.initialize
    )

    hass.data[DOMAIN].setdefault(entry.entry_id, {})["client"] = client

    await _async_register_card(hass)

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS
    )

    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and register it as a resource.

    Registration is idempotent: the static path and the resource are only
    added once, even though this runs per config entry. Failures are logged
    and never prevent the integration itself from loading.
    """
    if hass.data[DOMAIN].get("card_registered"):
        return
    hass.data[DOMAIN]["card_registered"] = True

    try:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    URL_BASE,
                    hass.config.path("custom_components", DOMAIN, "frontend"),
                    cache_headers=True,
                )
            ]
        )
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to register the usage card static path")
        return

    try:
        from homeassistant.components.lovelace.const import (  # noqa: PLC0415
            LOVELACE_DATA,
        )

        lovelace_data = hass.data.get(LOVELACE_DATA)
        resources = getattr(lovelace_data, "resources", None)
        if resources is None:
            _LOGGER.debug("Lovelace not available, card must be added manually")
            return
        # YAML resource collections are read-only lists.
        if not hasattr(resources, "async_create_item"):
            _LOGGER.info(
                "Lovelace uses YAML resources; add %s manually under "
                "lovelace.resources in configuration.yaml",
                CARD_URL,
            )
            return

        await resources.async_load()
        existing = {item.get("url") for item in resources.async_items()}
        if CARD_URL in existing:
            return
        await resources.async_create_item({"res_type": "module", "url": CARD_URL})
        _LOGGER.info("Registered Lovelace resource %s", CARD_URL)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.warning(
            "Could not auto-register the usage card; add it manually under "
            "Settings > Dashboards > Resources with URL %s",
            CARD_URL,
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(f"Unloading entry: {entry.title}")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    _LOGGER.debug(f"Unload platforms for entry: {entry.title}, success: {unload_ok}")
    entry_data = hass.data[DOMAIN].pop(entry.entry_id, {}) or {}
    coordinator = entry_data.get("coordinator")
    backfill_task = getattr(coordinator, "_backfill_task", None)
    if backfill_task is not None and not backfill_task.done():
        backfill_task.cancel()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove device"""
    _LOGGER.info(f"removing device {device_entry.name}")
    account_num = list(device_entry.identifiers)[0][1]

    # remove entities
    entity_reg = entity_registry.async_get(hass)
    entities = {
        ent.unique_id: ent.entity_id
        for ent in entity_registry.async_entries_for_config_entry(
            entity_reg, config_entry.entry_id
        )
        if account_num in ent.unique_id
    }
    for entity_id in entities.values():
        entity_reg.async_remove(entity_id)

    # update config entry
    new_data = config_entry.data.copy()
    new_data[CONF_ELE_ACCOUNTS].pop(account_num)
    new_data[CONF_UPDATED_AT] = str(int(time.time() * 1000))
    hass.config_entries.async_update_entry(
        config_entry,
        data=new_data,
    )
    _LOGGER.info(
        "Removed ele account from %s: %s",
        config_entry.data[CONF_USERNAME],
        account_num,
    )
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    _LOGGER.info("Removing entry: account %s", entry.data[CONF_USERNAME])

    # logout
    def client_logout():
        client = CSGClient.load(
            {
                CONF_AUTH_TOKEN: entry.data[CONF_AUTH_TOKEN],
            }
        )
        if client.verify_login():
            client.logout(entry.data[CONF_LOGIN_TYPE])
            _LOGGER.info("CSG account %s logged out", entry.data[CONF_USERNAME])

    await hass.async_add_executor_job(client_logout)
