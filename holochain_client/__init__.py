"""holochain_client: A Python client for the Holochain Conductor API.

Compatible with Holochain 0.6.x / 0.7.x.

Usage::

    from holochain_client import AdminWebsocket, AppWebsocket

    admin = await AdminWebsocket.connect("ws://127.0.0.1:65000")
    agent_key = await admin.generate_agent_pub_key()
    ...
"""

try:
    from holochain_client._rust_adapter import AdminWebsocket, AppWebsocket
except ImportError:
    from holochain_client.api.admin.websocket import AdminWebsocket  # type: ignore[assignment]
    from holochain_client.api.app.websocket import AppWebsocket  # type: ignore[assignment]
from holochain_client.api.client import HolochainError, WsClient
from holochain_client.api.signing import (
    SigningCredentials,
    generate_signing_key_pair,
    get_signing_credentials,
    set_signing_credentials,
    random_cap_secret,
    random_nonce,
    sign_zome_call,
)
from holochain_client.types import (
    AgentPubKey,
    ActionHash,
    AnyDhtHash,
    AppAuthenticationToken,
    AppInfo,
    AppStatus,
    AppStatusFilter,
    CapSecret,
    CellId,
    CellType,
    ClonedCell,
    DnaHash,
    EntryHash,
    ExternalHash,
    FunctionName,
    HoloHash,
    HoloHashB64,
    HoloHashType,
    InstalledAppId,
    MembraneProof,
    NetworkSeed,
    Nonce256Bit,
    ProvisionedCell,
    RoleName,
    Signature,
    StemCell,
    Timestamp,
    WasmHash,
    ZomeName,
    encode_hash_to_base64,
    decode_hash_from_base64,
)

from holochain_client.utils.hash import (
    hash_type,
    core_hash,
    location_bytes,
    fake_agent_pub_key,
    fake_dna_hash,
    fake_entry_hash,
    fake_action_hash,
)
from holochain_client.utils.hashmap import HoloHashMap, DnaHashMap
from holochain_client.environments.launcher import (
    get_launcher_environment,
    LauncherEnvironment,
)

__all__ = [
    # Clients
    "AdminWebsocket",
    "AppWebsocket",
    "WsClient",
    "HolochainError",
    # Signing
    "SigningCredentials",
    "generate_signing_key_pair",
    "get_signing_credentials",
    "set_signing_credentials",
    "random_cap_secret",
    "random_nonce",
    "sign_zome_call",
    # Types
    "AgentPubKey",
    "ActionHash",
    "AnyDhtHash",
    "AppAuthenticationToken",
    "AppInfo",
    "AppStatus",
    "AppStatusFilter",
    "CapSecret",
    "CellId",
    "CellType",
    "ClonedCell",
    "DnaHash",
    "EntryHash",
    "ExternalHash",
    "FunctionName",
    "HoloHash",
    "HoloHashB64",
    "HoloHashType",
    "InstalledAppId",
    "MembraneProof",
    "NetworkSeed",
    "Nonce256Bit",
    "ProvisionedCell",
    "RoleName",
    "Signature",
    "StemCell",
    "Timestamp",
    "WasmHash",
    "ZomeName",
    "encode_hash_to_base64",
    "decode_hash_from_base64",
    # Utils
    "HoloHashMap",
    "DnaHashMap",
    "hash_type",
    "core_hash",
    "location_bytes",
    "fake_agent_pub_key",
    "fake_dna_hash",
    "fake_entry_hash",
    "fake_action_hash",
    # Environment
    "get_launcher_environment",
    "LauncherEnvironment",
]

__version__ = "0.2.0"
