"""Integration tests using a real Holochain conductor.

Requires ``holochain`` and ``hc`` on PATH (run inside ``nix develop``).
The fixture happ must be built first: ``cd fixture && npm run build:happ``.

Run all integration tests:
    uv run pytest tests/test_integration.py -s -v

Run with Rust conductor logs:
    RUST_LOG=info uv run pytest tests/test_integration.py -s -v
"""

from __future__ import annotations

import shutil

import pytest

from tests.harness import FIXTURE_HAPP, HolochainHarness

# Skip entire module when holochain is not on PATH
pytestmark = pytest.mark.skipif(
    shutil.which("holochain") is None,
    reason="holochain binary not found on PATH; run inside nix develop",
)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def harness():
    """Start a full Holochain sandbox and return the harness."""
    if not FIXTURE_HAPP.exists():
        pytest.skip(f"Fixture happ not built: {FIXTURE_HAPP}")
    async with HolochainHarness() as h:
        yield h


# ---------------------------------------------------------------------------
# Admin tests
# ---------------------------------------------------------------------------


class TestAdmin:
    async def test_generate_agent_pub_key(self, harness: HolochainHarness):
        key = await harness.admin.generate_agent_pub_key()
        assert len(key) == 39
        assert key[:3] == bytes([132, 32, 36])

    async def test_list_dnas(self, harness: HolochainHarness):
        dnas = await harness.admin.list_dnas()
        assert isinstance(dnas, list)
        assert len(dnas) >= 1  # fixture DNA is installed

    async def test_list_apps(self, harness: HolochainHarness):
        apps = await harness.admin.list_apps()
        assert any(a.installed_app_id == harness.app_id for a in apps)

    async def test_list_cell_ids(self, harness: HolochainHarness):
        ids = await harness.admin.list_cell_ids()
        assert isinstance(ids, list)
        assert len(ids) >= 1

    async def test_list_app_interfaces(self, harness: HolochainHarness):
        interfaces = await harness.admin.list_app_interfaces()
        assert isinstance(interfaces, list)
        assert len(interfaces) >= 1

    async def test_storage_info(self, harness: HolochainHarness):
        info = await harness.admin.storage_info()
        assert isinstance(info, dict)

    async def test_dump_network_stats(self, harness: HolochainHarness):
        stats = await harness.admin.dump_network_stats()
        assert isinstance(stats, (dict, str))

    async def test_agent_info(self, harness: HolochainHarness):
        infos = await harness.admin.agent_info()
        assert isinstance(infos, list)


# ---------------------------------------------------------------------------
# App tests
# ---------------------------------------------------------------------------


class TestApp:
    async def test_app_info(self, harness: HolochainHarness):
        info = await harness.app.app_info()
        assert info.installed_app_id == harness.app_id
        assert len(harness.app.my_pub_key) == 39

    async def test_call_zome_create_fixture(self, harness: HolochainHarness):
        result = await harness.app.call_zome(
            cell_id=harness.cell_id,
            zome_name="fixture",
            fn_name="create_fixture",
            payload={"content": "hello from python"},
        )
        assert result is not None

    async def test_call_zome_get_all_fixtures(self, harness: HolochainHarness):
        # Create one first
        await harness.app.call_zome(
            cell_id=harness.cell_id,
            zome_name="fixture",
            fn_name="create_fixture",
            payload={"content": "test entry"},
        )
        links = await harness.app.call_zome(
            cell_id=harness.cell_id,
            zome_name="fixture",
            fn_name="get_all_fixtures",
            payload=None,
        )
        assert isinstance(links, list)
        assert len(links) >= 1

    async def test_signal_subscription(self, harness: HolochainHarness):
        received: list = []
        unsub = harness.app.on("signal", lambda s: received.append(s))
        assert callable(unsub)
        unsub()  # unsubscribe immediately — just tests the API
