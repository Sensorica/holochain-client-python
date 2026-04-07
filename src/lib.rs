/// PyO3/Maturin wrapper over the canonical `holochain_client` Rust crate.
///
/// Build with:
///   maturin develop --features python-bindings
///
/// Python usage:
///   from holochain_client_rs import AdminWebsocketPy, AppWebsocketPy, ClientAgentSignerPy
#[cfg(feature = "python-bindings")]
use pyo3::exceptions::PyRuntimeError;
#[cfg(feature = "python-bindings")]
use pyo3::prelude::*;
#[cfg(feature = "python-bindings")]
use std::sync::Arc;

#[cfg(feature = "python-bindings")]
use holochain_client::{
    AdminWebsocket, AllowedOrigins, AppAuthenticationToken, AppWebsocket,
    AuthorizeSigningCredentialsPayload, ClientAgentSigner, DynAgentSigner,
    InstallAppPayload, IssueAppAuthenticationTokenPayload, ZomeCallTarget,
};

#[cfg(feature = "python-bindings")]
use holochain_client::{AgentPubKey, CellId, ExternIO};

#[cfg(feature = "python-bindings")]
use holo_hash::DnaHash;

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

#[cfg(feature = "python-bindings")]
fn py_err(e: impl std::fmt::Display) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}

// ---------------------------------------------------------------------------
// HoloHash byte conversion helpers
// ---------------------------------------------------------------------------

#[cfg(feature = "python-bindings")]
fn bytes_to_dna(b: Vec<u8>) -> PyResult<DnaHash> {
    if b.len() != 39 {
        return Err(py_err(format!("DnaHash must be 39 bytes, got {}", b.len())));
    }
    Ok(DnaHash::from_raw_39(b))
}

#[cfg(feature = "python-bindings")]
fn bytes_to_agent(b: Vec<u8>) -> PyResult<AgentPubKey> {
    if b.len() != 39 {
        return Err(py_err(format!("AgentPubKey must be 39 bytes, got {}", b.len())));
    }
    Ok(AgentPubKey::from_raw_39(b))
}

// ---------------------------------------------------------------------------
// SigningCredentialsPy
// ---------------------------------------------------------------------------

/// Opaque container for signing credentials returned by
/// `AdminWebsocketPy.authorize_signing_credentials`.
///
/// Exposes `signing_agent_key` (bytes) and `cap_secret` (bytes).
#[cfg_attr(feature = "python-bindings", pyclass)]
pub struct SigningCredentialsPy {
    pub signing_agent_key: Vec<u8>,
    pub cap_secret: Vec<u8>,
}

#[cfg(feature = "python-bindings")]
#[pymethods]
impl SigningCredentialsPy {
    #[getter]
    fn signing_agent_key(&self) -> Vec<u8> {
        self.signing_agent_key.clone()
    }

    #[getter]
    fn cap_secret(&self) -> Vec<u8> {
        self.cap_secret.clone()
    }
}

// ---------------------------------------------------------------------------
// ClientAgentSignerPy
// ---------------------------------------------------------------------------

/// Thread-safe signer that stores per-cell Ed25519 credentials.
///
/// Typical usage:
///   signer = ClientAgentSignerPy()
///   signing_key = admin.authorize_signing_credentials(dna, agent, signer)
///   app = AppWebsocketPy("127.0.0.1:9000", token, signer)
#[cfg_attr(feature = "python-bindings", pyclass)]
#[derive(Clone)]
pub struct ClientAgentSignerPy {
    inner: ClientAgentSigner,
}

#[cfg(feature = "python-bindings")]
#[pymethods]
impl ClientAgentSignerPy {
    #[new]
    fn new() -> Self {
        Self {
            inner: ClientAgentSigner::new(),
        }
    }
}

// ---------------------------------------------------------------------------
// AdminWebsocketPy
// ---------------------------------------------------------------------------

