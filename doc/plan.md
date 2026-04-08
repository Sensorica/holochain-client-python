# Plan: Holochain 0.6/0.7 Migration + Python/Rust Wrapper

## Status

| Phase | State | Commit |
|-------|-------|--------|
| 1.1 — flake.nix → holonix main-0.6 | ✅ Done | `ad234db` |
| 1.2 — fixture hdk/hdi 0.6/0.7 | ✅ Done | `d0091a8` |
| 1.3 — Python wire protocol | ✅ Done | — |
| 2.1-2.4 — PyO3/Maturin wrapper scaffold | ✅ Done | — |
| 2.5 — pyproject.toml → Maturin backend | ✅ Done | `d7509ef` |
| 3.1 — Missing admin methods | ✅ Done | — |
| 3.2 — AppWebsocket auth token | ✅ Done | — |
| 3.3 — Signals | ✅ Done | — |

All phases complete.

---

## Phase 1 — Holochain Environment Update ✅

### Breaking changes discovered (hdk 0.2 → 0.6)

These are undocumented in the official changelog and required debugging:

- **getrandom 0.3** — `hdi 0.7` / `hdk 0.6` depend on `getrandom 0.3.x` which no longer
  supports `wasm32-unknown-unknown` by default. Fix: `RUSTFLAGS='--cfg getrandom_backend="custom"'`.
  Note: `RUSTFLAGS=''` in the npm script overwrites `.cargo/config.toml` — the flag must be
  set directly in `package.json`.
- **`holochain_serialized_bytes`** — The `#[hdk_entry_helper]` derive macro generates code that
  references `holochain_serialized_bytes` by direct path. It must be a direct dependency of the
  integrity crate (not just transitive via hdi).
- **`#[hdk_entry_defs]` → `#[hdk_entry_types]`** — Renamed. `EntryTypes` and `LinkTypes` now
  require explicit `#[derive(Serialize, Deserialize)]` (required by coordinator for signals).
- **`OpUpdate::Entry`** — `original_action` / `original_app_entry` fields removed. Only
  `{ app_entry, action }` remains.
- **`OpDelete`** — No longer an enum with an `Entry` variant. Now a plain struct
  `{ action: Delete }` with no information about the original entry.
- **`get_links`** — Signature changed from `(base, type, None)` to
  `(LinkQuery::try_new(base, type)?, GetStrategy::Network)`.
  Use `GetStrategy::Local` in single-node test sandboxes — `Network` times out.
- **`delete_link`** — Now requires `GetOptions::default()` as a second argument.
- **Manifest version** — `manifest_version: "1"` → `"0"` for `hc app pack` in holochain 0.6.1-rc.x.
- **DNA/hApp manifest** — `bundled:` key renamed to `path:`. Fields `origin_time` and
  `quantum_time` removed from DNA modifiers.

### Wire protocol changes (Python client)

- **`install_app` source format** — Must use `{"type": "path", "value": "..."}`, not `{"path": "..."}`.
- **`CapAccess` serde** — Internal tagging: `{"type": "assigned", "value": {...}}`, not
  `{"Assigned": {...}}` (external tagging).
- **`AgentInfo` payload** — `AdminRequest::AgentInfo` is a struct variant requiring
  `{"dna_hashes": null}` — sending `null` directly fails deserialization.
- **`AppInfo`** — New `installed_at` field added in Holochain 0.6.
- **Zome call response** — Returns msgpack-encoded bytes that require a second
  `msgpack.unpackb()` decode.
- **`allowed_origins`** — The Rust client sends `Origin: holochain_websocket`;
  conductor config must allow `"*"` or that exact origin.

---

## Phase 2 — PyO3/Maturin Rust Wrapper ✅

### Architecture

```
src/lib.rs                    ← PyO3 wrappers (AdminWebsocketPy, AppWebsocketPy, ...)
Cargo.toml                    ← cdylib crate, python-bindings feature flag
```

The Tokio runtime is owned by each wrapper object. All async Rust calls are driven
with `block_on`, exposing a synchronous Python API.

### Dependency note

`holochain_client` and `holo_hash` are pinned to paths in the nix store
(`/nix/store/2kn3b3nrx22iv2b3r09skxj9f25s9dl3-source/crates/...`) because:

- The crates.io release (`0.7.0-rc.0`) depends on `holochain_conductor_api 0.5.6`
  which is incompatible with conductor 0.6.1-rc.6.
- The compatible version (`0.8.1-rc.6`) lives in the Holochain monorepo and is not
  yet published on crates.io.

Once a compatible version is published, `Cargo.toml` should be updated to use a
version specifier instead of a nix store path.

### Key API differences (holochain_client 0.8.1-rc.6 vs 0.7.0-rc.0)

| Change | Detail |
|--------|--------|
| `AdminWebsocket::connect` | Added `origin: Option<String>` parameter |
| `EnableAppResponse` | Private newtype `(AppInfo)` — serialize the wrapper directly, not `.0` |
| `attach_app_interface` | Added `danger_bind_addr: Option<String>` parameter |
| `AppWebsocket::connect` | Added `origin: Option<String>` parameter |

---

## Phase 3 — Python Client API Update ✅

All missing Holochain 0.6 admin methods added to `AdminWebsocket`:
`storage_info`, `dump_network_stats`, `dump_network_metrics`, `get_agent_info`,
`add_agent_info`, `issue_app_authentication_token`, `update_coordinators`.

App authentication token flow (required since Holochain 0.4+):
```python
token_resp = await admin.issue_app_authentication_token(app_id)
app = await AppWebsocket.connect(url, token=token_resp["token"])
```

Signal support added to `AppWebsocket` via an event emitter pattern:
```python
app.on("signal", callback)
```
