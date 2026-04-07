"""Tests for launcher environment detection."""

import os
import pytest
from holochain_client.environments.launcher import get_launcher_environment


class TestLauncherEnvironment:
    def test_no_env_returns_none(self, monkeypatch):
        monkeypatch.delenv("HOLOCHAIN_APP_INTERFACE_PORT", raising=False)
        assert get_launcher_environment() is None

    def test_detects_port(self, monkeypatch):
        monkeypatch.setenv("HOLOCHAIN_APP_INTERFACE_PORT", "8888")
        monkeypatch.delenv("HOLOCHAIN_APP_INTERFACE_TOKEN", raising=False)
        monkeypatch.delenv("HOLOCHAIN_ADMIN_INTERFACE_PORT", raising=False)
        env = get_launcher_environment()
        assert env is not None
        assert env.app_interface_port == 8888
        assert env.app_ws_url == "ws://localhost:8888"
        assert env.app_interface_token is None
        assert env.admin_ws_url is None

    def test_detects_token_and_admin(self, monkeypatch):
        monkeypatch.setenv("HOLOCHAIN_APP_INTERFACE_PORT", "9000")
        monkeypatch.setenv("HOLOCHAIN_APP_INTERFACE_TOKEN", "dGVzdA==")  # base64("test")
        monkeypatch.setenv("HOLOCHAIN_ADMIN_INTERFACE_PORT", "9001")
        env = get_launcher_environment()
        assert env is not None
        assert env.app_interface_token == b"test"
        assert env.admin_interface_port == 9001
        assert env.admin_ws_url == "ws://localhost:9001"
