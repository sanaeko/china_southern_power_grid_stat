"""Import smoke test: load the integration modules against generated HA stubs.

Catches import-time errors (bad names, circular imports, typos evaluated at
class-definition time) without Home Assistant installed. Anything only used at
runtime is stubbed permissively.

Run with: python tests/import_smoke.py
"""

from __future__ import annotations

import importlib
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "custom_components", "china_southern_power_grid_stat")
PKG = "china_southern_power_grid_stat"


def make_base(name: str) -> type:
    """Create a permissive base class with a unique identity."""

    class Base:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, item):
            if item.startswith("__"):
                raise AttributeError(item)
            return None

    Base.__name__ = name
    return Base


class PermissiveModule(types.ModuleType):
    """Module returning a permissive class for any requested attribute."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        cls = make_base(name)
        setattr(self, name, cls)
        return cls


class _EnumMeta(type):
    """Metaclass where any attribute lookup returns its own name."""

    def __getattr__(cls, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return item


class EnumStub(metaclass=_EnumMeta):
    """Enum-like stub: ``Stub.ENERGY == "ENERGY"``."""

    def __init__(self, *args, **kwargs):
        pass


class EnumModule(PermissiveModule):
    """Module whose attributes are enum-like stubs."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        setattr(self, name, type(name, (EnumStub,), {}))
        return getattr(self, name)


def mod(name: str, **attrs) -> types.ModuleType:
    module = PermissiveModule(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def install_ha_stubs() -> None:
    mod("homeassistant")
    mod("homeassistant.core", HomeAssistant=make_base("HomeAssistant"), callback=lambda f: f)
    mod(
        "homeassistant.const",
        CONF_USERNAME="username",
        STATE_UNAVAILABLE="unavailable",
        UnitOfEnergy=type("UnitOfEnergy", (), {"KILO_WATT_HOUR": "kWh"}),
        Platform=type("Platform", (), {"SENSOR": "sensor", "CALENDAR": "calendar"}),
        EntityCategory=type("EntityCategory", (), {"DIAGNOSTIC": "diagnostic"}),
    )
    mod("homeassistant.exceptions", ConfigEntryAuthFailed=make_base("AuthFailed"))
    mod("homeassistant.components")
    sensor_mod = EnumModule("homeassistant.components.sensor")
    sensor_mod.SensorEntity = make_base("SensorEntity")
    sys.modules["homeassistant.components.sensor"] = sensor_mod
    mod("homeassistant.components.calendar", CalendarEntity=make_base("CalendarEntity"))
    mod("homeassistant.components.http", StaticPathConfig=make_base("StaticPathConfig"))
    mod("homeassistant.config_entries", ConfigEntry=make_base("ConfigEntry"))

    mod(
        "homeassistant.helpers.entity",
        DeviceInfo=type("DeviceInfo", (dict,), {}),
    )
    mod("homeassistant.helpers.entity_platform")
    mod("homeassistant.helpers.storage", Store=make_base("Store"))
    mod("homeassistant.helpers.entity_registry")
    mod("homeassistant.helpers.device_registry")
    mod(
        "homeassistant.helpers.update_coordinator",
        CoordinatorEntity=make_base("CoordinatorEntity"),
        DataUpdateCoordinator=make_base("DataUpdateCoordinator"),
    )
    helpers = mod(
        "homeassistant.helpers",
        entity=sys.modules["homeassistant.helpers.entity"],
        storage=sys.modules["homeassistant.helpers.storage"],
        update_coordinator=sys.modules["homeassistant.helpers.update_coordinator"],
    )
    del helpers


def install_package() -> None:
    """Register the component as an importable package without running __init__."""
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [PKG_DIR]
    # sensor.py does `from . import CONF_UPDATED_AT`.
    pkg.CONF_UPDATED_AT = "updated_at"
    sys.modules[PKG] = pkg

    const_mod = types.ModuleType(f"{PKG}.csg_client.const")
    login_type = type(
        "LoginType",
        (),
        {
            "LOGIN_TYPE_SMS": "sms",
            "LOGIN_TYPE_PWD_AND_SMS": "pwd_sms",
            "LOGIN_TYPE_CSG_QR": "csg_qr",
            "LOGIN_TYPE_WX_QR": "wx_qr",
            "LOGIN_TYPE_ALI_QR": "ali_qr",
        },
    )
    client = types.ModuleType(f"{PKG}.csg_client")
    client.__path__ = [os.path.join(PKG_DIR, "csg_client")]
    client.__package__ = PKG
    for name, value in {
        "JSON_KEY_METERING_POINT_NUMBER": "mpNumber",
        "WF_ATTR_CHARGE": "charge",
        "WF_ATTR_DATE": "date",
        "WF_ATTR_KWH": "kwh",
        "WF_ATTR_LADDER": "ladder",
        "WF_ATTR_LADDER_REMAINING_KWH": "ladder_remaining_kwh",
        "WF_ATTR_LADDER_START_DATE": "ladder_start_date",
        "WF_ATTR_LADDER_TARIFF": "ladder_tariff",
        "LoginType": login_type,
        "CSGAPIError": type("CSGAPIError", (Exception,), {}),
        "NotLoggedIn": type("NotLoggedIn", (Exception,), {}),
        "CSGClient": make_base("CSGClient"),
        "CSGElectricityAccount": make_base("CSGElectricityAccount"),
    }.items():
        setattr(client, name, value)
    sys.modules[f"{PKG}.csg_client"] = client
    del const_mod


def main() -> int:
    install_ha_stubs()
    install_package()

    failures = 0
    for name in ("const", "history", "sensor", "calendar"):
        try:
            importlib.import_module(f"{PKG}.{name}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"OK   {name}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
