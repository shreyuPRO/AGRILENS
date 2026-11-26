"""
Governance tool (tools/governance/agl_governance.py): pure functions and the hook entry point.
The repository-wide checks themselves are exercised by running `agl_governance.py check --full`; these tests pin the
parsing and decision logic that the hooks rely on, without touching git state.
"""
import importlib.util
import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def gov():
    path = os.path.join(ROOT, "tools", "governance", "agl_governance.py")
    spec = importlib.util.spec_from_file_location("agl_governance_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_semver_parsing(gov):
    assert gov.vtuple("5.0.0") == (5, 0, 0) and gov.vtuple("10.2.31") == (10, 2, 31)
    for bad in ("5.0", "5.0.0-rc1", "v5.0.0", "05.0.0", ""):
        assert gov.vtuple(bad) is None


def test_const_reads_string_and_int_constants(gov):
    src = 'APP_VERSION = "5.1.0"\nMODEL_NUM_CLASSES = 24\nX_APP_VERSION = "9.9.9"\n'
    assert gov.const(src, "APP_VERSION") == "5.1.0"
    assert gov.const(src, "MODEL_NUM_CLASSES") == "24"
    assert gov.const(src, "MISSING") == ""


def test_rules_are_consistent(gov):
    rules = gov.load_rules()
    assert rules["version"]["source_file"] == "application/main.py" and rules["version"]["constant"] == "APP_VERSION"
    names = [a["name"] for a in rules["areas"]]
    assert len(names) == len(set(names))
    paths = [e["path"] for e in rules["documentation_index"]]
    assert len(paths) == len(set(paths)) and "HOW_TO.md" in paths
    assert set(rules["current_docs"]) - set(paths) == set(), "every current document must be in the HOW_TO index"


@pytest.mark.parametrize("path,area", [
    ("application/main.py", "application"),
    ("deployment/ota/ota_update.sh", "device-scripts"),
    ("AGRILENS_RaspberryPi/main.py", "generated-package"),
    ("deployment/rollback/AGRILENS-5.0.1-rollback/main.py", "frozen-release-artefacts"),
    ("tools/governance/agl_governance.py", "governance"),
    ("documentation/technical/ROLLBACK.md", "documentation"),
    ("HOW_TO.md", "documentation"),
    ("some/new/notes.md", "documentation"),
])
def test_area_mapping(gov, path, area):
    assert gov.area_of(path, gov.load_rules())["name"] == area


def test_shipped_areas_require_version_handling(gov):
    rules = gov.load_rules()
    assert gov.area_of("application/main.py", rules)["version_relevant"]
    assert gov.area_of("deployment/raspberry_pi/run_agrilens.sh", rules)["version_relevant"]
    assert not gov.area_of("tools/governance/agl_governance.py", rules)["version_relevant"]


def test_register_parsing(gov):
    text = ("# reg\n\n### CR-0007 — Example\n\n| Field | Value |\n|---|---|\n| Date | 2026-11-18 |\n| Category | Tooling; Documentation |\n"
            "| Commit | pending |\n\n### CR-0008 - Second\n| Field | Value |\n|---|---|\n| Date | 2026-11-19 |\n")
    entries = gov.parse_register(text)
    assert [e["id"] for e in entries] == ["CR-0007", "CR-0008"]
    assert entries[0]["title"] == "Example" and entries[0]["fields"]["Category"] == "Tooling; Documentation"
    assert entries[0]["fields"]["Commit"] == "pending" and "Commit" not in entries[1]["fields"]


def test_the_change_register_is_complete(gov):
    entries = gov.parse_register(open(os.path.join(ROOT, "documentation", "CHANGE_REGISTER.md"), encoding="utf-8").read())
    assert entries, "change register has no entries"
    cats = set(gov.load_rules()["change_categories"])
    for e in entries:
        assert all(e["fields"].get(f) for f in gov.REGISTER_FIELDS), e["id"]
        assert {c.strip() for c in e["fields"]["Category"].split(";")} <= cats, e["id"]


def test_how_to_index_matches_rules(gov):
    rules = gov.load_rules()
    text = open(os.path.join(ROOT, "HOW_TO.md"), encoding="utf-8").read()
    block = text.split(gov.INDEX_BEGIN, 1)[1].split(gov.INDEX_END, 1)[0]
    assert block.strip() == gov.render_index(rules).strip()
    assert not open(os.path.join(ROOT, "HOW_TO.md"), "rb").read().startswith(b"\xef\xbb\xbf")


def test_version_markers_match_source(gov):
    rules = gov.load_rules()
    v = gov.const(open(os.path.join(ROOT, "application", "main.py"), encoding="utf-8").read(), "APP_VERSION")
    for f in rules["version"]["marker_files"]:
        marks = gov.VERSION_MARK.findall(open(os.path.join(ROOT, f), encoding="utf-8").read())
        assert marks and all(m == v for m in marks), f


def test_doc_references_extracts_links_and_repository_paths(gov):
    text = "See [a](../technical/ROLLBACK.md#x), [web](https://example.org), `documentation/CHANGE_REGISTER.md`, `tools/governance/`, `x.md`."
    refs = gov.doc_references("documentation/governance/G.md", text)
    assert "documentation/technical/ROLLBACK.md" in refs and "documentation/CHANGE_REGISTER.md" in refs and "tools/governance" in refs
    assert not any(r.startswith("https") for r in refs)


@pytest.mark.parametrize("command,commit,publish", [
    ("git commit -m 'x'", True, False),
    ('git -C "D:/repo" commit -am x', True, False),
    ("git commit --dry-run", False, False),
    ("git log --grep commit", False, False),
    ("git push origin main", False, True),
    ("git push https://github.com/x/y.git a:main", False, True),
    ("gh release create AGRILENS-5.1.0", False, True),
    ("powershell -File deployment\\ota\\publish_ota_release.ps1 -ReleaseId X", False, True),
    ("git status; git diff", False, False),
    ("git -c user.name=t -c user.email=t@x commit -m y", True, False),
    ("git --no-pager -C repo push github main", False, True),
    ("git config --get user.name", False, False),
])
def test_hook_command_classification(gov, command, commit, publish):
    assert bool(gov.GIT_COMMIT.search(command)) is commit
    assert bool(gov.PUBLISH.search(command)) is publish


def test_pretool_hook_delegates_to_the_repository_named_by_the_tool_cwd(gov, monkeypatch, tmp_path):
    """Kiro puts the session cwd at the top of the payload and the command's cwd in tool_input; the latter decides."""
    calls = []
    monkeypatch.setattr(gov, "run", lambda cmd, **kw: (0, str(tmp_path), "") if "rev-parse" in cmd else (0, "", ""))
    monkeypatch.setattr(gov, "_delegate_print", lambda tool, top, raw: calls.append(top) or 0)
    (tmp_path / "tools" / "governance").mkdir(parents=True)
    (tmp_path / "tools" / "governance" / "agl_governance.py").write_text("")
    payload = {"cwd": gov.ROOT, "tool_input": {"command": "git commit -m x", "cwd": str(tmp_path)}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert gov.cmd_hook_pretool(None) == 0 and calls == [str(tmp_path)]


def test_extract_commands_finds_nested_command_fields(gov):
    payload = {"tool_name": "execute_pwsh", "tool_input": {"command": "git push", "cwd": "x"}, "other": [{"cmd": "a"}]}
    assert set(gov.extract_commands(payload)) == {"git push", "a"}


def test_pretool_hook_asks_before_push_and_ignores_other_commands(gov, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": "git push origin main"}})))
    assert gov.cmd_hook_pretool(None) == 0
    decision = json.loads(capsys.readouterr().out)
    assert decision["hookSpecificOutput"]["permissionDecision"] == "ask"
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": "python -m pytest"}})))
    assert gov.cmd_hook_pretool(None) == 0 and capsys.readouterr().out == ""


def test_pretool_hook_blocks_a_failing_commit_with_the_dedicated_code(gov, monkeypatch, capsys):
    class Failing:
        failed = [{"check": "x"}]

        def render(self):
            return "FAIL report"
    monkeypatch.setattr(gov, "run_check", lambda mode, tests=True: Failing())
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": "git commit -m x"}})))
    assert gov.cmd_hook_pretool(None) == gov.HOOK_BLOCK == 3
    assert "commit blocked" in capsys.readouterr().err


def test_secret_patterns_detect_tokens_but_allow_the_documented_admin_pin(gov):
    import re
    rules = gov.load_rules()
    pats = [re.compile(p) for p in rules["secret_patterns"]]
    token = "gh" + "p_" + "A1b2C3d4" * 5
    assert any(p.search(f'token = "{token}"') for p in pats)
    assert any(p.search("-----BEGIN " + "RSA PRIVATE KEY-----") for p in pats)
    assert not any(p.search("label = 'Tomato_healthy'") for p in pats)
    pin_line = 'ADMIN_PASSWORD = "AGRILENS"'
    assert any(a["line"] in pin_line for a in rules["secret_allowlist"])
