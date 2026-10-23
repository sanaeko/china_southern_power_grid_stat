"""Tests for the calendar/back-fill helpers.

These load ``sensor.py``'s helper functions by extracting them, avoiding a full
Home Assistant import.
"""

from __future__ import annotations

import datetime
import os

import pytest

SENSOR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "custom_components",
    "china_southern_power_grid_stat",
    "sensor.py",
)


def _load_helpers():
    """Execute only the module-level date helpers from sensor.py."""
    from datetime import timedelta  # noqa: PLC0415

    source = open(SENSOR_PATH, encoding="utf-8").read()
    start = source.index("def _month_length(")
    end = source.index("async def async_setup_entry(")
    snippet = source[start:end]
    namespace = {
        "datetime": datetime,
        "timedelta": timedelta,
        "__name__": "sensor_helpers",
    }
    exec(compile(snippet, SENSOR_PATH, "exec"), namespace)  # noqa: S102
    return namespace


helpers = _load_helpers()
backfill_months = helpers["backfill_months"]
_month_length = helpers["_month_length"]
_next_month = helpers["_next_month"]


def d(text):
    return datetime.date.fromisoformat(text)


@pytest.mark.parametrize(
    "month,expected",
    [
        ("2024-01", 31),
        ("2024-02", 29),  # leap year
        ("2025-02", 28),
        ("2026-04", 30),
        ("2026-12", 31),
    ],
)
def test_month_length(month, expected):
    assert _month_length(d(f"{month}-01")) == expected


def test_next_month_handles_year_rollover():
    assert _next_month(d("2026-12-01")) == d("2027-01-01")
    assert _next_month(d("2026-01-31")) == d("2026-02-01")
    assert _next_month(d("2024-01-01")) == d("2024-02-01")


def test_backfill_window_covers_exactly_one_year():
    months = backfill_months(d("2026-10-23"), 12)
    assert len(months) == 12
    assert months[0] == d("2025-11-01")
    assert months[-1] == d("2026-10-01")
    # Strictly consecutive months, oldest first.
    for i in range(1, len(months)):
        assert months[i] == _next_month(months[i - 1])


@pytest.mark.parametrize("months", [1, 3, 12, 24])
def test_backfill_window_length(months):
    result = backfill_months(d("2026-10-23"), months)
    assert len(result) == months
    assert result[-1] == d("2026-10-01")


def test_backfill_window_across_year_boundary():
    months = backfill_months(d("2026-01-05"), 12)
    assert months[0] == d("2025-02-01")
    assert months[-1] == d("2026-01-01")
    assert len(months) == 12
