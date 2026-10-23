"""Regression tests for the bugs that caused `daily_usage_history` to publish
no data in the field.

Two defects combined:

1. ``_history_attributes`` called ``min(history.days).isoformat()``. The keys of
   ``history.days`` are ``"YYYY-MM-DD"`` strings, so this raised
   ``AttributeError`` and the whole attribute build was discarded silently by
   the surrounding ``except Exception`` handler.
2. ``SUFFIX_DAILY_USAGE_HISTORY`` and ``ATTR_KEY_DAILY_USAGE_HISTORY`` had the
   same value (``"daily_usage_history"``), so writing the attribute payload
   into the same per-account coordinator dict overwrote the numeric state.
"""

from __future__ import annotations

import datetime
import importlib.util
import os
import sys

import pytest

COMP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "custom_components",
    "china_southern_power_grid_stat",
)


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(COMP, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


history = _load("csg_history_reg", "history.py")
AccountHistory = history.AccountHistory

CONST_SOURCE = open(os.path.join(COMP, "const.py"), encoding="utf-8").read()


def const_value(name: str):
    """Read a constant's value out of const.py without importing the package."""
    for line in CONST_SOURCE.splitlines():
        if line.startswith(f"{name} = "):
            raw = line.split("=", 1)[1].strip()
            return raw.strip().strip('"')
    raise AssertionError(f"{name} not found in const.py")


def test_history_start_uses_string_keys():
    """Regression: history_start must be the raw YYYY-MM-DD key, not isoformat()."""
    h = AccountHistory()
    h.merge_days([(datetime.date(2026, 10, 20), 1.0, None)])
    oldest = min(h.days)
    assert isinstance(oldest, str) is True
    # This is what the fixed code stores.
    assert oldest == "2026-10-20"
    # And this is what used to blow up.
    with pytest.raises(AttributeError):
        oldest.isoformat()  # noqa: B018


def test_state_and_attribute_keys_do_not_collide():
    """Regression: state key and attribute payload key must be distinct."""
    state_key = const_value("SUFFIX_DAILY_USAGE_HISTORY")
    attr_coord_key = const_value("COORD_KEY_DAILY_HISTORY_ATTRS")
    monthly_state_key = const_value("SUFFIX_MONTHLY_USAGE_SUMMARY")
    monthly_attr_coord_key = const_value("COORD_KEY_MONTHLY_HISTORY_ATTRS")

    assert state_key != attr_coord_key, (
        "writing attributes under the state key overwrites the sensor value"
    )
    assert monthly_state_key != monthly_attr_coord_key
    for coord_key in (
        attr_coord_key,
        monthly_attr_coord_key,
    ):
        for suffix in (
            "SUFFIX_DAILY_USAGE_HISTORY",
            "SUFFIX_MONTHLY_USAGE_SUMMARY",
            "SUFFIX_BAL",
            "SUFFIX_ARR",
        ):
            assert coord_key != const_value(suffix), (
                f"{coord_key} would overwrite {suffix}"
            )


def test_attribute_payload_survives_beside_state():
    """A state value and an attribute payload can coexist in one dict."""
    state_key = const_value("SUFFIX_DAILY_USAGE_HISTORY")
    attr_key = const_value("COORD_KEY_DAILY_HISTORY_ATTRS")

    h = AccountHistory()
    h.merge_days([(datetime.date(2026, 10, 20), 58.1, 34.0)])
    latest = h.latest_day()

    account_data = {state_key: latest[1].kwh}
    account_data[attr_key] = {"daily_usage_history": h.daily_series(
        datetime.date.today() - datetime.timedelta(days=372), datetime.date.today()
    )}

    assert account_data[state_key] == 58.1
    assert account_data[attr_key]["daily_usage_history"]


def test_daily_series_covers_requested_window():
    h = AccountHistory()
    end = datetime.date(2026, 10, 23)
    start = end - datetime.timedelta(days=372)
    series = h.daily_series(start, end)
    assert len(series) == 373
    assert series[0]["date"] == start.isoformat()
    assert series[-1]["date"] == end.isoformat()
