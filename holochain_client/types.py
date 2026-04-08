"""Core Holochain types mirroring holochain_zome_types and holochain_conductor_api."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NewType

# ---------------------------------------------------------------------------
# HoloHash types  (39-byte: 3-byte prefix + 32-byte hash + 4-byte DHT loc)
# ---------------------------------------------------------------------------

HoloHash = bytes  # length 39
AgentPubKey = HoloHash
DnaHash = HoloHash
WasmHash = HoloHash
EntryHash = HoloHash
ActionHash = HoloHash
AnyDhtHash = HoloHash
ExternalHash = HoloHash
DhtOpHash = HoloHash
WarrantHash = HoloHash

HoloHashB64 = str
AgentPubKeyB64 = HoloHashB64
DnaHashB64 = HoloHashB64
EntryHashB64 = HoloHashB64
ActionHashB64 = HoloHashB64
AnyDhtHashB64 = HoloHashB64

# Prefixes used in HoloHash construction
AGENT_PREFIX = bytes([132, 32, 36])
DNA_PREFIX = bytes([132, 45, 36])
ENTRY_PREFIX = bytes([132, 33, 36])
ACTION_PREFIX = bytes([132, 41, 36])
EXTERNAL_PREFIX = bytes([132, 55, 36])


class HoloHashType(str, Enum):
    AGENT = "agent"
    ENTRY = "entry"
    DHT_OP = "dhtop"
    WARRANT = "warrant"
    DNA = "dna"
    ACTION = "action"
    WASM = "wasm"
    EXTERNAL = "external"


# ---------------------------------------------------------------------------
# Fundamental compound types
# ---------------------------------------------------------------------------

CellId = tuple[DnaHash, AgentPubKey]
"""A cell is uniquely identified by its DNA hash and Agent public key."""

InstalledAppId = str
RoleName = str
ZomeName = str
FunctionName = str
NetworkSeed = str
DnaProperties = Any
MembraneProof = bytes
Signature = bytes
CapSecret = bytes  # 64 bytes
Nonce256Bit = bytes  # 32 bytes
Timestamp = int  # microseconds since epoch

AppAuthenticationToken = bytes


# ---------------------------------------------------------------------------
# Cell types
# ---------------------------------------------------------------------------


class CellType(str, Enum):
    PROVISIONED = "provisioned"
    CLONED = "cloned"
    STEM = "stem"


@dataclass
class ProvisionedCell:
    cell_id: CellId
    dna_modifiers: dict[str, Any] = field(default_factory=dict)
    name: str = ""


@dataclass
class ClonedCell:
    cell_id: CellId
    clone_id: str = ""
    original_dna_hash: DnaHash = b""
    dna_modifiers: dict[str, Any] = field(default_factory=dict)
    name: str = ""
    enabled: bool = True


@dataclass
class StemCell:
    original_dna_hash: DnaHash = b""
    dna_modifiers: dict[str, Any] = field(default_factory=dict)
    name: str = ""


@dataclass
class CellInfo:
    type: CellType
    value: ProvisionedCell | ClonedCell | StemCell


# ---------------------------------------------------------------------------
# App info
# ---------------------------------------------------------------------------


class AppStatus(str, Enum):
    RUNNING = "running"
    DISABLED = "disabled"
    AWAITING_MEMPROOFS = "awaiting_memproofs"
    PAUSED = "paused"


@dataclass
class AppInfo:
    installed_app_id: InstalledAppId
    cell_info: dict[RoleName, list[dict[str, Any]]]
    status: Any = None
    agent_pub_key: AgentPubKey = b""
    manifest: Any = None
    installed_at: Any = None


class AppStatusFilter(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"


# ---------------------------------------------------------------------------
# Base64 encoding helpers
# ---------------------------------------------------------------------------


def encode_hash_to_base64(hash_bytes: HoloHash) -> HoloHashB64:
    """Encode a HoloHash to a URL-safe base64 string."""
    return base64.b64encode(hash_bytes).decode("utf-8")


def decode_hash_from_base64(hash_b64: HoloHashB64) -> HoloHash:
    """Decode a URL-safe base64 string to a HoloHash."""
    return base64.b64decode(hash_b64)
