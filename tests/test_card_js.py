"""Runs the card's JavaScript unit tests as part of the pytest suite.

The Lovelace card is plain browser JavaScript, so its discovery logic is tested
with a small Node harness (``card_discovery_check.mjs``) rather than Python.
Skipped when Node is unavailable.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "card_discovery_check.mjs")

NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_card_entity_discovery():
    """The card must find the history sensor after the entity_id changed."""
    assert os.path.isfile(HARNESS), f"missing harness: {HARNESS}"
    proc = subprocess.run(
        [NODE, HARNESS],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=HERE,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"card checks failed:\n{output}"
    assert "FAIL" not in output, output
    assert "card checks passed" in output, output
