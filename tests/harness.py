"""Test harness: spawn a real Holochain sandbox for integration tests.

Usage as async context manager::

    async with HolochainHarness() as h:
        agent = await h.admin.generate_agent_pub_key()
        result = await h.app.call_zome(
            cell_id=h.cell_id,
            zome_name="fixture",
            fn_name="create_fixture",
            payload={"content": "hello"},
        )

The harness:
1. Creates an isolated temp directory and writes a conductor-config.yaml.
2. Launches the ``holochain`` binary on random ports.
3. Connects ``AdminWebsocket``.
4. Installs the fixture ``.happ`` and enables the app.
5. Authorizes signing credentials for the first cell.
6. Attaches an app interface and connects ``AppWebsocket``.
7. Tears everything down on exit.

Requires ``holochain`` on PATH (provided by ``nix develop``).
The fixture happ must be pre-built: ``cd fixture && npm run build:happ``.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from holochain_client.api.admin.websocket import AdminWebsocket
from holochain_client.api.app.websocket import AppWebsocket
from holochain_client.types import AgentPubKey, AppInfo, CellId

# Path to the pre-built fixture happ (relative to repo root)
_REPO_ROOT = Path(__file__).parent.parent
FIXTURE_HAPP = _REPO_ROOT / "fixture" / "workdir" / "fixture.happ"


def _free_port() -> int:
    """Return a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _write_conductor_config(config_path: Path, data_dir: Path, admin_port: int) -> None:
    """Write a minimal conductor-config.yaml for holochain 0.6.

    The format is derived from what ``hc sandbox create`` generates.
    ``danger_test_keystore`` bypasses the lair passphrase prompt.
    """
    config_path.write_text(
        f"""\
---
data_root_path: {data_dir}
keystore:
  type: danger_test_keystore
admin_interfaces:
  - driver:
      type: websocket
      port: {admin_port}
      allowed_origins: any
"""
    )


class HolochainHarness:
    """Async context manager that owns a full Holochain sandbox lifecycle."""

    def __init__(
        self,
        happ_path: Path | str | None = None,
        app_id: str = "test-app",
    ) -> None:
        self.happ_path = Path(happ_path) if happ_path else FIXTURE_HAPP
        self.app_id = app_id

        self._sandbox_dir: Path | None = None
        self._holochain_proc: subprocess.Popen | None = None  # type: ignore[type-arg]

        # Populated during __aenter__
        self.admin_port: int = 0
        self.app_port: int = 0
        self.admin: AdminWebsocket
        self.app: AppWebsocket
        self.agent_key: AgentPubKey
        self.app_info: AppInfo
        self.cell_id: CellId

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> HolochainHarness:
        await self._start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._stop()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _start(self) -> None:
        if not self.happ_path.exists():
            raise FileNotFoundError(
                f"Fixture happ not found: {self.happ_path}\n"
                "Run: cd fixture && npm run build:happ"
            )

        # 1. Create sandbox directory and conductor config
        self._sandbox_dir = Path(tempfile.mkdtemp(prefix="holochain-test-"))
        data_dir = self._sandbox_dir / "databases"
        data_dir.mkdir()
        config_path = self._sandbox_dir / "conductor-config.yaml"
        self.admin_port = _free_port()
        _write_conductor_config(config_path, data_dir, self.admin_port)

        # 2. Start holochain
        # lair_server_in_proc prompts for a passphrase on stdin.
        # For automated tests we send an empty passphrase immediately.
        env = {**os.environ, "RUST_LOG": os.environ.get("RUST_LOG", "warn")}
        self._holochain_proc = subprocess.Popen(
            ["holochain", "--config-path", str(config_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        # 3. Wait for admin port then give the WS server a moment to be ready
        await self._wait_for_port(self.admin_port)
        await asyncio.sleep(0.5)

        # 4. Connect admin
        self.admin = await AdminWebsocket.connect(f"ws://127.0.0.1:{self.admin_port}")

        # 5. Generate agent + install app
        self.agent_key = await self.admin.generate_agent_pub_key()
        self.app_info = await self.admin.install_app(
            {
                "source": {"type": "path", "value": str(self.happ_path)},
                "agent_key": self.agent_key,
                "installed_app_id": self.app_id,
            }
        )
        await self.admin.enable_app(self.app_id)

        # 6. Resolve cell_id from the first role
        first_role = next(iter(self.app_info.cell_info))
        cells = self.app_info.cell_info[first_role]
        self.cell_id = tuple(cells[0]["value"]["cell_id"])

        # 7. Authorize signing credentials
        await self.admin.authorize_signing_credentials(self.cell_id)

        # 8. Attach app interface
        iface = await self.admin.attach_app_interface(port=0, allowed_origins="*")
        self.app_port = iface["port"]

        # 9. Issue token + connect app ws
        token_resp = await self.admin.issue_app_authentication_token(
            self.app_id, expiry_seconds=60, single_use=False
        )
        token = token_resp["token"]
        self.app = await AppWebsocket.connect(
            f"ws://127.0.0.1:{self.app_port}", token
        )

    async def _stop(self) -> None:
        try:
            if hasattr(self, "app"):
                await self.app.close()
        except Exception:
            pass
        try:
            if hasattr(self, "admin"):
                await self.admin.close()
        except Exception:
            pass
        if self._holochain_proc is not None:
            self._holochain_proc.terminate()
            try:
                self._holochain_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._holochain_proc.kill()
        if self._sandbox_dir is not None:
            shutil.rmtree(self._sandbox_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _wait_for_port(port: int, timeout: float = 30.0) -> None:
        """Poll until the given TCP port accepts connections."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return
            except OSError:
                await asyncio.sleep(0.2)
        raise TimeoutError(f"Holochain did not start within {timeout}s (port {port})")
