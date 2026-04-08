# Holochain Client - Python

A Python client for the Holochain Conductor API, compatible with Holochain 0.6.x / 0.7.x.

This repository provides two complementary clients:

- **Python async client** (`holochain_client`) — pure Python, async/await, no Rust build step required
- **Rust wrapper** (`holochain_client_rs`) — PyO3/Maturin binding over the canonical Rust `holochain_client` crate, synchronous API, requires Rust toolchain inside `nix develop`

[![License: CAL 1.0](https://img.shields.io/badge/License-CAL%201.0-blue.svg)](https://github.com/holochain/cryptographic-autonomy-license)

---

## Table of Contents

- [Python Async Client](#python-async-client)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Signal Handling](#signal-handling)
  - [Clone Cell Management](#clone-cell-management)
  - [Signing Credentials](#signing-credentials-browser-pattern)
  - [Launcher Environment](#launcher-environment)
  - [API Reference](#api-reference)
- [Rust Wrapper](#rust-wrapper-holochain_client_rs)
  - [Prerequisites](#prerequisites)
  - [Build](#build)
  - [Usage](#usage)
  - [API Reference (Rust wrapper)](#api-reference-rust-wrapper)
- [Development](#development)
- [Compatibility](#compatibility)

---

## Python Async Client

### Installation

```bash
pip install holochain-client
```

Requires Python 3.10+.

### Quick Start

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
    iface = await admin.attach_app_interface(port=0, allowed_origins="*")
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

    await app.close()
    await admin.close()

asyncio.run(main())
```

### Signal Handling

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

### Clone Cell Management

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

### Signing Credentials (Browser Pattern)

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

### Launcher Environment

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

### API Reference

#### AdminWebsocket

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

#### AppWebsocket

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

---

## Rust Wrapper (`holochain_client_rs`)

The Rust wrapper is a synchronous Python extension module built with PyO3/Maturin over the
canonical `holochain_client` Rust crate. It exposes `AdminWebsocketPy`, `AppWebsocketPy`,
and `ClientAgentSignerPy` — a complete blocking API suitable for scripts and backends that
do not require Python async.

> **Note:** The Rust dependencies (`holochain_client`, `holo_hash`) are currently pinned
> to a path inside the nix store. Building outside of `nix develop` is not supported until
> compatible versions are published on crates.io.

### Prerequisites

**1. Install Nix** (Determinate Systems installer — enables flakes automatically):

```bash
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix \
  | sh -s -- install
```

Open a new terminal after installation.

**2. Enter the dev environment** — provides `holochain`, `cargo`, `rustc`, `maturin`, `node`:

```bash
cd holochain-client-python
nix develop
```

**3. Create and activate a Python virtualenv:**

```bash
python -m venv .venv
source .venv/bin/activate
pip install msgpack  # runtime dependency for the wrapper examples
```

**4. Build the test fixture** (only needed if you want to run integration tests):

```bash
cd fixture && npm install && npm run build:happ && cd ..
```

### Build

All commands must run inside `nix develop` with the virtualenv active.

```bash
# Development build — compiles the Rust extension and installs it into the active venv
maturin develop --features python-bindings

# Release wheel
maturin build --release --features python-bindings
# Output: target/wheels/holochain_client-*.whl
```

After `maturin develop`, the module is importable as `holochain_client_rs`.

### Usage

The Rust wrapper exposes a **synchronous** (blocking) API. All calls block the calling
thread until the conductor responds — no `asyncio` needed.

#### Prerequisites for the example

- A running Holochain conductor with admin WebSocket on port 8000
- A built `.happ` bundle

Start a conductor quickly with a minimal config:

```yaml
# conductor-config.yaml
data_root_path: /tmp/my-sandbox/databases
keystore:
  type: danger_test_keystore
admin_interfaces:
  - driver:
      type: websocket
      port: 8000
      allowed_origins: "*"
```

```bash
holochain --config-path conductor-config.yaml
```

#### Full example

```python
import json
import msgpack
import holochain_client_rs as rs

# 1. Connect to the admin WebSocket
admin = rs.AdminWebsocketPy("ws://127.0.0.1:8000")

# 2. Generate an agent keypair
#    PyO3 returns Vec<u8> as list[int] — wrap with bytes() when needed
agent_key = bytes(admin.generate_agent_pub_key())

# 3. Install a hApp
#    source must use {"type": "path", "value": "..."} format
app_info_json = admin.install_app(json.dumps({
    "source": {"type": "path", "value": "/path/to/my-app.happ"},
    "agent_key": list(agent_key),
    "installed_app_id": "my-app",
}))
app_info = json.loads(app_info_json)

# 4. Enable the app
admin.enable_app("my-app")

# 5. Extract the cell ID from app_info
first_role = next(iter(app_info["cell_info"]))
cell_entry = app_info["cell_info"][first_role][0]
dna_hash   = bytes(cell_entry["value"]["cell_id"][0])
agent_key2 = bytes(cell_entry["value"]["cell_id"][1])

# 6. Create a signer and authorize signing credentials for the cell
signer = rs.ClientAgentSignerPy()
signing_key = bytes(admin.authorize_signing_credentials(
    list(dna_hash), list(agent_key2), signer
))

# 7. Attach an app interface — returns the bound port number directly
app_port = admin.attach_app_interface(0, "*", None)

# 8. Issue an authentication token — returns raw token bytes
token = bytes(admin.issue_app_auth_token("my-app", expiry_seconds=3600, single_use=False))

# 9. Connect to the app WebSocket
app = rs.AppWebsocketPy(f"ws://127.0.0.1:{app_port}", list(token), signer)

# 10. Call a zome function
#     Payload must be msgpack-encoded bytes.
#     The response is also msgpack-encoded bytes — decode with msgpack.unpackb.
payload = msgpack.packb({"content": "Hello from the Rust wrapper!"})
result_bytes = bytes(app.call_zome(
    list(dna_hash),
    list(agent_key2),
    "my_zome",
    "create_entry",
    list(payload),
))
result = msgpack.unpackb(result_bytes, raw=False)
print("Zome call result:", result)
```

### API Reference (Rust wrapper)

All classes live in the `holochain_client_rs` module.

> **Type note:** PyO3 maps Rust `Vec<u8>` to Python `list[int]`, not `bytes`.
> Wrap with `bytes(value)` when you need a `bytes` object, or pass `list(b)` to
> convert `bytes` back to a list before passing to wrapper methods.

#### `AdminWebsocketPy(addr)`

Connects to the Holochain admin WebSocket.
`addr` — socket address, e.g. `"127.0.0.1:8000"` or `"ws://127.0.0.1:8000"`.

| Method | Parameters | Returns |
|---|---|---|
| `generate_agent_pub_key` | — | `list[int]` — 39-byte agent pub key |
| `install_app` | `payload_json: str` | `str` — JSON-serialised `AppInfo` |
| `uninstall_app` | `app_id: str, force: bool = False` | `None` |
| `enable_app` | `app_id: str` | `str` — JSON-serialised `AppInfo` |
| `disable_app` | `app_id: str` | `None` |
| `list_apps` | `status_filter: str = None` | `str` — JSON `Vec<AppInfo>` |
| `list_cell_ids` | — | `list[tuple[list, list]]` — `(dna, agent)` byte pairs |
| `list_dnas` | — | `list[list[int]]` — 39-byte DNA hashes |
| `attach_app_interface` | `port: int, allowed_origins: str, installed_app_id: str \| None` | `int` — bound port |
| `issue_app_auth_token` | `app_id: str, expiry_seconds: int, single_use: bool` | `list[int]` — token bytes |
| `authorize_signing_credentials` | `dna: list[int], agent: list[int], signer: ClientAgentSignerPy` | `list[int]` — signing key bytes |

#### `AppWebsocketPy(addr, token, signer)`

Connects to the Holochain app WebSocket.
`token` — raw token bytes from `issue_app_auth_token` (as `list[int]`).
`signer` — a `ClientAgentSignerPy` already populated via `authorize_signing_credentials`.

| Method | Parameters | Returns |
|---|---|---|
| `app_info` | — | `str \| None` — JSON `AppInfo` |
| `call_zome` | `dna: list[int], agent: list[int], zome: str, fn_name: str, payload: list[int]` | `list[int]` — msgpack-encoded response bytes |

#### `ClientAgentSignerPy()`

Opaque credential store shared between admin and app connections.
Create one instance per session:

```python
signer = rs.ClientAgentSignerPy()
# Pass to authorize_signing_credentials, then to AppWebsocketPy
```

---

## Development

### Running tests

All commands inside `nix develop` with `.venv` active.

```bash
# Install Python dev dependencies
pip install -e ".[dev]"

# Build the Rust extension
maturin develop --features python-bindings

# Run all integration tests (spawns a real Holochain sandbox automatically)
pytest tests/ -s

# Single test with conductor logs
RUST_LOG=info pytest tests/api/app/client_test.py -k test_call_zome -s

# Lint / format
ruff check .
ruff format .
```

### Project layout

```
holochain_client/        # Python async client
    api/client.py        # WsClient: msgpack wire protocol
    api/signing.py       # Ed25519 keypair + credential store
    api/admin/           # AdminWebsocket (20+ methods)
    api/app/             # AppWebsocket (zome calls, signals, clones)
    types.py             # HoloHash, CellId, AppInfo, enums
    hdk/types.py         # Record, Action, Entry, Link
    environments/        # Launcher/Kangaroo/Moss detection
src/lib.rs               # Rust wrapper (PyO3/Maturin)
Cargo.toml               # Rust crate config
fixture/                 # Minimal test hApp (integrity + coordinator zomes)
tests/
    harness.py           # Spawns a real Holochain sandbox for integration tests
    api/                 # Python client tests
    test_integration.py  # Full end-to-end tests
```

---

## Compatibility

| Client | Holochain |
|---|---|
| Python async (`holochain_client`) | 0.6.x / 0.7.x |
| Rust wrapper (`holochain_client_rs`) | 0.6.x (uses monorepo `holochain_client` 0.8.1-rc.6) |

---

## License

[CAL-1.0](https://github.com/holochain/cryptographic-autonomy-license)

Copyright (C) 2024, Holochain Foundation
