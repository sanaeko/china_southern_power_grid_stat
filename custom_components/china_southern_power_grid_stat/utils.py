"""helper functions"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

#: Kept short so device/entity names stay readable in the UI.
MAX_DEVICE_NAME_LEN = 40


def account_display_name(account_data: dict[str, Any] | None) -> str:
    """Build a human friendly device name from an electricity account.

    Uses the account holder's name and address as provided by the CSG API,
    e.g. ``"张三 幸福小区3栋501"``. Falls back to the account number when the
    API did not supply a name, so the device is always identifiable.
    """
    if not isinstance(account_data, dict):
        return "南方电网"

    user_name = (account_data.get("user_name") or "").strip()
    address = (account_data.get("address") or "").strip()
    account_number = (account_data.get("account_number") or "").strip()

    # The API sometimes pads addresses with the account number or repeated
    # whitespace; collapse it so names do not look broken.
    address = " ".join(address.split())
    user_name = " ".join(user_name.split())

    if user_name and address:
        name = f"{user_name} {address}"
    elif user_name:
        name = user_name
    elif address:
        name = address
    else:
        # Nothing but the account number is available.
        return account_number or "南方电网"

    if account_number and account_number not in name:
        # Keep the account number visible so multiple accounts stay distinct.
        name = f"{name} {account_number}"

    if len(name) > MAX_DEVICE_NAME_LEN:
        name = name[: MAX_DEVICE_NAME_LEN - 1] + "…"
    return name
