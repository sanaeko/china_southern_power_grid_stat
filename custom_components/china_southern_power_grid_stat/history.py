"""Persistent daily usage history for the China Southern Power Grid integration.

This module is deliberately free of Home Assistant runtime dependencies (apart
from the generic ``Store`` helper which is injected by the caller) so that the
data handling logic can be unit tested in isolation.

Stored layout::

    {
        "<account_number>": {
            "days": {
                "2026-10-21": {"kwh": 58.45, "cost": 35.07},
                ...
            },
            "months": {
                "2026-10": {"kwh": 328.33, "cost": 200.42},
                ...
            },
            "updated": "2026-10-23T09:35:17+08:00",
        }
    }

Keys are ``YYYY-MM-DD`` for days and ``YYYY-MM`` for months. Values are
normalised to ``float`` where available, and ``None`` when the upstream API
reported the field as missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

DATE_FORMAT = "%Y-%m-%d"
MONTH_FORMAT = "%Y-%m"

#: How many days of daily data are retained per account (1 year + slack for
#: leap days and the trailing "today"/"yesterday" overlap).
MAX_DAYS = 400

#: How many months of monthly aggregates are retained per account.
MAX_MONTHS = 25


def parse_date(value: Any) -> date | None:
    """Parse an API date string into a ``date``, or ``None`` if invalid."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    # The CSG API returns e.g. ``2026-10-21``. Be tolerant about a trailing
    # time component in case the format changes upstream.
    if len(text) > 10 and text[10] in (" ", "T"):
        text = text[:10]
    try:
        return datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        return None


def month_key(day: date) -> str:
    """Return the ``YYYY-MM`` bucket key for a date."""
    return day.strftime(MONTH_FORMAT)


def _as_float(value: Any) -> float | None:
    """Convert an API value to float, returning ``None`` when not numeric."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def estimate_cost(kwh: float | None, rate: float) -> float | None:
    """Estimate a charge from a consumption figure.

    The CSG API does not expose how a day's consumption splits across the
    time-of-use periods, so this is a lower-bound estimate: the caller passes
    the valley rate, the cheapest period.
    """
    if kwh is None:
        return None
    return round(kwh * rate, 2)


@dataclass
class DayRecord:
    """One day's consumption."""

    kwh: float | None = None
    cost: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        return {"kwh": self.kwh, "cost": self.cost}

    @classmethod
    def from_dict(cls, data: Any) -> DayRecord:
        if not isinstance(data, dict):
            return cls()
        return cls(kwh=_as_float(data.get("kwh")), cost=_as_float(data.get("cost")))


@dataclass
class MonthRecord:
    """Aggregates for a calendar month.

    ``days`` counts how many daily records contributed to the sums. ``partial``
    is ``True`` when the month is the current one (or when the monthly total
    reported by the API is larger than the sum of the daily values we hold),
    meaning the sums should be shown as "so far".
    """

    kwh: float = 0.0
    cost: float = 0.0
    days: int = 0
    partial: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kwh": round(self.kwh, 2),
            "cost": round(self.cost, 2),
            "days": self.days,
            "partial": self.partial,
        }


