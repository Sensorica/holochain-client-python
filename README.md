# Holochain Client - Python

A Python client for the Holochain Conductor API, compatible with Holochain 0.6.x / 0.7.x.

[![License: CAL 1.0](https://img.shields.io/badge/License-CAL%201.0-blue.svg)](https://github.com/holochain/cryptographic-autonomy-license)

## Installation

```bash
pip install holochain-client
```

Requires Python 3.10+.

## Quick Start

```python
import asyncio
from holochain_client import AdminWebsocket, AppWebsocket

async def main():
    # Connect to admin interface
    admin = await AdminWebsocket.connect("ws://127.0.0.1:65000")

    # Generate an agent key and install an app
    agent_key = await admin.generate_agent_pub_key()
    app_info = await admin.install_app({
        "source": {"type": "path", "value": "./my-app.happ"},
        "agent_key": agent_key,
        "installed_app_id": "my-app",
    })
    await admin.enable_app("my-app")

    # Get the cell ID for the first role
    role_name = next(iter(app_info.cell_info))
    cell_id = tuple(app_info.cell_info[role_name][0]["value"]["cell_id"])

    # Authorize signing credentials (generates keypair and grants capability)
    await admin.authorize_signing_credentials(cell_id)

    # Attach an app interface and get a token
    iface = await admin.attach_app_interface(port=0, allowed_origins="my-app")
    token_resp = await admin.issue_app_authentication_token("my-app")

    # Connect to app interface
    app = await AppWebsocket.connect(
        url=f"ws://127.0.0.1:{iface['port']}",
        token=token_resp["token"],
    )

    # Call a zome function
    result = await app.call_zome(
        cell_id=cell_id,
        zome_name="my_zome",
        fn_name="create_entry",
        payload={"content": "Hello from Python!"},
    )
    print("Zome call result:", result)

    # Or use role_name instead of cell_id
    result = await app.call_zome(
        role_name=role_name,
        zome_name="my_zome",
        fn_name="get_entries",
    )

    await app.close()
    await admin.close()

asyncio.run(main())
```

## Signal Handling

```python
def handle_signal(signal):
    if signal.get("type") == "app":
        print("App signal:", signal["value"])
    elif signal.get("type") == "system":
        print("System signal:", signal["value"])

# Register a listener (returns an unsubscribe function)
unsubscribe = app.on("signal", handle_signal)

# ... later
unsubscribe()
```

Async signal handlers are also supported:

```python
async def async_handler(signal):
    await process_signal(signal)

app.on("signal", async_handler)
```

## Clone Cell Management

```python
# Create a clone
clone = await app.create_clone_cell(
    role_name="my_role",
    modifiers={"network_seed": "custom-seed-123"},
)

# Disable / enable
await app.disable_clone_cell({"type": "clone_id", "value": clone["clone_id"]})
await app.enable_clone_cell({"type": "clone_id", "value": clone["clone_id"]})
```

## Signing Credentials (Browser Pattern)

For long-running applications, you can manage signing credentials manually:

```python
from holochain_client import (
    generate_signing_key_pair,
    set_signing_credentials,
    SigningCredentials,
)

key_pair, signing_key = generate_signing_key_pair()
cap_secret = await admin.grant_signing_key(
    cell_id,
    {"type": "all"},
    signing_key,
)
set_signing_credentials(cell_id, SigningCredentials(cap_secret, key_pair, signing_key))
```

## Launcher Environment

When running inside Holochain Launcher, Kangaroo, or Moss:

```python
from holochain_client.environments.launcher import get_launcher_environment

env = get_launcher_environment()
if env:
    app = await AppWebsocket.connect(
        url=env.app_ws_url,
        token=env.app_interface_token,
    )
```

## API Reference

### AdminWebsocket

| Method | Description |
|---|---|
| `generate_agent_pub_key()` | Generate a new agent keypair |
| `install_app(payload)` | Install a hApp |
| `uninstall_app(app_id)` | Uninstall a hApp |
| `enable_app(app_id)` | Enable a disabled app |
| `disable_app(app_id)` | Disable a running app |
| `list_apps(status_filter?)` | List installed apps |
| `list_dnas()` | List registered DNAs |
| `list_cell_ids()` | List all cell IDs |
| `register_dna(payload)` | Register a DNA |
| `get_dna_definition(dna_hash)` | Get a DNA's definition |
| `update_coordinators(payload)` | Update coordinator zomes |
| `attach_app_interface(port, origins)` | Open an app WebSocket port |
| `list_app_interfaces()` | List open app interfaces |
| `issue_app_authentication_token(app_id)` | Issue a connection token |
| `authorize_signing_credentials(cell_id)` | Generate and authorize signing keys |
| `grant_signing_key(cell_id, fns, key)` | Grant a specific signing key |
| `grant_zome_call_capability(cell_id, grant)` | Grant a capability |
| `dump_state(cell_id)` | Dump cell state as JSON |
| `dump_network_stats()` | Dump network statistics |
| `storage_info()` | Get storage information |
| `add_admin_interfaces(configs)` | Add admin WebSocket interfaces |

### AppWebsocket

| Method | Description |
|---|---|
| `app_info()` | Get app info with all cell infos |
| `call_zome(cell_id/role_name, zome, fn, payload)` | Call a zome function (auto-signed) |
| `on("signal", callback)` | Subscribe to signals |
| `create_clone_cell(role_name, modifiers)` | Clone a cell |
| `enable_clone_cell(clone_cell_id)` | Enable a clone |
| `disable_clone_cell(clone_cell_id)` | Disable a clone |
| `provide_memproofs(memproofs)` | Provide membrane proofs |
| `enable_app()` | Enable after memproofs |
| `get_countersigning_session_state(cell_id)` | Get countersigning state |
| `abandon_countersigning_session(cell_id)` | Force-abandon a session |
| `publish_countersigning_session(cell_id)` | Force-publish a session |
| `dump_network_stats()` | Network statistics |
| `dump_network_metrics(request?)` | Network metrics |

## Compatibility

| Python client | Holochain |
|---|---|
| 0.2.x | 0.6.x / 0.7.x |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run unit tests
pytest tests/ -v

# Run integration tests (requires running conductor)
HOLOCHAIN_TEST_ADMIN_URL=ws://127.0.0.1:65000 pytest tests/test_integration.py -v

# Lint
ruff check .
ruff format .

# Type check
mypy holochain_client/
```

## Architecture

```
holochain_client/
    __init__.py              # Public API
    types.py                 # HoloHash, CellId, AppInfo, enums
    api/
        client.py            # WsClient: msgpack wire protocol + reconnection
        signing.py           # Ed25519 keypair, credential store, call signing
        admin/websocket.py   # AdminWebsocket (20+ conductor admin methods)
        app/websocket.py     # AppWebsocket (zome calls, signals, clones)
    hdk/types.py             # Record, Action, Entry, Link, Capabilities
    utils/
        hash.py              # Hash type detection, fake hashes for testing
        hashmap.py           # HoloHashMap / DnaHashMap
    environments/
        launcher.py          # Launcher/Kangaroo/Moss env detection
```

## License

[CAL-1.0](https://github.com/holochain/cryptographic-autonomy-license)

Copyright (C) 2024, Holochain Foundation
