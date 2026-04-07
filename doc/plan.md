# Plan : Migration Holochain 0.6/0.7 + Wrapper Python/Rust

## Statut

| Phase | État | Commit |
|-------|------|--------|
| 1.1 — flake.nix → holonix main-0.6 | ✅ Complété | `ad234db` |
| 1.2 — fixture hdk/hdi 0.6/0.7 | ✅ Complété | `d0091a8` |
| 1.3 — protocole wire Python | 🔲 À faire | — |
| 2 — Wrapper PyO3/Maturin | 🔲 À faire | — |
| 3 — API Python 0.6 | 🔲 À faire | — |

## État actuel

- Client Python pur (WebSocket + msgpack) ciblant **Holochain 0.2.6**
- `flake.nix` pin : `holochain-0.2.6`, fixture avec `hdk = "=0.2.5"` / `hdi = "=0.3.5"`
- Dépendance Rust existante : `holochain-serialization` (PyO3) pour la signature uniquement
- API couverte : `AdminClient` (14 méthodes) + `AppClient` (`call_zome`)

## Objectif

Supporter **Holochain 0.6 et 0.7** via un wrapper PyO3/Maturin sur le crate Rust
canonique `holochain_client`, plutôt que de maintenir un client Python pur.

---

## Phase 1 — Mise à jour de l'environnement Holochain ✅

> **Complété** — voir commit `d0091a8` pour l'ensemble des corrections.

### Breaking changes découverts (hdk 0.2 → 0.6)

Ces points ne sont pas documentés dans le changelog officiel et ont nécessité du débogage :

- **getrandom 0.3** — `hdi 0.7` / `hdk 0.6` utilisent directement `getrandom 0.3.x` qui ne supporte plus `wasm32-unknown-unknown` par défaut. Fix : `RUSTFLAGS='--cfg getrandom_backend="custom"'`. Note : `RUSTFLAGS=''` dans le script npm écrase `.cargo/config.toml`, il faut mettre le flag directement dans `package.json`.
- **`holochain_serialized_bytes`** — Le derive macro `#[hdk_entry_helper]` génère du code qui référence `holochain_serialized_bytes` par chemin direct. Il doit être une dépendance directe du crate integrity (pas seulement transitive via hdi).
- **`#[hdk_entry_defs]`** → **`#[hdk_entry_types]`** — Renommé. `EntryTypes` et `LinkTypes` ont besoin de `#[derive(Serialize, Deserialize)]` explicites (requis par le coordinator pour les signaux).
- **`OpUpdate::Entry`** — Plus de champs `original_action` / `original_app_entry`. Seulement `{ app_entry, action }`.
- **`OpDelete`** — N'est plus un enum avec un variant `Entry`. C'est maintenant un struct `{ action: Delete }` sans information sur l'entrée originale.
- **`get_links`** — Signature changée de `(base, type, None)` vers `(LinkQuery::try_new(base, type)?, GetStrategy::Network)`.
- **`delete_link`** — Requiert maintenant `GetOptions::default()` comme second argument.
- **Manifest version** — `manifest_version: "1"` → `"0"` pour `hc app pack` de holochain 0.6.1-rc.x.

### 1.1 Mettre à jour `flake.nix`

```nix
# Remplacer
versions.inputs.holochain.url = "github:holochain/holochain/holochain-0.2.6";
# Par
versions.inputs.holochain.url = "github:holochain/holochain/holochain-0.6.x";
# (ou holonix ref=main-0.6 selon l'approche holonix)
```

Référence holonix 0.6 : `github:holochain/holonix/ref=main-0.6`

### 1.2 Mettre à jour le fixture Rust

`fixture/Cargo.toml` :
```toml
hdk = "=0.6.0"
hdi = "=0.7.0"
```

Mettre à jour le code du zome si l'API HDK a changé entre 0.2 et 0.6.

### 1.3 Vérifier la compatibilité du protocole wire