@dataclass
class AccountHistory:
    """History for a single electricity account."""

    days: dict[str, DayRecord] = field(default_factory=dict)
    months: dict[str, MonthRecord] = field(default_factory=dict)
    updated: str | None = None
    #: Set once a full back-fill has run, so restarts do not refetch 12 months.
    backfilled: bool = False

    # -- (de)serialisation -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "days": {k: v.to_dict() for k, v in sorted(self.days.items())},
            "months": {k: v.to_dict() for k, v in sorted(self.months.items())},
            "updated": self.updated,
            "backfilled": self.backfilled,
        }

    @classmethod
    def from_dict(cls, data: Any) -> AccountHistory:
        history = cls()
        if not isinstance(data, dict):
            return history
        raw_days = data.get("days")
        if isinstance(raw_days, dict):
            for key, value in raw_days.items():
                if parse_date(key) is None:
                    continue
                history.days[key] = DayRecord.from_dict(value)
        raw_months = data.get("months")
        if isinstance(raw_months, dict):
            for key, value in raw_months.items():
                if not isinstance(key, str) or len(key) != 7:
                    continue
                if not isinstance(value, dict):
                    continue
                history.months[key] = MonthRecord(
                    kwh=_as_float(value.get("kwh")) or 0.0,
                    cost=_as_float(value.get("cost")) or 0.0,
                    days=int(_as_float(value.get("days")) or 0),
                    partial=bool(value.get("partial")),
                )
        updated = data.get("updated")
        history.updated = updated if isinstance(updated, str) else None
        history.backfilled = bool(data.get("backfilled"))
        return history

    # -- mutation ----------------------------------------------------------
    def merge_days(
        self,
        records: Iterable[tuple[date, float | None, float | None]],
    ) -> bool:
        """Merge ``(date, kwh, cost)`` tuples.

        Returns ``True`` when anything changed. Existing values are only
        overwritten when the incoming value is not ``None``: daily figures are
        occasionally unavailable on one poll and we do not want a transient
        API gap to erase good data.
        """
        changed = False
        for day, kwh, cost in records:
            key = day.strftime(DATE_FORMAT)
            record = self.days.get(key)
            if record is None:
                record = self.days[key] = DayRecord()
                changed = True
            if kwh is not None and record.kwh != kwh:
                record.kwh = kwh
                changed = True
            if cost is not None and record.cost != cost:
                record.cost = cost
                changed = True
        return changed

    def merge_month(
        self, month: str, kwh: float | None, cost: float | None
    ) -> bool:
        """Merge an authoritative monthly total reported by the API."""
        if kwh is None and cost is None:
            return False
        record = self.months.get(month)
        changed = False
        if record is None:
            record = self.months[month] = MonthRecord()
            changed = True
        if kwh is not None and record.kwh != kwh:
            record.kwh = kwh
            changed = True
        if cost is not None and record.cost != cost:
            record.cost = cost
            changed = True
        return changed

    def rebuild_months(self, today: date) -> bool:
        """Recompute monthly aggregates from the daily records.

        Summing the daily values is valid because the CSG API returns one
        reading per billing day, and verified against the API's own monthly
        totals these sums match exactly.

        Any monthly total that the API reported directly is preserved when it
        is *larger* than the sum of the days we hold (which happens when daily
        data for a month was unavailable but the monthly figure was not). The
        month is then flagged as ``partial``.
        """
        sums: dict[str, MonthRecord] = {}
        for key, record in self.days.items():
            day = parse_date(key)
            if day is None or record.kwh is None:
                continue
            bucket = sums.get(month_key(day))
            if bucket is None:
                bucket = sums[month_key(day)] = MonthRecord()
            bucket.kwh += record.kwh
            bucket.cost += record.cost or 0.0
            bucket.days += 1

        changed = False
        current_month = month_key(today)
        for month, bucket in sums.items():
            existing = self.months.get(month)
            if existing is not None:
                # Prefer a directly reported total when it covers more usage
                # than we can account for from the daily records.
                if existing.kwh > bucket.kwh + 0.01:
                    bucket.kwh = existing.kwh
                    bucket.cost = max(bucket.cost, existing.cost)
                    bucket.partial = True
                elif existing.partial:
                    bucket.partial = True
                # The API's charge total can legitimately exceed the sum of the
                # daily charges (rounding/fees); never report less than it.
                if existing.cost > bucket.cost + 0.01:
                    bucket.cost = existing.cost
            # The month in progress is always "so far".
            if month == current_month:
                bucket.partial = True

            if self.months.get(month) is None or existing.to_dict() != bucket.to_dict():
                changed = True
            self.months[month] = bucket
        return changed

    def prune(self, today: date, max_days: int = MAX_DAYS, max_months: int = MAX_MONTHS) -> bool:
        """Drop records outside the retention window."""
        changed = False
        oldest_day = today - timedelta(days=max_days)
        for key in sorted(self.days):
            day = parse_date(key)
            if day is None or day < oldest_day:
                del self.days[key]
                changed = True

        # Keep months covered by the retention window, plus a hard cap so a
        # corrupted or back-filled future date cannot grow the store forever.
        oldest_month = month_key(oldest_day)
        keep_months = set(self.month_keys()[-max_months:])
        for key in list(self.months):
            if key < oldest_month or key not in keep_months:
                del self.months[key]
                changed = True
        return changed

    # -- queries -----------------------------------------------------------
    def month_keys(self) -> list[str]:
        """Return the sorted list of months covered by daily records."""
        keys = {month_key(day) for key in self.days if (day := parse_date(key))}
        keys.update(self.months)
        return sorted(keys)

    def compact_daily_series(self) -> list[list[Any]]:
        """Return the daily history as compact rows for state attributes.

        Each row is ``[date, kwh]`` or ``[date, kwh, cost]``. Only days with a
        reading are included; the calendar infers gaps from the dates. The list
        form keeps the payload well under Home Assistant's 16 KB recorder limit
        even for a full year.
        """
        rows: list[list[Any]] = []
        for key in sorted(self.days):
            record = self.days[key]
            if record.kwh is None:
                continue
            if record.cost is None:
                rows.append([key, round(record.kwh, 2)])
            else:
                rows.append([key, round(record.kwh, 2), round(record.cost, 2)])
        return rows

    def monthly_series(self, months: int = 12) -> list[dict[str, Any]]:
        """Return up to the last ``months`` months in chronological order."""
        keys = self.month_keys()[-months:]
        result: list[dict[str, Any]] = []
        for key in keys:
            record = self.months.get(key)
            if record is None:
                result.append(
                    {"month": key, "kwh": 0.0, "cost": 0.0, "days": 0, "partial": True}
                )
                continue
            result.append({"month": key, **record.to_dict()})
        return result

    def yearly_series(self) -> list[dict[str, Any]]:
        """Aggregate the monthly records into calendar years."""
        totals: dict[str, dict[str, Any]] = {}
        for key, record in self.months.items():
            year = key[:4]
            bucket = totals.setdefault(
                year,
                {"year": year, "kwh": 0.0, "cost": 0.0, "months": 0, "partial": False},
            )
            bucket["kwh"] += record.kwh
            bucket["cost"] += record.cost
            bucket["months"] += 1
            if record.partial:
                bucket["partial"] = True
        return [
            {
                **bucket,
                "kwh": round(bucket["kwh"], 2),
                "cost": round(bucket["cost"], 2),
            }
            for _, bucket in sorted(totals.items())
        ]

    def latest_day(self) -> tuple[str, DayRecord] | None:
        """Return the most recent day that has a kilowatt-hour reading."""
        for key in sorted(self.days, reverse=True):
            record = self.days[key]
            if record.kwh is not None:
                return key, record
        return None

    def latest_month_key(self) -> str | None:
        """Return the most recent month that has any data."""
        keys = self.month_keys()
        return keys[-1] if keys else None

    def estimated_costs(self, rate: float) -> dict[str, Any]:
        """Estimate charges at ``rate`` for the latest day and latest month."""
        latest = self.latest_day()
        day_cost = estimate_cost(latest[1].kwh, rate) if latest else None

        month_key = self.latest_month_key()
        month_cost = None
        if month_key is not None:
            record = self.months.get(month_key)
            if record is not None:
                month_cost = round(record.kwh * rate, 2)

        return {
            "day": day_cost,
            "day_date": latest[0] if latest else None,
            "month": month_cost,
            "month_key": month_key,
        }


