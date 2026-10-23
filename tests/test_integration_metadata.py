"""Tests for integration metadata that Home Assistant validates at runtime.

The domain is not a free-form string: apart from identifying the integration it
is validated by HA before certain endpoints will respond. The brand-image
endpoint in particular rejects anything that is not ``[\\da-z_]+``, which is why
the domain had to lose its uppercase ``GDJM`` suffix.
"""

from __future__ import annotations

import json
import os
import re

COMP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "custom_components",
    "china_southern_power_grid_stat",
)
CONST_SOURCE = open(os.path.join(COMP, "const.py"), encoding="utf-8").read()
MANIFEST = json.loads(open(os.path.join(COMP, "manifest.json"), encoding="utf-8").read())

# Copied verbatim from homeassistant/core.py so the test fails if HA's rule
# and our assumption ever drift apart.
_OBJECT_ID = r"(?!_)[\da-z_]+(?<!_)"
VALID_DOMAIN = re.compile(r"^(?!.+__)" + _OBJECT_ID + r"$")

DOMAIN = MANIFEST["domain"]


def const_value(name: str) -> str:
    match = re.search(rf'^{name} = "([^"]+)"$', CONST_SOURCE, re.M)
    assert match, f"{name} not found in const.py"
    return match.group(1)


def test_domain_is_a_valid_ha_domain():
    """HA's brand endpoint 404s any domain that fails this pattern."""
    assert VALID_DOMAIN.match(DOMAIN), (
        f"domain {DOMAIN!r} is not a valid HA domain; brand images can never be "
        f"served for it (this is why the uppercase 'GDJM' suffix was dropped)"
    )


def test_domain_is_lowercase():
    assert DOMAIN == DOMAIN.lower(), f"domain must be lowercase, got {DOMAIN!r}"
    assert "GDJM" not in DOMAIN


def test_const_domain_matches_manifest():
    """A mismatch would split storage, unique_ids and the brand lookup."""
    assert const_value("DOMAIN") == DOMAIN


def test_legacy_domain_is_different_and_uppercase():
    """Kept only to migrate the usage history written under the old name."""
    legacy = const_value("LEGACY_DOMAIN")
    assert legacy != DOMAIN
    assert legacy == "china_southern_power_grid_stat_GDJM"


def test_storage_key_follows_the_domain():
    assert 'STORAGE_KEY_USAGE_HISTORY = f"{DOMAIN}.usage_history"' in CONST_SOURCE
    assert f"{DOMAIN}.usage_history" != f"{const_value('LEGACY_DOMAIN')}.usage_history"


def test_frontend_directory_is_found_from_the_module_file():
    """The card must be located relative to this file, not via the domain.

    Regression: the static path was built as ``custom_components/<domain>``,
    which only worked while the folder happened to be named after the domain.
    Renaming the domain broke it.
    """
    frontend = os.path.join(COMP, "frontend")
    assert os.path.isdir(frontend), f"frontend directory missing: {frontend}"
    card = os.path.join(frontend, const_value("CARD_FILENAME"))
    assert os.path.isfile(card), f"card asset missing: {card}"

    # And the registration code must not go through the domain any more.
    init_source = open(os.path.join(COMP, "__init__.py"), encoding="utf-8").read()
    assert 'Path(__file__).parent / "frontend"' in init_source
    assert 'hass.config.path("custom_components", DOMAIN' not in init_source


def test_card_url_is_served_from_the_registered_static_path():
    url_base = const_value("URL_BASE")
    # CARD_URL is an f-string, so rebuild it the same way const.py does.
    assert 'CARD_URL = f"{URL_BASE}/{CARD_FILENAME}?v={CARD_VERSION}"' in CONST_SOURCE
    card_url = f"{url_base}/{const_value('CARD_FILENAME')}?v={const_value('CARD_VERSION')}"
    assert card_url.startswith(url_base + "/")
    assert url_base.startswith("/")
    assert not url_base.endswith("/")


def test_card_version_is_pinned_in_the_url():
    """The version query is what busts the browser cache between releases."""
    version = const_value("CARD_VERSION")
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version