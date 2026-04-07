"""HDK (Holochain Development Kit) types for working with Holochain data.

These mirror the types from holochain_zome_types that appear in zome call
responses, enabling typed deserialization of records, actions, entries, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from holochain_client.types import (
    ActionHash,
    AgentPubKey,
    AnyDhtHash,
    DnaHash,
    EntryHash,
    HoloHash,
    Signature,
    Timestamp,
)


# ---------------------------------------------------------------------------
# Actions (formerly Headers)
# ---------------------------------------------------------------------------


class ActionType(str, Enum):
    DNA = "Dna"
    AGENT_VALIDATION_PKG = "AgentValidationPkg"
    INIT_ZOMES_COMPLETE = "InitZomesComplete"
    CREATE_LINK = "CreateLink"
    DELETE_LINK = "DeleteLink"
    OPEN_CHAIN = "OpenChain"
    CLOSE_CHAIN = "CloseChain"
    CREATE = "Create"
    UPDATE = "Update"
    DELETE = "Delete"


@dataclass
class SignedActionHashed:
    hashed: dict[str, Any]  # { hash: ActionHash, content: Action }
    signature: Signature = b""


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------


class EntryType(str, Enum):
    AGENT = "Agent"
    APP = "App"
    CAP_CLAIM = "CapClaim"
    CAP_GRANT = "CapGrant"


@dataclass
class Entry:
    entry_type: EntryType
    entry: Any = None


# ---------------------------------------------------------------------------
# Records (Action + Entry pairs as stored on the source chain / DHT)
# ---------------------------------------------------------------------------


@dataclass
class Record:
    signed_action: SignedActionHashed
    entry: Entry | None = None


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


@dataclass
class Link:
    author: AgentPubKey = b""
    target: AnyDhtHash = b""
    timestamp: Timestamp = 0
    zome_index: int = 0
    link_type: int = 0
    tag: bytes = b""
    create_link_hash: ActionHash = b""


# ---------------------------------------------------------------------------
# Details (used in get_details responses)
# ---------------------------------------------------------------------------


@dataclass
class RecordDetails:
    record: Record
    validation_status: str = ""
    deletes: list[SignedActionHashed] = field(default_factory=list)
    updates: list[SignedActionHashed] = field(default_factory=list)


@dataclass
class EntryDetails:
    entry: Entry
    actions: list[SignedActionHashed] = field(default_factory=list)
    rejected_actions: list[SignedActionHashed] = field(default_factory=list)
    deletes: list[SignedActionHashed] = field(default_factory=list)
    updates: list[SignedActionHashed] = field(default_factory=list)
    entry_dht_status: str = ""


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class GrantedFunctionsType(str, Enum):
    ALL = "All"
    LISTED = "Listed"


@dataclass
class ZomeCallCapGrant:
    tag: str = ""
    functions: dict[str, Any] = field(default_factory=dict)
    access: dict[str, Any] = field(default_factory=dict)
