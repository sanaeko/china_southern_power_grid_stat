"""Tests for the pure helpers in utils.py.

Covers the two behaviours that caused field-visible bugs:

* ``find_card_resources`` must ignore the ``?v=`` query, otherwise every release
  registers another Lovelace resource and stale ones keep loading.
* ``account_display_name`` builds the device name (covered in test_naming.py).
"""

from __future__ import annotations

import importlib.util
import os
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


utils = _load("csg_utils_card", "utils.py")
find_card_resources = utils.find_card_resources
card_resource_url_path = utils.card_resource_url_path

CARD = "/china_southern_power_grid_stat/china-southern-power-grid-usage-card.js"
TARGET = f"{CARD}?v=1.2.0"


def test_url_path_strips_the_query():
    assert card_resource_url_path(f"{CARD}?v=1.0.0") == CARD
    assert card_resource_url_path(CARD) == CARD
    assert card_resource_url_path(None) == ""
    assert card_resource_url_path(123) == ""


def test_matches_despite_different_versions():
    """The regression: v1.0.0/v1.1.0/v1.2.0 all point at the same file."""
    items = [
        {"id": "a", "url": f"{CARD}?v=1.0.0"},
        {"id": "b", "url": f"{CARD}?v=1.1.0"},
        {"id": "c", "url": TARGET},
    ]
    matched = find_card_resources(items, TARGET)
    assert [item["id"] for item in matched] == ["a", "b", "c"]


def test_ignores_unrelated_resources():
    items = [
        {"id": "a", "url": "/webrtc/webrtc-camera.js?v=v3.6.1"},
        {"id": "b", "url": "/hacsfiles/electricity-info-card/electricity-info-card.js"},
        {"id": "c", "url": TARGET},
    ]
    matched = find_card_resources(items, TARGET)
    assert [item["id"] for item in matched] == ["c"]


def test_no_match_on_an_empty_collection():
    assert find_card_resources([], TARGET) == []


def test_tolerates_items_without_a_url():
    items = [{"id": "a"}, {"id": "b", "url": None}, {"id": "c", "url": TARGET}]
    matched = find_card_resources(items, TARGET)
    assert [item["id"] for item in matched] == ["c"]


def test_duplicates_are_identified_for_cleanup():
    """Everything past the first match should be deleted."""
    items = [
        {"id": "old1", "url": f"{CARD}?v=1.0.0"},
        {"id": "old2", "url": f"{CARD}?v=1.1.0"},
        {"id": "current", "url": TARGET},
    ]
    keep, *duplicates = find_card_resources(items, TARGET)
    assert keep["id"] == "old1"
    assert [d["id"] for d in duplicates] == ["old2", "current"]


def test_empty_card_url_never_matches_everything():
    """Guards against a blank URL matching every url-less item."""
    items = [{"id": "a"}, {"id": "b", "url": ""}]
    assert find_card_resources(items, "") == []