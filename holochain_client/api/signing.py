"""Zome call signing: keypair generation, credential storage, and call signing.

Mirrors the JS client's zome-call-signing.ts and the Rust client's signing module.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any

import msgpack
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from holochain_client.types import (
    AGENT_PREFIX,
    AgentPubKey,
    CapSecret,
    CellId,
    Nonce256Bit,
    Timestamp,
    encode_hash_to_base64,
)


@dataclass
class SigningCredentials:
    """Stored credentials for signing zome calls on behalf of a cell."""

    cap_secret: CapSecret
    key_pair: Ed25519PrivateKey
    signing_key: AgentPubKey  # 39-byte agent pub key derived from the signing public key


# ---------------------------------------------------------------------------
# Global credential store  (cell_id_b64 -> SigningCredentials)
# ---------------------------------------------------------------------------

_credentials_store: dict[str, SigningCredentials] = {}


def _cell_id_key(cell_id: CellId) -> str:
    return encode_hash_to_base64(cell_id[0]) + encode_hash_to_base64(cell_id[1])


def get_signing_credentials(cell_id: CellId) -> SigningCredentials | None:
    return _credentials_store.get(_cell_id_key(cell_id))


def set_signing_credentials(cell_id: CellId, creds: SigningCredentials) -> None:
    _credentials_store[_cell_id_key(cell_id)] = creds


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


def generate_signing_key_pair(
    agent_pub_key: AgentPubKey | None = None,
) -> tuple[Ed25519PrivateKey, AgentPubKey]:
    """Generate an ed25519 keypair and derive an AgentPubKey from the public key.

    The last 4 bytes (DHT location) are copied from agent_pub_key if provided,
    otherwise set to [0,0,0,0] since this identity is only used for signing.
    """
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes_raw()

    location_bytes = agent_pub_key[35:39] if agent_pub_key else bytes(4)
    signing_key = AGENT_PREFIX + public_bytes + location_bytes
    assert len(signing_key) == 39

    return private_key, signing_key


def random_cap_secret() -> CapSecret:
    return os.urandom(64)


def random_nonce() -> Nonce256Bit:
    return os.urandom(32)


def get_nonce_expiration() -> Timestamp:
    """5 minutes from now, in microseconds."""
    return int((time.time() + 5 * 60) * 1_000_000)


# ---------------------------------------------------------------------------
# Signing a zome call
# ---------------------------------------------------------------------------


@dataclass
class SignedZomeCall:
    """The wire format for a signed zome call (bytes + signature)."""

    bytes: bytes
    signature: bytes


def sign_zome_call(request: dict[str, Any]) -> SignedZomeCall:
    """Sign a zome call request using the stored signing credentials.

    The request dict must contain: cell_id, zome_name, fn_name, payload.
    Optional: provenance, cap_secret, nonce, expires_at.
    """
    cell_id: CellId = request["cell_id"]
    creds = get_signing_credentials(cell_id)
    if creds is None:
        raise ValueError(
            f"No signing credentials authorized for cell "
            f"[{encode_hash_to_base64(cell_id[0])}, {encode_hash_to_base64(cell_id[1])}]"
        )

    # Build the canonical zome call params
    zome_call_params = {
        "cap_secret": creds.cap_secret,
        "cell_id": list(cell_id),
        "zome_name": request["zome_name"],
        "fn_name": request["fn_name"],
        "provenance": creds.signing_key,
        "payload": msgpack.packb(request.get("payload")),
        "nonce": request.get("nonce") or random_nonce(),
        "expires_at": request.get("expires_at") or get_nonce_expiration(),
    }

    encoded = msgpack.packb(zome_call_params)
    # Hash with SHA-512 before signing (matching the JS client)
    data_hash = hashlib.sha512(encoded).digest()
    signature = creds.key_pair.sign(data_hash)

    return SignedZomeCall(bytes=encoded, signature=signature)