class HistoryStore:
    """In-memory history for all accounts, backed by :class:`Store`."""

    def __init__(self, store: Any) -> None:
        self._store = store
        self._accounts: dict[str, AccountHistory] = {}
        self._loaded = False

    @property
    def accounts(self) -> dict[str, AccountHistory]:
        return self._accounts

    def get(self, account_number: str) -> AccountHistory:
        """Return (creating if needed) the history for an account."""
        history = self._accounts.get(account_number)
        if history is None:
            history = self._accounts[account_number] = AccountHistory()
        return history

    async def async_load(self) -> None:
        """Load from persistent storage; no-op when already loaded."""
        if self._loaded:
            return
        raw = await self._store.async_load()
        if isinstance(raw, dict):
            for account_number, data in raw.items():
                if isinstance(account_number, str):
                    self._accounts[account_number] = AccountHistory.from_dict(data)
        self._loaded = True

    async def async_save(self) -> None:
        """Persist all accounts immediately."""
        await self._store.async_save(self._snapshot())

    def async_delay_save(self, delay: float = 5) -> None:
        """Schedule a debounced save.

        The snapshot is built when the delayed write fires, but ``to_dict``
        returns fresh plain dicts, so serialising it off the event loop cannot
        observe a concurrently mutated record.
        """
        self._store.async_delay_save(self._snapshot, delay=delay)

    def _snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a plain-data snapshot safe to serialise in another thread."""
        return {k: v.to_dict() for k, v in list(self._accounts.items())}