Entre 0.2 et 0.6, le protocole WebSocket/msgpack a pu changer :
- Structure de `AppRequest` / `AppResponse`
- Format de `ZomeCallUnsigned` (nonce, expiry, signatures)
- Nouveaux champs dans `AppInfo`, `CellInfo`

Référence : comparer avec `holochain-client-js` (implémentation canonique JS).

---

## Phase 2 — Wrapper PyO3/Maturin sur le client Rust

### 2.1 Architecture cible

```
holochain_client/
├── _rust/              ← extension compilée par Maturin (optionnelle)
│   └── holochain_client_rs.so
├── api/
│   ├── admin/client.py ← garde le fallback Python pur (ou délègue au Rust)
│   └── app/client.py
└── __init__.py
```

### 2.2 Initialiser Maturin

```bash
# Dans la racine du repo
pip install maturin
maturin init --bindings pyo3
```

Cela crée `Cargo.toml` + `src/lib.rs` à la racine.

### 2.3 `Cargo.toml` — dépendance sur le client Rust Holochain

```toml
[package]
name = "holochain-client-python"
version = "0.1.0"
edition = "2021"

[lib]
name = "holochain_client_rs"
crate-type = ["cdylib"]

[features]
default = []
python-bindings = ["pyo3"]

[dependencies]
pyo3 = { version = "0.21", features = ["extension-module"], optional = true }
holochain_client = { git = "https://github.com/holochain/holochain", tag = "holochain-0.6.x" }
tokio = { version = "1", features = ["full"] }

[dev-dependencies]
tokio = { version = "1", features = ["full"] }
```

### 2.4 Types à wrapper (`src/lib.rs`)

Priorité par ordre d'usage :

| Type Rust | Classe Python | Méthodes exposées |
|-----------|--------------|-------------------|
| `AdminWebsocket` | `AdminWebsocketPy` | `connect`, toutes les méthodes admin |
| `AppWebsocket` | `AppWebsocketPy` | `connect`, `call_zome` |
| `SigningCredentials` | `SigningCredentialsPy` | constructeur |
| `AppInfo` | `AppInfoPy` | propriétés en lecture |
| `CellId` | `CellIdPy` | constructeur, accesseurs |

Pattern à suivre (depuis `holochain-serialization-python`) :

```rust
#[cfg_attr(feature = "python-bindings", pyclass)]
pub struct AdminWebsocketPy {
    inner: AdminWebsocket,
    rt: tokio::runtime::Runtime,
}

#[cfg_attr(feature = "python-bindings", pymethods)]
impl AdminWebsocketPy {
    #[cfg(feature = "python-bindings")]
    #[new]
    fn connect(url: &str) -> PyResult<Self> {
        let rt = tokio::runtime::Runtime::new()
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        let inner = rt.block_on(AdminWebsocket::connect(url))
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(Self { inner, rt })
    }

    fn install_app(&self, payload: &InstallAppPayloadPy) -> PyResult<AppInfoPy> {
        self.rt.block_on(self.inner.install_app(payload.into()))
            .map(AppInfoPy::from)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
}
```

> **Note importante** : utiliser `block_on` pour exposer une API synchrone à Python.
> L'async Python peut appeler depuis un thread séparé si nécessaire.

### 2.5 Mettre à jour `pyproject.toml`

```toml
[build-system]
requires = ["maturin>=1.4,<2.0"]
build-backend = "maturin"

[tool.maturin]
features = ["python-bindings"]
python-source = "."

[project.optional-dependencies]
rust = []  # installers can pip install holochain-client[rust]
```

---

## Phase 3 — Mise à jour de l'API Python

### 3.1 Méthodes AdminClient manquantes (vérifier avec 0.6)

Comparer avec `holochain-client-js` pour identifier les nouvelles méthodes :
- `storage_info`
- `dump_conductor_state`
- `graft_records_onto_source_chain`
- `get_agent_info` / `add_agent_info`
- `issue_app_auth_token`

### 3.2 Authentification app (nouveau en 0.4+)

Depuis Holochain 0.4+, `AppWebsocket` requiert un token d'authentification :