/// Synchronous Python wrapper around `AdminWebsocket`.
///
/// The Tokio runtime is owned by this object; all async calls are driven
/// with `block_on`.
///
/// Connection:
///   admin = AdminWebsocketPy("127.0.0.1:8000")
#[cfg_attr(feature = "python-bindings", pyclass)]
pub struct AdminWebsocketPy {
    inner: AdminWebsocket,
    rt: tokio::runtime::Runtime,
}

#[cfg(feature = "python-bindings")]
#[pymethods]
impl AdminWebsocketPy {
    /// Connect to the admin WebSocket.
    ///
    /// `addr` — socket address, e.g. `"127.0.0.1:8000"` or `"ws://127.0.0.1:8000"`.
    #[new]
    fn connect(addr: &str) -> PyResult<Self> {
        let addr = addr
            .trim_start_matches("ws://")
            .trim_start_matches("wss://")
            .trim_end_matches('/');
        let rt = tokio::runtime::Runtime::new().map_err(py_err)?;
        let inner = rt
            .block_on(AdminWebsocket::connect(addr))
            .map_err(py_err)?;
        Ok(Self { inner, rt })
    }

    // ------------------------------------------------------------------
    // Key management
    // ------------------------------------------------------------------

    /// Generate a new agent keypair in the keystore.
    /// Returns the raw 39-byte `AgentPubKey`.
    fn generate_agent_pub_key(&self) -> PyResult<Vec<u8>> {
        let key = self
            .rt
            .block_on(self.inner.generate_agent_pub_key())
            .map_err(py_err)?;
        Ok(key.get_raw_39().to_vec())
    }

    // ------------------------------------------------------------------
    // App lifecycle
    // ------------------------------------------------------------------

    /// Install a hApp bundle.
    ///
    /// `payload_json` — JSON-serialised `InstallAppPayload`, e.g.:
    ///   '{"source":{"path":"/path/to/app.happ"},"installed_app_id":"my-app"}'
    ///
    /// Returns JSON-serialised `AppInfo`.
    fn install_app(&self, payload_json: &str) -> PyResult<String> {
        let payload: InstallAppPayload =
            serde_json::from_str(payload_json).map_err(py_err)?;
        let info = self
            .rt
            .block_on(self.inner.install_app(payload))
            .map_err(py_err)?;
        serde_json::to_string(&info).map_err(py_err)
    }

    /// Uninstall an app.
    #[pyo3(signature = (installed_app_id, force=None))]
    fn uninstall_app(&self, installed_app_id: &str, force: Option<bool>) -> PyResult<()> {
        self.rt
            .block_on(
                self.inner
                    .uninstall_app(installed_app_id.to_string(), force.unwrap_or(false)),
            )
            .map_err(py_err)
    }

    /// Enable a previously installed app.
    /// Returns JSON-serialised `AppInfo`.
    fn enable_app(&self, installed_app_id: &str) -> PyResult<String> {
        let resp = self
            .rt
            .block_on(self.inner.enable_app(installed_app_id.to_string()))
            .map_err(py_err)?;
        serde_json::to_string(&resp.app).map_err(py_err)
    }

    /// Disable a running app.
    fn disable_app(&self, installed_app_id: &str) -> PyResult<()> {
        self.rt
            .block_on(self.inner.disable_app(installed_app_id.to_string()))
            .map_err(py_err)
    }

    /// List installed apps.
    ///
    /// `status_filter` — optional JSON string of `AppStatusFilter` variant,
    ///   e.g. `'"Running"'`. Pass `None` to list all apps.
    ///
    /// Returns JSON-serialised `Vec<AppInfo>`.
    #[pyo3(signature = (status_filter=None))]
    fn list_apps(&self, status_filter: Option<&str>) -> PyResult<String> {
        let filter = status_filter
            .map(|s| serde_json::from_str(s).map_err(py_err))
            .transpose()?;
        let apps = self
            .rt
            .block_on(self.inner.list_apps(filter))
            .map_err(py_err)?;
        serde_json::to_string(&apps).map_err(py_err)
    }

