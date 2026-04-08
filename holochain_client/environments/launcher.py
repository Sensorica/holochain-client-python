"""Launcher environment detection for Tauri/Kangaroo/Moss apps.

When a Holochain app runs inside a launcher environment (e.g. Holochain Launcher,
Kangaroo, or Moss/Weave), the runtime injects configuration via environment
variables. This module detects and reads those values.

Environment variables:
    HOLOCHAIN_APP_INTERFACE_PORT: The port of the app WebSocket interface.
    HOLOCHAIN_APP_INTERFACE_TOKEN: Base64-encoded authentication token.
    HOLOCHAIN_ADMIN_INTERFACE_PORT: (optional) Admin interface port.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from holochain_client.types import AppAuthenticationToken


@dataclass
class LauncherEnvironment:
    """Configuration injected by a Holochain launcher."""

    app_interface_port: int | None = None
    app_interface_token: AppAuthenticationToken | None = None
    admin_interface_port: int | None = None

    @property
    def app_ws_url(self) -> str | None:
        if self.app_interface_port is not None:
            return f"ws://localhost:{self.app_interface_port}"
        return None

    @property
    def admin_ws_url(self) -> str | None:
        if self.admin_interface_port is not None:
            return f"ws://localhost:{self.admin_interface_port}"
        return None


def get_launcher_environment() -> LauncherEnvironment | None:
    """Detect if we are running inside a Holochain launcher environment.

    Returns a LauncherEnvironment if detected, None otherwise.
    """
    port_str = os.environ.get("HOLOCHAIN_APP_INTERFACE_PORT")
    if port_str is None:
        return None

    token_str = os.environ.get("HOLOCHAIN_APP_INTERFACE_TOKEN")
    token: AppAuthenticationToken | None = None
    if token_str:
        try:
            token = base64.b64decode(token_str)
        except Exception:
            # If it's not base64, try using it as raw bytes
            token = token_str.encode()

    admin_port_str = os.environ.get("HOLOCHAIN_ADMIN_INTERFACE_PORT")

    return LauncherEnvironment(
        app_interface_port=int(port_str),
        app_interface_token=token,
        admin_interface_port=int(admin_port_str) if admin_port_str else None,
    )
