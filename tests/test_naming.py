"""Tests for device/entity naming built from the CSG account."""

from __future__ import annotations

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


utils = _load("csg_utils", "utils.py")
account_display_name = utils.account_display_name

CONST_SOURCE = open(os.path.join(COMP, "const.py"), encoding="utf-8").read()

# Extract only the plain, dependency-free data blocks so const.py can be
# evaluated without importing the package (it imports .csg_client).
_names_block = re.search(r"SUFFIX_TO_ENTITY_NAME: dict.*?^\}", CONST_SOURCE, re.S | re.M)
_ids_block = re.search(r"SUFFIX_TO_OBJECT_ID: dict.*?^\}", CONST_SOURCE, re.S | re.M)
_suffixes = dict(re.findall(r'^(SUFFIX_\w+) = "([^"]+)"$', CONST_SOURCE, re.M))

_ns = dict(_suffixes)
_ns["dict"] = dict
exec(_names_block.group(0), _ns)  # noqa: S102
exec(_ids_block.group(0), _ns)  # noqa: S102
CHINESE_NAMES = _ns["SUFFIX_TO_ENTITY_NAME"]
OBJECT_IDS = _ns["SUFFIX_TO_OBJECT_ID"]
CALENDAR_NAME = re.search(r'^CALENDAR_ENTITY_NAME = "([^"]+)"', CONST_SOURCE, re.M).group(1)
CALENDAR_OBJECT_ID = re.search(r'^CALENDAR_OBJECT_ID = "([^"]+)"', CONST_SOURCE, re.M).group(1)


def test_full_name_and_address():
    account = {
        "account_number": "0307150390150952",
        "user_name": "张三",
        "address": "幸福小区3栋501",
    }
    assert account_display_name(account) == "张三 幸福小区3栋501 0307150390150952"


def test_name_without_address():
    assert account_display_name(
        {"account_number": "123", "user_name": "李四", "address": ""}
    ) == "李四 123"


def test_address_only():
    assert account_display_name(
        {"account_number": "123", "user_name": "", "address": "某小区1号"}
    ) == "某小区1号 123"


def test_falls_back_to_account_number():
    assert account_display_name({"account_number": "0307150390150952"}) == "0307150390150952"
    assert account_display_name(None) == "南方电网"
    assert account_display_name({}) == "南方电网"


def test_account_number_not_duplicated():
    """If the API already embeds the number in the name, do not repeat it."""
    account = {
        "account_number": "0307150390150952",
        "user_name": "0307150390150952",
        "address": "",
    }
    name = account_display_name(account)
    assert name.count("0307150390150952") == 1


def test_whitespace_is_collapsed():
    account = {
        "account_number": "1",
        "user_name": "  张  三 ",
        "address": " 幸福  小区 ",
    }
    assert "  " not in account_display_name(account)


def test_long_names_are_truncated():
    account = {"account_number": "1", "user_name": "名" * 60, "address": ""}
    name = account_display_name(account)
    assert len(name) <= utils.MAX_DEVICE_NAME_LEN
    assert name.endswith("…")


def test_entity_names_are_short_and_unique():
    """Every suffix maps to a distinct, human friendly Chinese name."""
    assert len(CHINESE_NAMES) == 20
    names = list(CHINESE_NAMES.values())
    assert len(names) == len(set(names)), f"duplicate entity names: {names}"
    for name in names:
        assert len(name) <= 8, f"entity name too long: {name}"
    assert CALENDAR_NAME == "用电日历"


def test_object_ids_are_ascii_and_unique():
    """entity_ids must be ASCII (not pinyin) and unique across entities."""
    assert len(OBJECT_IDS) == 20
    ids = list(OBJECT_IDS.values())
    assert len(ids) == len(set(ids)), f"duplicate object ids: {ids}"
    for object_id in ids:
        assert object_id.isascii(), f"{object_id} is not ASCII"
        assert object_id == object_id.lower()
        assert re.fullmatch(r"[a-z0-9_]+", object_id), object_id
    assert CALENDAR_OBJECT_ID.isascii()


def test_every_suffix_has_both_a_name_and_an_object_id():
    assert set(CHINESE_NAMES) == set(OBJECT_IDS)
    # Mapping keys are the *values* of the SUFFIX_* constants.
    assert set(CHINESE_NAMES) == set(_suffixes.values())


def test_names_and_ids_are_not_swapped():
    """Guard against accidentally putting pinyin in the object id."""
    for suffix, object_id in OBJECT_IDS.items():
        assert not any("\u4e00" <= ch <= "\u9fff" for ch in object_id), suffix
    for suffix, name in CHINESE_NAMES.items():
        assert any("\u4e00" <= ch <= "\u9fff" for ch in name), suffix