    /// List all cell IDs.
    /// Returns a list of `(dna_hash_bytes, agent_pub_key_bytes)` tuples.
    fn list_cell_ids(&self) -> PyResult<Vec<(Vec<u8>, Vec<u8>)>> {
        let ids = self
            .rt
            .block_on(self.inner.list_cell_ids())
            .map_err(py_err)?;
        Ok(ids
            .into_iter()
            .map(|cell_id| {
                (
                    cell_id.dna_hash().get_raw_39().to_vec(),
                    cell_id.agent_pubkey().get_raw_39().to_vec(),
                )
            })
            .collect())
    }

    /// List all installed DNA hashes.
    /// Returns a list of raw 39-byte DNA hashes.
    fn list_dnas(&self) -> PyResult<Vec<Vec<u8>>> {
        let dnas = self
            .rt
            .block_on(self.inner.list_dnas())
            .map_err(py_err)?;
        Ok(dnas.into_iter().map(|h| h.get_raw_39().to_vec()).collect())
    }

    // ------------------------------------------------------------------
    // Interface management
    // ------------------------------------------------------------------

    /// Attach an app WebSocket interface.
    ///
    /// `allowed_origins` — `"any"` or a comma-separated list of allowed origins.
    /// Returns the port the interface was bound to.
    #[pyo3(signature = (port, allowed_origins=None, installed_app_id=None))]
    fn attach_app_interface(
        &self,
        port: u16,
        allowed_origins: Option<&str>,
        installed_app_id: Option<&str>,
    ) -> PyResult<u16> {
        let origins = match allowed_origins.unwrap_or("any").to_lowercase().as_str() {
            "any" | "*" => AllowedOrigins::Any,
            s => AllowedOrigins::Origins(
                s.split(',').map(|o| o.trim().to_string()).collect(),
            ),
        };
        self.rt
            .block_on(self.inner.attach_app_interface(
                port,
                origins,
                installed_app_id.map(String::from),
            ))
            .map_err(py_err)
    }

    // ------------------------------------------------------------------
    // Authentication
    // ------------------------------------------------------------------

    /// Issue an app authentication token.
    ///
    /// Returns the raw token bytes.
    fn issue_app_auth_token(
        &self,
        installed_app_id: &str,
        expiry_seconds: u64,
        single_use: bool,
    ) -> PyResult<Vec<u8>> {
        let payload = IssueAppAuthenticationTokenPayload {
            installed_app_id: installed_app_id.to_string(),
            expiry_seconds,
            single_use,
        };
        let issued = self
            .rt
            .block_on(self.inner.issue_app_auth_token(payload))
            .map_err(py_err)?;
        Ok(Vec::from(issued.token))
    }

    // ------------------------------------------------------------------
    // Signing credentials
    // ------------------------------------------------------------------

    /// Authorize signing credentials for a cell and register them in `signer`.
    ///
    /// Combines `AdminWebsocket::authorize_signing_credentials` with
    /// `ClientAgentSigner::add_credentials` so the credentials are immediately
    /// usable by `AppWebsocketPy`.
    ///
    /// Parameters:
    ///   cell_id_dna   — raw 39-byte DnaHash
    ///   cell_id_agent — raw 39-byte AgentPubKey
    ///   signer        — the signer object that will hold the credentials
    ///
    /// Returns the raw 39-byte signing agent pub key.
    fn authorize_signing_credentials(
        &self,
        cell_id_dna: Vec<u8>,
        cell_id_agent: Vec<u8>,
        signer: &mut ClientAgentSignerPy,
    ) -> PyResult<Vec<u8>> {
        let dna = bytes_to_dna(cell_id_dna)?;
        let agent = bytes_to_agent(cell_id_agent)?;
        let cell_id = CellId::new(dna, agent);

        let creds = self
            .rt
            .block_on(self.inner.authorize_signing_credentials(
                AuthorizeSigningCredentialsPayload {
                    cell_id: cell_id.clone(),
                    functions: None, // unrestricted
                },
            ))
            .map_err(py_err)?;

        let signing_key_bytes = creds.signing_agent_key.get_raw_39().to_vec();

        signer.inner.add_credentials(cell_id, creds);

        Ok(signing_key_bytes)
    }
}

