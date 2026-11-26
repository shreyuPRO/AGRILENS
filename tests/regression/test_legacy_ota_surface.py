"""
Guards what the DEPLOYED Raspberry Pi (v4.9.x) downloads on every boot.

The device's OTA fetches fixed files from main/AGRILENS_RaspberryPi/. Until the unit is migrated,
those committed files must keep serving identical content, and the legacy directory must not gain
new changes. Also characterises the two version parsers (shell and in-app) the old OTA uses.
"""
import os
import re
import subprocess

import pytest

from conftest import ROOT

# Working-tree changes that existed before Phase A. They belong to the owner and are never committed by this work.
KNOWN_PRE_EXISTING_DIRTY = {
    "AGRILENS_RaspberryPi/kiosk_config.json",
    "AGRILENS_RaspberryPi/labels.txt",
    "AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md",
}


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        pytest.skip("git unavailable: %s" % e)


# The three Phase A guards that froze AGRILENS_RaspberryPi/ at 4.9.4 were retired in 5.0.0 (the folder is now generated).
# Their replacement, tests/integration/test_ota_publication.py, tests the 4.9.4 -> 5.0.0 update hop itself.

# ---- version parsers --------------------------------------------------------------------------------------

def _shell_parse_ver():
    text = open(os.path.join(ROOT, "tests", "regression", "baseline", "legacy_4.9.4", "ota_update.sh"), encoding="utf-8").read()
    m = re.search(r"def parse_ver\(v_str\):\n(?:[ \t]+.*\n)+", text)
    assert m, "parse_ver not found in ota_update.sh"
    ns = {}
    exec(m.group(0), ns)
    return ns["parse_ver"]


@pytest.mark.parametrize("text,app_expected", [
    ("4.9.4", (4, 9, 4)), ("v4.9.4", (4, 9, 4)), ("4.10.0", (4, 10, 0)), ("4.9", (4, 9, 0)),
    ("", (0, 0, 0)), (None, (0, 0, 0)), ("abc", (0, 0, 0)),
    # Known defect (characterised, not fixed): digits of a suffix are merged into the patch number, so
    # "4.9.4-rc1" is read as 4.9.41 and would outrank 4.9.5. Phase D replaces this parser.
    ("4.9.4-rc1", (4, 9, 41)),
])
def test_in_app_version_parser(app, text, app_expected):
    assert app._parse_version_tuple(text) == app_expected


def test_in_app_parser_orders_versions_numerically(app):
    p = app._parse_version_tuple
    assert p("4.10.0") > p("4.9.9") and p("5.0.0") > p("4.99.99") and p("4.9.4") == p("v4.9.4")


def test_shell_and_in_app_parsers_currently_disagree_on_suffixes():
    # Documented divergence: the shell parser keeps up to 4 numbers, the in-app parser keeps 3.
    parse_ver = _shell_parse_ver()
    assert parse_ver("4.9.4") == (4, 9, 4)
    assert parse_ver("4.9.4-rc1") == (4, 9, 4, 1)
    assert parse_ver("4.9") == (4, 9)
    assert parse_ver("") == (0, 0, 0)


def test_in_app_version_extraction_reads_this_app(app):
    with open(os.path.join(os.path.dirname(os.path.abspath(app.__file__)), os.path.basename(app.__file__)), encoding="utf-8") as f:
        text = f.read()
    assert app._extract_version_from_code(text) == app.APP_VERSION
