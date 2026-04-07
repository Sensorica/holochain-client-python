# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

This project requires a Nix development environment for Holochain tools:

```bash
nix develop                        # Enter Nix shell (provides hc, holochain binaries)
python -m venv .venv && source .venv/bin/activate
poetry install --no-root
```

Build the test fixture (required before running tests):

```bash
cd fixture && npm install && npm run build:happ && cd ..
```

## Commands

```bash
# Run all tests
poetry run pytest

# Run a single test file
poetry run pytest tests/api/app/client_test.py

# Run a single test with output
RUST_LOG=info poetry run pytest tests/api/app/client_test.py -k test_call_zome -s

# Lint
poetry run ruff check

# Format
poetry run ruff format
```

## Architecture

Python async WebSocket client library for the [Holochain](https://holochain.org) Conductor API. Communication uses MessagePack serialization over persistent WebSocket connections.

**Two main clients:**

- `AdminClient` (`holochain_client/api/admin/`) — conductor administration: install/uninstall apps, register DNAs, manage agent keys, capability grants, query state
- `AppClient` (`holochain_client/api/app/`) — application calls: `call_zome()` to invoke zome functions with cryptographic signing

**Shared infrastructure** (`holochain_client/api/common/`):
- `request.py` — wire message serialization
- `pending_request_pool.py` — async request/response multiplexing via `asyncio.Event` + request ID tracking
- `signing.py` — Ed25519 signing and in-memory credential store keyed by `CellId`

**Request flow:** client method → serialize to msgpack → send over WebSocket → wait on `asyncio.Event` in `PendingRequestPool` → response decoded and returned.

**Test harness** (`tests/harness.py`) spawns a local Holochain sandbox via `hc sandbox`, creates both clients, installs the fixture happ, and tears everything down after each test suite.

## Key Patterns

- All network operations are `async`; clients hold a single persistent WebSocket connection
- Request/response types are Python `dataclass` objects defined in `types.py` alongside each client
- Zome calls require signing credentials set up via `authorize_signing_credentials()` before calling `call_zome()`
- `holochain-serialization` package prepares the canonical bytes before Ed25519 signing
