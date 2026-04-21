"""Sprint 3 — RiskClassifier (Pattern #10: Command Risk Classification)."""
from __future__ import annotations

import pytest

from parallax_v3.contracts import RiskLevel
from parallax_v3.tools.risk_classifier import RiskClassifier


@pytest.fixture
def clf():
    return RiskClassifier()


def test_rm_rf_root_is_danger_block(clf):
    assert clf.classify("rm -rf /") == RiskLevel.DANGER_BLOCK


def test_rm_r_root_is_danger_block(clf):
    assert clf.classify("rm -r /") == RiskLevel.DANGER_BLOCK


def test_pip_install_asks_user(clf):
    assert clf.classify("pip install requests") == RiskLevel.ASK_USER


def test_pip_uninstall_asks_user(clf):
    assert clf.classify("pip uninstall numpy") == RiskLevel.ASK_USER


def test_curl_asks_user(clf):
    assert clf.classify("curl https://example.com") == RiskLevel.ASK_USER


def test_git_push_safe_confirm(clf):
    assert clf.classify("git push origin main") == RiskLevel.SAFE_CONFIRM


def test_pytest_safe_auto(clf):
    assert clf.classify("pytest tests/unit -q") == RiskLevel.SAFE_AUTO


def test_latexmk_safe_auto(clf):
    assert clf.classify("latexmk -pdf paper.tex") == RiskLevel.SAFE_AUTO


def test_unknown_command_defaults_to_ask_user(clf):
    # Safety default — unknown commands require explicit approval
    assert clf.classify("some_weird_binary --flag") == RiskLevel.ASK_USER
