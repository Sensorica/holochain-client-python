# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

### 1. Install Nix (if not already installed)

```bash
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
```

Flakes are enabled automatically by the Determinate Systems installer. Then open a new terminal.

### 2. Enter the Nix dev environment

```bash
cd /path/to/holochain-client-python
nix develop
```

**All subsequent commands must run inside `nix develop`.** This provides `holochain`, `hc`, `cargo`, `rustc` (with `wasm32-unknown-unknown` target), `node`, and `npm` pinned to holonix `main-0.6` (Holochain 0.6.x).

### 3. Install Python dependencies

```bash
python -m venv .venv && source .venv/bin/activate
poetry install --no-root
```

### 4. Build the test fixture

```bash
cd fixture && npm install && npm run build:happ && cd ..
```

This compiles the Rust zomes to WASM and packages the `.happ`. The `RUSTFLAGS` in `fixture/package.json` include `--cfg getrandom_backend="custom"` which is required for `getrandom 0.3.x` with `wasm32-unknown-unknown`.

## Commands

```bash
# Run all tests
poetry run pytest -s

# Run a single test file
poetry run pytest tests/api/app/client_test.py -s

# Run a single test with Rust conductor logs
RUST_LOG=info poetry run pytest tests/api/app/client_test.py -k test_call_zome -s

# Lint
poetry run ruff check

# Format
poetry run ruff format
```

## Architecture

Python async WebSocket client for Holochain Conductor API (0.6.x / 0.7.x). Uses MessagePack wire protocol over persistent WebSocket connections.

**Python client** (`holochain_client/`):
- `api/client.py` — `WsClient`: msgpack wire protocol, reconnection, pending request pool
- `api/signing.py` — Ed25519 keypair generation, credential store keyed by `CellId`
- `api/admin/websocket.py` — `AdminWebsocket`: 20+ conductor admin methods
- `api/app/websocket.py` — `AppWebsocket`: `call_zome()`, signals, clone cells
- `types.py` — `HoloHash`, `CellId`, `AppInfo`, enums
- `hdk/types.py` — `Record`, `Action`, `Entry`, `Link`, capabilities
- `environments/launcher.py` — Launcher/Kangaroo/Moss env detection

**Test fixture** (`fixture/`): A minimal Rust hApp (integrity + coordinator zomes) compiled to WASM. Used by `tests/harness.py` which spawns a real Holochain sandbox for integration tests.

**Test harness** (`tests/harness.py`): context manager that spawns `hc sandbox`, connects `AdminWebsocket` + `AppWebsocket`, installs the fixture happ, then tears everything down.

## Key Patterns

- All network operations are `async`; clients hold a single persistent WebSocket connection
- Zome calls require signing credentials set up via `authorize_signing_credentials()` before `call_zome()`
- App connections since Holochain 0.4+ require an auth token from `issue_app_authentication_token()`
- `holochain-serialization` package (Rust/PyO3) provides canonical byte serialization for zome call signing

## Fixture — hdk/hdi 0.6/0.7 Migration Notes

Breaking changes encountered when migrating from HDK 0.2 to 0.6 (documented here for future reference):

| Change | Old | New |
|--------|-----|-----|
| Wasm entropy | `RUSTFLAGS=''` | `RUSTFLAGS='--cfg getrandom_backend="custom"'` |
| `holochain_serialized_bytes` | transitive dep only | must be a **direct** dep in integrity `Cargo.toml` |
| Entry type macro | `#[hdk_entry_defs]` | `#[hdk_entry_types]` |
| `get_links` | `get_links(base, type, None)` | `get_links(LinkQuery::try_new(base, type)?, GetStrategy::Network)` |
| `delete_link` | `delete_link(hash)` | `delete_link(hash, GetOptions::default())` |
| `OpUpdate::Entry` fields | `original_action`, `original_app_entry`, `app_entry`, `action` | `app_entry`, `action` only |
| `OpDelete` | enum with `Entry` variant | plain struct `{ action: Delete }` |
| Manifest version | `"1"` | `"0"` (for hc 0.6.1-rc.x) |

## Roadmap

See `doc/plan.md` for the phased plan toward a PyO3/Maturin Rust wrapper.
