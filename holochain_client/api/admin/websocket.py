"""AdminWebsocket: client for the Holochain Conductor admin interface.

Provides all admin operations: app lifecycle, agent key generation,
interface management, signing credential authorization, etc.
"""

from __future__ import annotations

import json
from typing import Any

from holochain_client.api.client import WsClient, HolochainError
from holochain_client.api.signing import (
    generate_signing_key_pair,
    random_cap_secret,
    set_signing_credentials,
    SigningCredentials,
)
from holochain_client.types import (
    AgentPubKey,
    AppAuthenticationToken,
    AppInfo,
    AppStatusFilter,
    CapSecret,
    CellId,
    DnaHash,
    InstalledAppId,
    RoleName,
)


class AdminWebsocket:
    """A websocket connection to the Holochain Conductor admin interface."""

    def __init__(self, client: WsClient, default_timeout: float = 60.0) -> None:
        self.client = client
        self.default_timeout = default_timeout

    @classmethod
    async def connect(
        cls,
        url: str,
        default_timeout: float = 60.0,
    ) -> AdminWebsocket:
        """Connect to the admin interface.

        Args:
            url: WebSocket URL, e.g. "ws://127.0.0.1:65000".
            default_timeout: Default timeout for requests in seconds.
        """
        client = await WsClient.connect(url)
        return cls(client, default_timeout)

    # ------------------------------------------------------------------
    # Agent
    # ------------------------------------------------------------------

    async def generate_agent_pub_key(self, timeout: float | None = None) -> AgentPubKey:
        resp = await self._request("generate_agent_pub_key", None, timeout)
        return resp["value"]

    # ------------------------------------------------------------------
    # DNA management
    # ------------------------------------------------------------------

    async def register_dna(self, payload: dict[str, Any], timeout: float | None = None) -> DnaHash:
        resp = await self._request("register_dna", payload, timeout)
        return resp["value"]

    async def get_dna_definition(
        self, dna_hash: DnaHash, timeout: float | None = None
    ) -> dict[str, Any]:
        resp = await self._request("get_dna_definition", dna_hash, timeout)
        return resp["value"]

    async def list_dnas(self, timeout: float | None = None) -> list[DnaHash]:
        resp = await self._request("list_dnas", None, timeout)
        return resp["value"]

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------

    async def install_app(
        self,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> AppInfo:
        """Install a hApp from a path or bundle.

        Example payload::

            {
                "source": {"type": "path", "value": "./my-app.happ"},
                "agent_key": agent_key,
                "installed_app_id": "my-app",
            }
        """
        resp = await self._request("install_app", payload, timeout)
        return AppInfo(**resp["value"])

    async def uninstall_app(
        self, installed_app_id: InstalledAppId, timeout: float | None = None
    ) -> None:
        await self._request("uninstall_app", {"installed_app_id": installed_app_id}, timeout)

    async def enable_app(
        self, installed_app_id: InstalledAppId, timeout: float | None = None
    ) -> dict[str, Any]:
        resp = await self._request("enable_app", {"installed_app_id": installed_app_id}, timeout)
        return resp["value"]

    async def disable_app(
        self, installed_app_id: InstalledAppId, timeout: float | None = None
    ) -> None:
        await self._request("disable_app", {"installed_app_id": installed_app_id}, timeout)

    async def list_apps(
        self,
        status_filter: AppStatusFilter | None = None,
        timeout: float | None = None,
    ) -> list[AppInfo]:
        # ListApps is a struct variant — always send the struct even with no filter
        payload = {"status_filter": status_filter.value if status_filter else None}
        resp = await self._request("list_apps", payload, timeout)
        return [AppInfo(**x) for x in resp["value"]]

    # ------------------------------------------------------------------
    # Cell management
    # ------------------------------------------------------------------

    async def list_cell_ids(self, timeout: float | None = None) -> list[CellId]:
        resp = await self._request("list_cell_ids", None, timeout)
        return [tuple(c) for c in resp["value"]]

    async def delete_clone_cell(
        self, payload: dict[str, Any], timeout: float | None = None
    ) -> None:
        await self._request("delete_clone_cell", payload, timeout)

    # ------------------------------------------------------------------
    # Coordinator updates
    # ------------------------------------------------------------------

    async def update_coordinators(
        self, payload: dict[str, Any], timeout: float | None = None
    ) -> None:
        await self._request("update_coordinators", payload, timeout)

    # ------------------------------------------------------------------
    # App interface management
    # ------------------------------------------------------------------

    async def attach_app_interface(
        self,
        port: int = 0,
        allowed_origins: str = "*",
        installed_app_id: InstalledAppId | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Attach an app interface. Returns {"port": <actual_port>}."""
        payload: dict[str, Any] = {"port": port, "allowed_origins": allowed_origins}
        if installed_app_id:
            payload["installed_app_id"] = installed_app_id
        resp = await self._request("attach_app_interface", payload, timeout)
        return resp["value"]

    async def list_app_interfaces(self, timeout: float | None = None) -> list[dict[str, Any]]:
        resp = await self._request("list_app_interfaces", None, timeout)
        return resp["value"]

    # ------------------------------------------------------------------
    # Authentication tokens
    # ------------------------------------------------------------------

    async def revoke_app_authentication_token(
        self,
        token: AppAuthenticationToken,
        timeout: float | None = None,
    ) -> None:
        """Revoke a previously issued app authentication token."""
        await self._request("revoke_app_authentication_token", token, timeout)

    async def issue_app_authentication_token(
        self,
        installed_app_id: InstalledAppId,
        expiry_seconds: int = 30,
        single_use: bool = True,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Issue a token for connecting to an app interface.

        Returns a dict with 'token' key.
        """
        resp = await self._request(
            "issue_app_authentication_token",
            {
                "installed_app_id": installed_app_id,
                "expiry_seconds": expiry_seconds,
                "single_use": single_use,
            },
            timeout,
        )
        return resp["value"]

    # ------------------------------------------------------------------
    # Agent key management
    # ------------------------------------------------------------------

    async def revoke_agent_key(
        self,
        installed_app_id: InstalledAppId,
        agent_key: AgentPubKey,
        timeout: float | None = None,
    ) -> list[tuple[CellId, str]]:
        """Revoke an agent key from an app.

        Returns a list of (cell_id, error_message) pairs for any cells
        that could not be revoked.
        """
        resp = await self._request(
            "revoke_agent_key",
            {"app_id": installed_app_id, "agent_key": agent_key},
            timeout,
        )
        return [(tuple(pair[0]), pair[1]) for pair in resp["value"]]

    # ------------------------------------------------------------------
    # Signing credentials
    # ------------------------------------------------------------------

    async def grant_zome_call_capability(
        self,
        cell_id: CellId,
        cap_grant: dict[str, Any],
        timeout: float | None = None,
    ) -> None:
        """Grant a zome call capability."""
        await self._request(
            "grant_zome_call_capability",
            {"cell_id": list(cell_id), "cap_grant": cap_grant},
            timeout,
        )

    async def grant_signing_key(
        self,
        cell_id: CellId,
        functions: dict[str, Any],
        signing_key: AgentPubKey,
        timeout: float | None = None,
    ) -> CapSecret:
        """Grant a signing key for zome calls and return the cap secret."""
        cap_secret = random_cap_secret()
        await self.grant_zome_call_capability(
            cell_id,
            {
                "tag": "zome-call-signing-key",
                "functions": functions,
                "access": {
                    "type": "assigned",
                    "value": {
                        "secret": cap_secret,
                        "assignees": [signing_key],
                    },
                },
            },
            timeout,
        )
        return cap_secret

    async def authorize_signing_credentials(
        self,
        cell_id: CellId,
        functions: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> None:
        """Generate a signing keypair, grant it, and store the credentials.

        This is the high-level convenience method (like the JS client's
        adminWs.authorizeSigningCredentials).
        """
        key_pair, signing_key = generate_signing_key_pair()
        cap_secret = await self.grant_signing_key(
            cell_id,
            functions or {"type": "all"},
            signing_key,
            timeout,
        )
        set_signing_credentials(
            cell_id,
            SigningCredentials(
                cap_secret=cap_secret,
                key_pair=key_pair,
                signing_key=signing_key,
            ),
        )

    # ------------------------------------------------------------------
    # Agent info (P2P peer discovery)
    # ------------------------------------------------------------------

    async def agent_info(
        self,
        dna_hashes: list[DnaHash] | None = None,
        timeout: float | None = None,
    ) -> list[str]:
        """Return agent info for all DNAs (or a subset if dna_hashes is given)."""
        payload = {"dna_hashes": dna_hashes}
        resp = await self._request("agent_info", payload, timeout)
        return resp["value"]

    async def add_agent_info(
        self,
        agent_infos: list[str],
        timeout: float | None = None,
    ) -> None:
        """Add pre-fetched agent infos to the peer store."""
        await self._request("add_agent_info", {"agent_infos": agent_infos}, timeout)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def dump_state(
        self, cell_id: CellId, timeout: float | None = None
    ) -> dict[str, Any]:
        resp = await self._request("dump_state", {"cell_id": list(cell_id)}, timeout)
        value = resp["value"]
        return json.loads(value) if isinstance(value, str) else value

    async def dump_conductor_state(self, timeout: float | None = None) -> dict[str, Any]:
        """Return the full conductor state as a dict."""
        resp = await self._request("dump_conductor_state", None, timeout)
        value = resp["value"]
        return json.loads(value) if isinstance(value, str) else value

    async def dump_full_state(
        self,
        cell_id: CellId,
        dht_ops_cursor: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Return the full DHT state for a cell (large response)."""
        payload: dict[str, Any] = {"cell_id": list(cell_id)}
        if dht_ops_cursor is not None:
            payload["dht_ops_cursor"] = dht_ops_cursor
        resp = await self._request("dump_full_state", payload, timeout)
        return resp["value"]

    async def dump_network_stats(self, timeout: float | None = None) -> dict[str, Any]:
        resp = await self._request("dump_network_stats", None, timeout)
        value = resp["value"]
        return json.loads(value) if isinstance(value, str) else value

    async def dump_network_metrics(
        self,
        dna_hash: DnaHash | None = None,
        include_dht_summary: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Return network metrics, optionally filtered to a single DNA."""
        payload: dict[str, Any] = {"include_dht_summary": include_dht_summary}
        if dna_hash is not None:
            payload["dna_hash"] = dna_hash
        resp = await self._request("dump_network_metrics", payload, timeout)
        return resp["value"]

    async def storage_info(self, timeout: float | None = None) -> dict[str, Any]:
        resp = await self._request("storage_info", None, timeout)
        return resp["value"]

    # ------------------------------------------------------------------
    # Source chain grafting
    # ------------------------------------------------------------------

    async def graft_records(
        self,
        cell_id: CellId,
        validate: bool,
        records: list[dict[str, Any]],
        timeout: float | None = None,
    ) -> None:
        """Graft a list of records onto an existing source chain."""
        await self._request(
            "graft_records_onto_source_chain",
            {"cell_id": list(cell_id), "validate": validate, "records": records},
            timeout,
        )

    # ------------------------------------------------------------------
    # Admin interfaces
    # ------------------------------------------------------------------

    async def add_admin_interfaces(
        self, configs: list[dict[str, Any]], timeout: float | None = None
    ) -> None:
        await self._request("add_admin_interfaces", configs, timeout)

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self.client.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _request(
        self, tag: str, value: Any = None, timeout: float | None = None
    ) -> dict[str, Any]:
        payload = {"type": tag, "value": value}
        return await self.client.request(payload, timeout or self.default_timeout)
