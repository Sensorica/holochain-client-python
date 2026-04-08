"""Rust-backed admin and app websocket clients.

Wraps ``holochain_client_rs`` (PyO3/Maturin) with the same async API as the
pure-Python client so that existing code works without changes.

Falls back gracefully: if ``holochain_client_rs`` is not installed this module
raises ``ImportError`` and ``__init__.py`` uses the pure-Python client instead.
"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Awaitable

import msgpack

import holochain_client_rs as _rs

from holochain_client.types import (
    AgentPubKey,
    AppAuthenticationToken,
    AppInfo,
    CellId,
    DnaHash,
    InstalledAppId,
    RoleName,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="hc-rust")

# Module-level signer shared between the last AdminWebsocket and AppWebsocket.
# In typical usage there is one admin connection that registers credentials,
# followed by one app connection that uses them.
_active_signer: _rs.ClientAgentSignerPy | None = None


async def _run(fn, *args):
    """Execute a blocking Rust call in the thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, fn, *args)


def _to_list(value) -> list:
    """Convert bytes or list[int] to list[int] (for Rust Vec<u8> params)."""
    if isinstance(value, (bytes, bytearray)):
        return list(value)
    return list(value)


def _parse_app_info(data: dict) -> AppInfo:
    """Parse a JSON-decoded dict into an AppInfo dataclass."""
    agent_pub_key = data.get("agent_pub_key", b"")
    if isinstance(agent_pub_key, list):
        agent_pub_key = bytes(agent_pub_key)
    return AppInfo(
        installed_app_id=data["installed_app_id"],
        cell_info=data.get("cell_info", {}),
        status=data.get("status"),
        agent_pub_key=agent_pub_key,
        manifest=data.get("manifest"),
        installed_at=data.get("installed_at"),
    )


# ---------------------------------------------------------------------------
# AdminWebsocket
# ---------------------------------------------------------------------------

