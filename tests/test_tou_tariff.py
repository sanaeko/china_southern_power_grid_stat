"""Tests for the time-of-use charge estimate."""

from __future__ import annotations

import datetime
import importlib.util
import os
import re
import sys

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


history = _load("csg_history_tou", "history.py")
AccountHistory = history.AccountHistory
estimate_cost = history.estimate_cost

CONST_SOURCE = open(os.path.join(COMP, "const.py"), encoding="utf-8").read()

_rates_ns = {}
_tou_rates = re.search(r"^TOU_RATES = \{(.*?)\}", CONST_SOURCE, re.S | re.M).group(1)
_rates_ns.update(eval(f"{{{_tou_rates}}}"))  # noqa: S307
TOU_RATES = _rates_ns
# ESTIMATE_RATE is defined as TOU_RATES["valley"]; resolve it from the rates.
assert 'ESTIMATE_RATE = TOU_RATES["valley"]' in CONST_SOURCE
ESTIMATE_RATE = TOU_RATES["valley"]

TOU_PERIODS = [
    (p, int(a), int(b))
    for p, a, b in re.findall(
        r'\("(\w+)", (\d+), (\d+)\)',
        re.search(r"^TOU_PERIODS.*?= \((.*?)^\)", CONST_SOURCE, re.S | re.M).group(1),
    )
]


def d(text):
    return datetime.date.fromisoformat(text)


def test_tariff_values_match_the_supplied_price_list():
    assert TOU_RATES == {"peak": 1.012, "valley": 0.233, "flat": 0.599}


def test_estimate_uses_the_valley_rate():
    assert ESTIMATE_RATE == 0.233


def test_tou_periods_cover_every_hour_exactly_once():
    """The periods must tile the day 0-24 with no gap or overlap."""
    assert TOU_PERIODS[0][1] == 0
    assert TOU_PERIODS[-1][2] == 24
    for (_, _, end), (_, start, _) in zip(
        TOU_PERIODS, TOU_PERIODS[1:], strict=False
    ):
        assert end == start, "periods must be contiguous"
    covered = sum(end - start for _, start, end in TOU_PERIODS)
    assert covered == 24


def test_tou_periods_match_the_stated_schedule():
    """峰 10-12,14-19 | 谷 0-8 | 平 8-10,12-14,19-24."""
    by_period = {}
    for period, start, end in TOU_PERIODS:
        by_period.setdefault(period, []).append((start, end))
    assert by_period["valley"] == [(0, 8)]
    assert by_period["peak"] == [(10, 12), (14, 19)]
    assert by_period["flat"] == [(8, 10), (12, 14), (19, 24)]


def test_estimate_cost_is_rounded_and_handles_missing_values():
    assert estimate_cost(100.0, 0.233) == 23.3
    assert estimate_cost(49.02, 0.233) == 11.42
    assert estimate_cost(None, 0.233) is None
    assert estimate_cost(0.0, 0.233) == 0.0


def test_estimated_costs_for_latest_day_and_month():
    h = AccountHistory()
    h.merge_days([(d("2026-09-30"), 100.0, None), (d("2026-10-21"), 50.0, None)])
    h.rebuild_months(d("2026-10-23"))

    costs = h.estimated_costs(ESTIMATE_RATE)
    # Latest day overall is 2026-10-21.
    assert costs["day_date"] == "2026-10-21"
    assert costs["day"] == 11.65  # 50 * 0.233
    # Latest month is 2026-10, sum of its days.
    assert costs["month_key"] == "2026-10"
    assert costs["month"] == 11.65


def test_estimated_costs_on_empty_history():
    costs = AccountHistory().estimated_costs(ESTIMATE_RATE)
    assert costs == {
        "day": None,
        "day_date": None,
        "month": None,
        "month_key": None,
    }


def test_estimate_is_a_lower_bound_for_real_bills():
    """Sanity check against real bills: valley rate must under-estimate.

    Real per-kWh averages observed for this account were 0.27-0.30 CNY, i.e.
    above the valley rate, so the estimate must be below the real charge.
    """
    month_kwh, real_charge = 571.31, 169.26
    assert month_kwh * ESTIMATE_RATE < real_charge
