"""Unit tests for the pure history data layer."""

from __future__ import annotations

import datetime
import importlib.util
import os
import sys

import pytest

_COMPONENT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "custom_components",
    "china_southern_power_grid_stat",
)


def _load_history_module():
    """Import the standalone ``history`` module without the HA integration package.

    Importing ``custom_components.china_southern_power_grid_stat`` would pull in
    ``calendar.py``/``sensor.py`` and therefore Home Assistant itself, which is
    not available in a plain unit-test environment. ``history.py`` is written
    to be importable on its own, so load it directly from its file.
    """
    spec = importlib.util.spec_from_file_location(
        "csg_history", os.path.join(_COMPONENT_DIR, "history.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["csg_history"] = module
    spec.loader.exec_module(module)
    return module


history = _load_history_module()
AccountHistory = history.AccountHistory
DayRecord = history.DayRecord
HistoryStore = history.HistoryStore
MonthRecord = history.MonthRecord
parse_date = history.parse_date


class FakeStore:
    """Minimal stand-in for homeassistant.helpers.storage.Store."""

    def __init__(self, data=None):
        self.data = data
        self.saves = 0
        self.delayed = 0

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.saves += 1
        self.data = data

    def async_delay_save(self, data_func, delay=0):
        self.delayed += 1
        self.data = data_func()


def d(text: str) -> datetime.date:
    return datetime.date.fromisoformat(text)


def test_parse_date_variants():
    assert parse_date("2026-10-21") == d("2026-10-21")
    assert parse_date("2026-10-21 00:00:00") == d("2026-10-21")
    assert parse_date("2026-10-21T00:00:00") == d("2026-10-21")
    assert parse_date(datetime.datetime(2026, 10, 21, 13, 5)) == d("2026-10-21")
    assert parse_date("not-a-date") is None
    assert parse_date(None) is None
    assert parse_date(12345) is None


def test_merge_days_tracks_changes_and_never_blanks_values():
    h = AccountHistory()
    assert h.merge_days([(d("2026-10-21"), 58.45, 35.07)]) is True
    assert h.days["2026-10-21"] == DayRecord(kwh=58.45, cost=35.07)

    # Re-merging identical data reports no change.
    assert h.merge_days([(d("2026-10-21"), 58.45, 35.07)]) is False

    # A polling gap (None) must not erase an existing reading.
    assert h.merge_days([(d("2026-10-21"), None, None)]) is False
    assert h.days["2026-10-21"].kwh == 58.45

    # A genuine correction is applied.
    assert h.merge_days([(d("2026-10-21"), 60.0, None)]) is True
    assert h.days["2026-10-21"].kwh == 60.0
    assert h.days["2026-10-21"].cost == 35.07


def test_rebuild_months_sums_daily_values():
    h = AccountHistory()
    h.merge_days(
        [
            (d("2026-09-01"), 10.0, 5.0),
            (d("2026-09-02"), 20.0, 10.0),
            (d("2026-09-03"), 0.0, 0.0),
        ]
    )
    h.rebuild_months(today=d("2026-10-23"))
    assert h.months["2026-09"].kwh == 30.0
    assert h.months["2026-09"].cost == 15.0
    assert h.months["2026-09"].days == 3
    assert h.months["2026-09"].partial is False


def test_rebuild_months_keeps_larger_reported_total_as_partial():
    """When daily data is missing, keep the API's authoritative total."""
    h = AccountHistory()
    h.merge_days([(d("2026-08-01"), 10.0, 5.0)])
    h.merge_month("2026-08", 442.63, 122.56)
    h.rebuild_months(today=d("2026-10-23"))
    assert h.months["2026-08"].kwh == 442.63
    assert h.months["2026-08"].cost == 122.56
    assert h.months["2026-08"].partial is True


def test_current_month_is_partial():
    h = AccountHistory()
    h.merge_days([(d("2026-10-01"), 10.0, 5.0)])
    h.rebuild_months(today=d("2026-10-23"))
    assert h.months["2026-10"].partial is True


def test_days_without_kwh_are_not_counted_in_sums():
    h = AccountHistory()
    h.merge_days([(d("2026-09-01"), None, 3.0), (d("2026-09-02"), 5.0, None)])
    h.rebuild_months(today=d("2026-10-23"))
    # Only the day with a kWh reading contributes to the totals.
    assert h.months["2026-09"].kwh == 5.0
    assert h.months["2026-09"].days == 1


def test_compact_daily_series_shape_and_gaps():
    """Only days with a reading are emitted, as short [date, kwh, cost?] rows."""
    h = AccountHistory()
    h.merge_days([(d("2026-09-01"), 1.0, 0.5), (d("2026-09-03"), 3.0, None)])
    h.merge_days([(d("2026-09-02"), None, 9.9)])  # cost only, no kWh

    rows = h.compact_daily_series()
    assert rows == [
        ["2026-09-01", 1.0, 0.5],
        ["2026-09-03", 3.0],
    ]


def test_compact_daily_series_stays_under_attribute_limit():
    """A full year must fit in Home Assistant's 16 KB attribute limit."""
    import json

    h = AccountHistory()
    start = d("2025-10-23")
    for offset in range(400):
        day = start + datetime.timedelta(days=offset)
        h.merge_days([(day, 55.12, 33.45)])
    h.rebuild_months(d("2026-10-23"))

    payload = {
        "daily": h.compact_daily_series(),
        "monthly": h.monthly_series(24),
        "yearly": h.yearly_series(),
    }
    size = len(json.dumps(payload, separators=(",", ":")).encode())
    assert size < 16384, f"attribute payload {size} bytes exceeds the 16 KB limit"


def test_monthly_and_yearly_series():
    h = AccountHistory()
    h.merge_days([(d("2025-11-01"), 100.0, 50.0), (d("2026-01-01"), 200.0, 100.0)])
    h.merge_days([(d("2026-10-01"), 5.0, 2.0)])
    h.rebuild_months(today=d("2026-10-23"))

    monthly = h.monthly_series(months=12)
    assert [m["month"] for m in monthly] == ["2025-11", "2026-01", "2026-10"]

    yearly = h.yearly_series()
    assert [y["year"] for y in yearly] == ["2025", "2026"]
    assert yearly[0]["kwh"] == 100.0
    assert yearly[1]["kwh"] == 205.0
    assert yearly[1]["months"] == 2


def test_prune_retention_window():
    h = AccountHistory()
    today = d("2026-10-23")
    h.merge_days(
        [
            (today - datetime.timedelta(days=500), 1.0, None),  # too old
            (today - datetime.timedelta(days=100), 2.0, None),  # kept
            (today, 3.0, None),  # kept
        ]
    )
    h.months["2020-01"] = MonthRecord(kwh=1, days=1)
    h.rebuild_months(today=today)
    changed = h.prune(today)
    assert changed is True
    assert len(h.days) == 2
    assert "2020-01" not in h.months


def test_roundtrip_serialisation():
    h = AccountHistory()
    h.merge_days([(d("2026-09-01"), 10.0, 5.0)])
    h.rebuild_months(today=d("2026-10-23"))
    h.updated = "2026-10-23T09:35:17+08:00"
    h.backfilled = True

    restored = AccountHistory.from_dict(h.to_dict())
    assert restored.days == h.days
    assert restored.months == h.months
    assert restored.updated == h.updated
    assert restored.backfilled is True


def test_backfilled_defaults_to_false_for_legacy_data():
    """Histories written before the flag existed must trigger a back-fill."""
    restored = AccountHistory.from_dict(
        {"days": {"2026-09-01": {"kwh": 1.0, "cost": None}}}
    )
    assert restored.backfilled is False


def test_from_dict_tolerates_corrupt_data():
    restored = AccountHistory.from_dict(
        {
            "days": {"bad-key": {"kwh": 1}, "2026-09-01": "garbage"},
            "months": {"2026-09": {"kwh": "12.5", "cost": None, "days": "2"}},
            "updated": 123,
        }
    )
    assert "bad-key" not in restored.days
    assert restored.days["2026-09-01"] == DayRecord()
    assert restored.months["2026-09"].kwh == 12.5
    assert restored.months["2026-09"].days == 2
    assert restored.updated is None
    assert AccountHistory.from_dict(None).days == {}


def test_latest_day_skips_entries_without_kwh():
    h = AccountHistory()
    h.merge_days([(d("2026-10-20"), 5.0, None), (d("2026-10-21"), None, None)])
    assert h.latest_day() == ("2026-10-20", DayRecord(kwh=5.0))
    assert AccountHistory().latest_day() is None


@pytest.mark.asyncio
async def test_history_store_load_save_and_delay():
    seeded = {"acc": {"days": {"2026-09-01": {"kwh": 1.0, "cost": 0.5}}}}
    fake = FakeStore(seeded)
    store = HistoryStore(fake)

    await store.async_load()
    assert store.get("acc").days["2026-09-01"].kwh == 1.0
    # Second load is a no-op and must not clobber in-memory changes.
    store.get("acc").merge_days([(d("2026-09-02"), 2.0, 1.0)])
    await store.async_load()
    assert "2026-09-02" in store.get("acc").days

    await store.async_save()
    assert fake.saves == 1
    assert fake.data["acc"]["days"]["2026-09-02"]["kwh"] == 2.0

    store.async_delay_save()
    assert fake.delayed == 1


@pytest.mark.asyncio
async def test_history_store_handles_empty_storage():
    store = HistoryStore(FakeStore(None))
    await store.async_load()
    assert store.accounts == {}
    assert store.get("new").days == {}


def _window_is_current(history, today, max_age_days=40):
    """Mirror of CSGCoordinator._history_window_is_current."""
    latest = history.latest_day()
    if latest is None:
        return False
    latest_date = parse_date(latest[0])
    if latest_date is None:
        return False
    return (today - latest_date).days <= max_age_days


def test_window_is_current_for_fresh_data():
    h = AccountHistory()
    h.merge_days([(d("2026-10-21"), 5.0, None)])
    assert _window_is_current(h, d("2026-10-23")) is True


def test_window_is_stale_after_a_long_gap():
    """A long offline period must trigger a re-fetch instead of silently skipping."""
    h = AccountHistory()
    h.merge_days([(d("2026-08-01"), 5.0, None)])
    assert _window_is_current(h, d("2026-10-23")) is False


def test_window_is_stale_for_empty_history():
    assert _window_is_current(AccountHistory(), d("2026-10-23")) is False