class AdminWebsocket:
    """Async Python wrapper backed by ``holochain_client_rs.AdminWebsocketPy``."""

    def __init__(self, rs_admin: _rs.AdminWebsocketPy, signer: _rs.ClientAgentSignerPy) -> None:
        global _active_signer
        self._rs = rs_admin
        self._signer = signer
        _active_signer = signer

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @classmethod
    async def connect(cls, url: str, default_timeout: float = 60.0) -> AdminWebsocket:
        signer = _rs.ClientAgentSignerPy()
        rs_admin = await _run(_rs.AdminWebsocketPy, url)
        return cls(rs_admin, signer)

    async def close(self) -> None:
        pass  # Rust wrapper manages its own connection lifetime

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    async def generate_agent_pub_key(self, timeout: float | None = None) -> AgentPubKey:
        result = await _run(self._rs.generate_agent_pub_key)
        return bytes(result)

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------

    async def install_app(self, payload: dict[str, Any], timeout: float | None = None) -> AppInfo:
        p = dict(payload)
        if isinstance(p.get("agent_key"), (bytes, bytearray)):
            p["agent_key"] = list(p["agent_key"])
        result_json = await _run(self._rs.install_app, json.dumps(p))
        return _parse_app_info(json.loads(result_json))

    async def uninstall_app(self, installed_app_id: InstalledAppId, force: bool = False, timeout: float | None = None) -> None:
        await _run(self._rs.uninstall_app, installed_app_id, force)

    async def enable_app(self, installed_app_id: InstalledAppId, timeout: float | None = None) -> dict[str, Any]:
        result_json = await _run(self._rs.enable_app, installed_app_id)
        return json.loads(result_json)

    async def disable_app(self, installed_app_id: InstalledAppId, timeout: float | None = None) -> None:
        await _run(self._rs.disable_app, installed_app_id)

    async def list_apps(self, status_filter=None, timeout: float | None = None) -> list[AppInfo]:
        filter_str = json.dumps(status_filter) if status_filter is not None else None
        result_json = await _run(self._rs.list_apps, filter_str)
        return [_parse_app_info(a) for a in json.loads(result_json)]

    # ------------------------------------------------------------------
    # Cell / DNA
    # ------------------------------------------------------------------

    async def list_cell_ids(self, timeout: float | None = None) -> list[CellId]:
        pairs = await _run(self._rs.list_cell_ids)
        return [(bytes(dna), bytes(agent)) for dna, agent in pairs]

    async def list_dnas(self, timeout: float | None = None) -> list[DnaHash]:
        result = await _run(self._rs.list_dnas)
        return [bytes(h) for h in result]

    # ------------------------------------------------------------------
    # Interfaces
    # ------------------------------------------------------------------

    async def list_app_interfaces(self, timeout: float | None = None) -> list[dict[str, Any]]:
        result_json = await _run(self._rs.list_app_interfaces)
        return json.loads(result_json)

    async def attach_app_interface(
        self,
        port: int = 0,
        allowed_origins: str = "*",
        installed_app_id: InstalledAppId | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        bound_port = await _run(self._rs.attach_app_interface, port, allowed_origins, installed_app_id)
        return {"port": bound_port}

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def issue_app_authentication_token(
        self,
        installed_app_id: InstalledAppId,
        expiry_seconds: int = 30,
        single_use: bool = True,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        token = await _run(self._rs.issue_app_auth_token, installed_app_id, expiry_seconds, single_use)
        return {"token": bytes(token)}

    # ------------------------------------------------------------------
    # Signing credentials
    # ------------------------------------------------------------------

    async def authorize_signing_credentials(
        self,
        cell_id: CellId,
        functions: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> None:
        dna, agent = cell_id
        await _run(
            self._rs.authorize_signing_credentials,
            _to_list(dna),
            _to_list(agent),
            self._signer,
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def storage_info(self, timeout: float | None = None) -> dict[str, Any]:
        result_json = await _run(self._rs.storage_info)
        return json.loads(result_json)

    async def dump_network_stats(self, timeout: float | None = None) -> dict[str, Any] | str:
        result_json = await _run(self._rs.dump_network_stats)
        try:
            return json.loads(result_json)
        except json.JSONDecodeError:
            return result_json

    async def agent_info(
        self,
        dna_hashes: list[DnaHash] | None = None,
        timeout: float | None = None,
    ) -> list[str]:
        hashes = [_to_list(h) for h in dna_hashes] if dna_hashes else None
        return await _run(self._rs.agent_info, hashes)

    async def add_agent_info(self, agent_infos: list[str], timeout: float | None = None) -> None:
        await _run(self._rs.add_agent_info, agent_infos)


# ---------------------------------------------------------------------------
# AppWebsocket
# ---------------------------------------------------------------------------

SignalCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class AppWebsocket:
    """Async Python wrapper backed by ``holochain_client_rs.AppWebsocketPy``."""

    def __init__(self, rs_app: _rs.AppWebsocketPy, app_info: AppInfo) -> None:
        self._rs = rs_app
        self.my_pub_key: AgentPubKey = app_info.agent_pub_key
        self.installed_app_id: InstalledAppId = app_info.installed_app_id
        self._cached_app_info: AppInfo = app_info
        self._listeners: list[SignalCallback] = []

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @classmethod
    async def connect(
        cls,
        url: str,
        token: AppAuthenticationToken,
        default_timeout: float = 60.0,
    ) -> AppWebsocket:
        global _active_signer
        if _active_signer is None:
            _active_signer = _rs.ClientAgentSignerPy()
        signer = _active_signer
        token_list = _to_list(token)
        rs_app = await _run(_rs.AppWebsocketPy, url, token_list, signer)
        inst = cls.__new__(cls)
        inst._rs = rs_app
        inst._listeners = []
        # Fetch app info to populate my_pub_key and installed_app_id
        info_json = await _run(rs_app.app_info)
        if info_json is None:
            raise RuntimeError("app_info returned None after connect")
        app_info = _parse_app_info(json.loads(info_json))
        inst.my_pub_key = app_info.agent_pub_key
        inst.installed_app_id = app_info.installed_app_id
        inst._cached_app_info = app_info
        return inst

    async def close(self) -> None:
        pass

    # ------------------------------------------------------------------
    # App info
    # ------------------------------------------------------------------

    async def app_info(self, timeout: float | None = None) -> AppInfo:
        info_json = await _run(self._rs.app_info)
        if info_json is None:
            raise RuntimeError("app_info returned None")
        app_info = _parse_app_info(json.loads(info_json))
        self._cached_app_info = app_info
        return app_info

    # ------------------------------------------------------------------
    # Zome calls
    # ------------------------------------------------------------------

    async def call_zome(
        self,
        cell_id: CellId | None = None,
        role_name: RoleName | None = None,
        zome_name: str = "",
        fn_name: str = "",
        payload: Any = None,
        timeout: float | None = None,
    ) -> Any:
        if role_name and cell_id is None:
            # Resolve role_name → cell_id via cached or fresh app_info
            info = self._cached_app_info or await self.app_info()
            cells = info.cell_info[role_name]
            cell_id = tuple(cells[0]["value"]["cell_id"])

        dna, agent = cell_id
        payload_bytes = msgpack.packb(payload)
        result = await _run(
            self._rs.call_zome,
            _to_list(dna),
            _to_list(agent),
            zome_name,
            fn_name,
            list(payload_bytes),
        )
        return msgpack.unpackb(bytes(result), raw=False)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def on(self, event_name: str, listener: SignalCallback) -> Callable[[], None]:
        """Subscribe to signals. Returns an unsubscribe function."""
        if event_name == "signal":
            self._listeners.append(listener)

            def unsubscribe():
                try:
                    self._listeners.remove(listener)
                except ValueError:
                    pass

            return unsubscribe
        return lambda: None
