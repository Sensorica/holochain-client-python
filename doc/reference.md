# Documentation

https://developer.holochain.org/concepts/2_application_architecture/

# working project

https://github.com/holochain/holochain-client-js


# Agent skill

https://github.com/Soushi888/holochain-agent-skill

# Guide to start wrapper

I already figured out a reasonable way to call Rust from Python here https://github.com/holochain/holochain-serialization-python/blob/main/src/lib.rs and here https://github.com/holochain/holochain-serialization-python/blob/main/test.py. As far as I know that code still works.

You can find the code for the Holochain Rust client here https://github.com/holochain/holochain/tree/develop/crates/client.

The only thing I can think of that we'd want to be careful about is not forcing everyone who uses the client to build Rust bindings. So the dependency on py03 would need to be optional and rather than using ⁨#[pyclass]⁩ directly for example, it would need to be ⁨#[cfg_attr(feature = "python-bindings", pyclass)]⁩

# Guide binding python with rust client

PyO3 bindings over the Rust client

Since holochain_client (Rust) is the canonical implementation, wrapping it with PyO3/Maturin would give you a Python client that stays in sync automatically. This is architecturally elegant and fits your compiled stack philosophy. The tradeoff: harder to debug, heavier build dependency (needs Rust toolchain).

# Goal

Support Holochain 0.6 and 0.7