// ---------------------------------------------------------------------------
// AppWebsocketPy
// ---------------------------------------------------------------------------

/// Synchronous Python wrapper around `AppWebsocket`.
///
/// Requires an auth token (from `AdminWebsocketPy.issue_app_auth_token`) and
/// a `ClientAgentSignerPy` that already holds credentials for each cell that
/// will be called.
///
/// Connection:
///   app = AppWebsocketPy("127.0.0.1:9000", token_bytes, signer)
#[cfg_attr(feature = "python-bindings", pyclass)]
pub struct AppWebsocketPy {
    inner: AppWebsocket,
    rt: tokio::runtime::Runtime,
}

#[cfg(feature = "python-bindings")]
#[pymethods]
impl AppWebsocketPy {
    /// Connect to an app WebSocket.
    ///
    /// `addr`  — socket address, e.g. `"127.0.0.1:9000"` or `"ws://…"`.
    /// `token` — raw bytes returned by `AdminWebsocketPy.issue_app_auth_token`.
    /// `signer`— `ClientAgentSignerPy` instance populated with credentials.
    #[new]
    fn connect(addr: &str, token: Vec<u8>, signer: &ClientAgentSignerPy) -> PyResult<Self> {
        let addr = addr
            .trim_start_matches("ws://")
            .trim_start_matches("wss://")
            .trim_end_matches('/');
        let token = AppAuthenticationToken::from(token);
        let rt = tokio::runtime::Runtime::new().map_err(py_err)?;
        // Clone shares the Arc<RwLock<...>> inside ClientAgentSigner, so
        // credentials added to `signer` after this call remain visible.
        let dyn_signer: DynAgentSigner = Arc::new(signer.inner.clone());
        let inner = rt
            .block_on(AppWebsocket::connect(addr, token, dyn_signer))
            .map_err(py_err)?;
        Ok(Self { inner, rt })
    }

    /// Fetch the app info for the connected app.
    /// Returns JSON-serialised `AppInfo` or `None` if the app is not found.
    fn app_info(&self) -> PyResult<Option<String>> {
        let info = self
            .rt
            .block_on(self.inner.app_info())
            .map_err(py_err)?;
        info.map(|i| serde_json::to_string(&i).map_err(py_err))
            .transpose()
    }

    /// Call a zome function.
    ///
    /// Parameters:
    ///   cell_id_dna   — raw 39-byte DnaHash
    ///   cell_id_agent — raw 39-byte signing AgentPubKey (from
    ///                   `AdminWebsocketPy.authorize_signing_credentials`)
    ///   zome_name     — name of the coordinator zome
    ///   fn_name       — name of the zome function
    ///   payload       — msgpack-encoded argument (use `msgpack.packb`)
    ///
    /// Returns msgpack-encoded response bytes (use `msgpack.unpackb`).
    fn call_zome(
        &self,
        cell_id_dna: Vec<u8>,
        cell_id_agent: Vec<u8>,
        zome_name: &str,
        fn_name: &str,
        payload: Vec<u8>,
    ) -> PyResult<Vec<u8>> {
        let dna = bytes_to_dna(cell_id_dna)?;
        let agent = bytes_to_agent(cell_id_agent)?;
        let cell_id = CellId::new(dna, agent);

        let result = self
            .rt
            .block_on(self.inner.call_zome(
                ZomeCallTarget::CellId(cell_id),
                zome_name.into(),
                fn_name.into(),
                ExternIO::from(payload),
            ))
            .map_err(py_err)?;

        Ok(result.into_vec())
    }
}

// ---------------------------------------------------------------------------
// PyModule registration
// ---------------------------------------------------------------------------

#[cfg(feature = "python-bindings")]
#[pymodule]
fn holochain_client_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AdminWebsocketPy>()?;
    m.add_class::<AppWebsocketPy>()?;
    m.add_class::<ClientAgentSignerPy>()?;
    m.add_class::<SigningCredentialsPy>()?;
    Ok(())
}
