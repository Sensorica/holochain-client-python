# Reference

## Official Documentation

- [Holochain Application Architecture](https://developer.holochain.org/concepts/2_application_architecture/)

## Reference Implementations

- [holochain-client-js](https://github.com/holochain/holochain-client-js) — canonical JS client
- [holochain-client-rust](https://github.com/holochain/holochain-client-rust) — standalone Rust client (crates.io)
- [holochain monorepo client crate](https://github.com/holochain/holochain/tree/develop/crates/client) — source used for the Rust wrapper in this repo

## Related Projects

- [holochain-agent-skill](https://github.com/Soushi888/holochain-agent-skill) — AI agent skill for Holochain

## PyO3/Maturin Wrapper Notes

### Starting point

The approach for calling Rust from Python was modelled after
[holochain-serialization-python](https://github.com/holochain/holochain-serialization-python):
- [`src/lib.rs`](https://github.com/holochain/holochain-serialization-python/blob/main/src/lib.rs)
- [`test.py`](https://github.com/holochain/holochain-serialization-python/blob/main/test.py)

### Optional bindings pattern

To avoid forcing all users to build Rust bindings, the `pyo3` dependency is optional
and all PyO3 attributes use `cfg_attr` instead of direct annotation:

```rust
// Instead of #[pyclass]:
#[cfg_attr(feature = "python-bindings", pyclass)]
pub struct AdminWebsocketPy { ... }
```

This allows the crate to compile without `python-bindings` as a pure Rust library.

### See also

- [doc/plan.md](plan.md) — migration and implementation plan
- `src/lib.rs` — full wrapper source