```python
token = await admin_client.issue_app_auth_token(app_id)
app_client = await AppClient.connect(app_url, token)
```

### 3.3 Signals

Holochain 0.6 supporte les signaux (events push depuis le conductor) :

```python
app_client.on_signal(callback)  # nouveau
```

---

## Phase 4 — Guide de test Holochain

### 4.1 Prérequis

**Installer Nix** (si pas déjà fait) :
```bash
sh <(curl -L https://nixos.org/nix/install) --daemon
```

Activer les flakes :
```bash
mkdir -p ~/.config/nix
echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf
```

### 4.2 Entrer dans l'environnement de développement

```bash
# Depuis la racine du repo
nix develop

# Vérifier que les outils sont disponibles
holochain --version   # doit afficher 0.6.x ou 0.7.x
hc --version
```

### 4.3 Construire le fixture Rust (zome de test)

```bash
cd fixture
npm install
npm run build:happ    # compile le zome WASM + package le .happ
cd ..
```

Le fichier résultant : `fixture/workdir/fixture.happ`

### 4.4 Lancer les tests

```bash
# Activer l'env Python
source .venv/bin/activate   # ou : poetry shell

# Tous les tests (spawne un sandbox Holochain réel)
poetry run pytest -s

# Un seul test avec logs Rust
RUST_LOG=info poetry run pytest tests/api/app/client_test.py -k test_call_zome -s

# Tests admin seulement
poetry run pytest tests/api/admin/ -s
```

### 4.5 Comprendre le harness de test

Le `tests/harness.py` :
1. Lance `hc sandbox create` pour créer un répertoire sandbox isolé
2. Démarre `holochain` sur des ports aléatoires
3. Crée un `AdminClient` connecté au port admin
4. Installe le fixture `.happ`
5. Attache un port app et crée un `AppClient`
6. Nettoie tout à la fin du test (`__aexit__`)

### 4.6 Déboguer un sandbox manuellement

```bash
# Créer un sandbox
hc sandbox create --directory /tmp/test-sandbox

# Lancer holochain manuellement
RUST_LOG=info holochain --config-path /tmp/test-sandbox/conductor-config.yaml

# Se connecter avec le client Python (port admin par défaut : 0 = aléatoire)
# Voir les logs du conductor pour le port assigné
```

### 4.7 Build de l'extension Rust (Phase 2)

```bash
# Build debug (rapide)
maturin develop --features python-bindings

# Build release (pour distribution)
maturin build --release --features python-bindings

# Installer localement
pip install target/wheels/holochain_client-*.whl
```

---

## Ordre d'exécution recommandé

```
Phase 1.1 → 1.2 → 1.3   (mise à jour env, 1-2 jours)
     ↓
Phase 2.2 → 2.3 → 2.4   (scaffold Maturin + premiers wrappers, 3-5 jours)
     ↓
Phase 3.2 → 3.1          (auth token + nouvelles méthodes, 2-3 jours)
     ↓
Phase 2.5 + 3.3          (packaging + signals, 1-2 jours)
```

## Fichiers à modifier / créer

| Fichier | Action | Phase |
|---------|--------|-------|
| `flake.nix` | Mettre à jour pin Holochain 0.2 → 0.6 | 1.1 |
| `fixture/Cargo.toml` | hdk 0.2 → 0.6, hdi 0.3 → 0.7 | 1.2 |
| `fixture/zomes/*/src/lib.rs` | Adapter l'API HDK si changée | 1.2 |
| `Cargo.toml` | Nouveau — config Maturin | 2.2 |
| `src/lib.rs` | Nouveau — wrappers PyO3 | 2.4 |
| `pyproject.toml` | Passer à Maturin build backend | 2.5 |
| `holochain_client/api/admin/client.py` | Nouvelles méthodes 0.6 | 3.1 |
| `holochain_client/api/admin/types.py` | Nouveaux types 0.6 | 3.1 |
| `holochain_client/api/app/client.py` | Auth token, signals | 3.2-3.3 |
| `tests/harness.py` | Auth token dans le harness | 3.2 |
