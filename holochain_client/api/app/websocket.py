"""AppWebsocket: client for a Holochain app running in a Conductor.

Provides zome calls, signal subscription, clone cell management,
countersigning sessions, and network diagnostics.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

import msgpack

from holochain_client.api.client import WsClient, HolochainError
from holochain_client.api.signing import sign_zome_call, get_signing_credentials
from holochain_client.types import (
    AgentPubKey,
    AppAuthenticationToken,
    AppInfo,
    CellId,
    CellType,
    DnaHash,
    FunctionName,
    InstalledAppId,
    RoleName,
    ZomeName,
)


SignalCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class AppWebsocket:
    """A websocket connection to a Holochain app running in a Conductor.

    Provides the full app API: zome calls with automatic signing,
    signal subscription, clone cell management, and countersigning.
    """

    def __init__(
        self,
        client: WsClient,
        app_info: AppInfo,
        default_timeout: float = 60.0,
    ) -> None:
        self.client = client
        self.my_pub_key: AgentPubKey = app_info.agent_pub_key
        self.installed_app_id: InstalledAppId = app_info.installed_app_id
        self.default_timeout = default_timeout
        self._cached_app_info: AppInfo | None = app_info

    @classmethod
    async def connect(
        cls,
        url: str,
        token: AppAuthenticationToken,
        default_timeout: float = 60.0,
    ) -> AppWebsocket:
        """Connect to an app interface, authenticate, and fetch app info.

        Args:
            url: WebSocket URL, e.g. "ws://127.0.0.1:65001".
            token: Authentication token obtained via AdminWebsocket.issue_app_authentication_token.
            default_timeout: Default timeout for requests in seconds.
        """
        client = await WsClient.connect(url)
        await client.authenticate(token)

        # Fetch app info to get agent pub key and installed app id
        resp = await client.request({"type": "app_info", "value": None}, default_timeout)
        if resp.get("value") is None:
            raise HolochainError(
                "AppNotFound",
                "The app for this connection token was not found. It needs to be installed and enabled.",
            )
        app_info = AppInfo(**resp["value"])
        return cls(client, app_info, default_timeout)

    # ------------------------------------------------------------------
    # App info
    # ------------------------------------------------------------------

    async def app_info(self, timeout: float | None = None) -> AppInfo:
        """Request the app's info including all cell infos."""
        resp = await self._request("app_info", None, timeout)
        if resp.get("value") is None:
            raise HolochainError("AppNotFound", "App info not found.")
        info = AppInfo(**resp["value"])
        self._cached_app_info = info
        return info

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
        """Call a zome function with automatic signing.

        Either cell_id or role_name must be provided. If role_name is given,
        the cell_id is resolved from the cached app info.
        """
        if cell_id is None and role_name is not None:
            app_info = self._cached_app_info or await self.app_info()
            cell_id = self._get_cell_id_from_role_name(role_name, app_info)
        if cell_id is None:
            raise HolochainError("MissingCellId", "Either cell_id or role_name must be provided.")

        request = {
            "cell_id": cell_id,
            "zome_name": zome_name,
            "fn_name": fn_name,
            "payload": payload,
        }

        # Sign the zome call
        signed = sign_zome_call(request)
        resp = await self._request(
            "call_zome",
            {"bytes": signed.bytes, "signature": signed.signature},
            timeout,
        )
        raw = resp.get("value")
        if isinstance(raw, bytes):
            return msgpack.unpackb(raw, raw=False)
        return raw

    async def call_zome_request(
        self,
        request: dict[str, Any],
        timeout: float | None = None,
    ) -> Any:
        """Call a zome using a raw request dict. Handles role_name resolution and signing."""
        if "role_name" in request and "cell_id" not in request:
            app_info = self._cached_app_info or await self.app_info()
            request["cell_id"] = self._get_cell_id_from_role_name(
                request.pop("role_name"), app_info
            )

        signed = sign_zome_call(request)
        resp = await self._request(
            "call_zome",
            {"bytes": signed.bytes, "signature": signed.signature},
            timeout,
        )
        raw = resp.get("value")
        if isinstance(raw, bytes):
            return msgpack.unpackb(raw, raw=False)
        return raw

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def on(self, event_name: str, listener: SignalCallback) -> Callable[[], None]:
        """Register a signal listener. Currently only 'signal' is supported.

        Returns an unsubscribe function.
        """
        if event_name != "signal":
            raise ValueError(f"Unknown event: {event_name}. Only 'signal' is supported.")
        return self.client.on_signal(listener)

    # ------------------------------------------------------------------
    # Clone cell management
    # ------------------------------------------------------------------

    async def create_clone_cell(
        self,
        role_name: RoleName,
        modifiers: dict[str, Any],
        membrane_proof: bytes | None = None,
        name: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Clone an existing provisioned cell."""
        payload: dict[str, Any] = {"role_name": role_name, "modifiers": modifiers}
        if membrane_proof is not None:
            payload["membrane_proof"] = membrane_proof
        if name is not None:
            payload["name"] = name
        resp = await self._request("create_clone_cell", payload, timeout)
        self._cached_app_info = None  # Invalidate cache
        return resp["value"]

    async def enable_clone_cell(
        self, clone_cell_id: dict[str, Any], timeout: float | None = None
    ) -> dict[str, Any]:
        """Enable a disabled clone cell.

        clone_cell_id: {"type": "clone_id", "value": "role.0"} or {"type": "dna_hash", "value": dna_hash}
        """
        resp = await self._request("enable_clone_cell", {"clone_cell_id": clone_cell_id}, timeout)
        return resp["value"]

    async def disable_clone_cell(
        self, clone_cell_id: dict[str, Any], timeout: float | None = None
    ) -> None:
        """Disable an enabled clone cell."""
        await self._request("disable_clone_cell", {"clone_cell_id": clone_cell_id}, timeout)

    # ------------------------------------------------------------------
    # Membrane proofs
    # ------------------------------------------------------------------

    async def provide_memproofs(
        self, memproofs: dict[str, bytes], timeout: float | None = None
    ) -> None:
        await self._request("provide_memproofs", memproofs, timeout)

    async def enable_app(self, timeout: float | None = None) -> None:
        """Enable app after providing membrane proofs."""
        await self._request("enable_app", None, timeout)

    # ------------------------------------------------------------------
    # Host functions
    # ------------------------------------------------------------------

    async def list_wasm_host_functions(self, timeout: float | None = None) -> list[str]:
        """Return the list of host functions available in the conductor."""
        resp = await self._request("list_wasm_host_functions", None, timeout)
        return resp["value"]

    # ------------------------------------------------------------------
    # Countersigning
    # ------------------------------------------------------------------

    async def get_countersigning_session_state(
        self, cell_id: CellId, timeout: float | None = None
    ) -> dict[str, Any] | None:
        resp = await self._request(
            "get_countersigning_session_state", list(cell_id), timeout
        )
        return resp.get("value")

    async def abandon_countersigning_session(
        self, cell_id: CellId, timeout: float | None = None
    ) -> None:
        """Force-abandon an unresolved countersigning session."""
        await self._request("abandon_countersigning_session", list(cell_id), timeout)

    async def publish_countersigning_session(
        self, cell_id: CellId, timeout: float | None = None
    ) -> None:
        """Force-publish an unresolved countersigning session."""
        await self._request("publish_countersigning_session", list(cell_id), timeout)

    # ------------------------------------------------------------------
    # Network diagnostics
    # ------------------------------------------------------------------

    async def dump_network_stats(self, timeout: float | None = None) -> dict[str, Any]:
        resp = await self._request("dump_network_stats", None, timeout)
        value = resp["value"]
        return json.loads(value) if isinstance(value, str) else value

    async def dump_network_metrics(
        self, request: dict[str, Any] | None = None, timeout: float | None = None
    ) -> dict[str, Any]:
        resp = await self._request("dump_network_metrics", request, timeout)
        return resp["value"]

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self.client.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_cell_id_from_role_name(self, role_name: RoleName, app_info: AppInfo) -> CellId:
        """Resolve a role_name (or clone_id like 'role.0') to a CellId."""
        is_clone = "." in role_name
        if is_clone:
            base_role = role_name.split(".")[0]
            cells = app_info.cell_info.get(base_role, [])
            for cell in cells:
                if (
                    cell.get("type") == CellType.CLONED
                    and cell.get("value", {}).get("clone_id") == role_name
                ):
                    return tuple(cell["value"]["cell_id"])
            raise HolochainError("NoCellForCloneId", f"No clone cell found with clone id {role_name}")

        cells = app_info.cell_info.get(role_name, [])
        for cell in cells:
            if cell.get("type") == CellType.PROVISIONED:
                return tuple(cell["value"]["cell_id"])
        raise HolochainError(
            "NoCellForRoleName", f"No provisioned cell found with role_name {role_name}"
        )

    async def _request(
        self, tag: str, value: Any = None, timeout: float | None = None
    ) -> dict[str, Any]:
        payload = {"type": tag, "value": value}
        return await self.client.request(payload, timeout or self.default_timeout)
