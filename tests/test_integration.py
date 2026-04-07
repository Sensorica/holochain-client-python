"""Integration tests for AdminWebsocket and AppWebsocket.

These tests require a running Holochain conductor. They are skipped by default
and can be enabled by setting the HOLOCHAIN_TEST_ADMIN_URL environment variable.

Usage:
    # Start conductor, then:
    HOLOCHAIN_TEST_ADMIN_URL=ws://127.0.0.1:65000 pytest tests/test_integration.py -v
"""

import os
import pytest

ADMIN_URL = os.environ.get("HOLOCHAIN_TEST_ADMIN_URL")
HAPP_PATH = os.environ.get("HOLOCHAIN_TEST_HAPP_PATH", "./fixture/workdir/test.happ")

pytestmark = pytest.mark.skipif(
    ADMIN_URL is None,
    reason="HOLOCHAIN_TEST_ADMIN_URL not set; skipping integration tests",
)


@pytest.fixture
async def admin_ws():
    from holochain_client import AdminWebsocket
    ws = await AdminWebsocket.connect(ADMIN_URL)
    yield ws
    await ws.close()


class TestAdminIntegration:
    async def test_generate_agent_pub_key(self, admin_ws):
        key = await admin_ws.generate_agent_pub_key()
        assert len(key) == 39
        assert key[:3] == bytes([132, 32, 36])

    async def test_list_dnas_empty(self, admin_ws):
        dnas = await admin_ws.list_dnas()
        assert isinstance(dnas, list)

    async def test_list_apps_empty(self, admin_ws):
        apps = await admin_ws.list_apps()
        assert isinstance(apps, list)

    async def test_list_app_interfaces(self, admin_ws):
        interfaces = await admin_ws.list_app_interfaces()
        assert isinstance(interfaces, list)

    async def test_dump_network_stats(self, admin_ws):
        stats = await admin_ws.dump_network_stats()
        assert isinstance(stats, (dict, str))


class TestAppIntegration:
    """Full lifecycle: install app, connect app ws, call zome."""

    async def test_full_lifecycle(self, admin_ws):
        if not os.path.exists(HAPP_PATH):
            pytest.skip(f"Test hApp not found at {HAPP_PATH}")

        from holochain_client import AppWebsocket

        # Generate agent
        agent_key = await admin_ws.generate_agent_pub_key()
        app_id = "test-app-python"

        # Install
        app_info = await admin_ws.install_app({
            "source": {"type": "path", "value": HAPP_PATH},
            "agent_key": agent_key,
            "installed_app_id": app_id,
        })
        assert app_info.installed_app_id == app_id

        # Enable
        await admin_ws.enable_app(app_id)

        # Authorize signing for the first cell
        first_role = next(iter(app_info.cell_info))
        cells = app_info.cell_info[first_role]
        cell_id = tuple(cells[0]["value"]["cell_id"])
        await admin_ws.authorize_signing_credentials(cell_id)

        # Attach app interface
        iface = await admin_ws.attach_app_interface(port=0, allowed_origins="*")
        port = iface["port"]

        # Issue token
        token_resp = await admin_ws.issue_app_authentication_token(app_id)
        token = token_resp["token"]

        # Connect app ws
        app_ws = await AppWebsocket.connect(f"ws://127.0.0.1:{port}", token)
        assert app_ws.installed_app_id == app_id
        assert len(app_ws.my_pub_key) == 39

        # App info
        info = await app_ws.app_info()
        assert info.installed_app_id == app_id

        # Signal subscription (just test registration, no signal emitted)
        received = []
        unsub = app_ws.on("signal", lambda s: received.append(s))
        assert callable(unsub)
        unsub()

        # Cleanup
        await app_ws.close()
        await admin_ws.uninstall_app(app_id)
