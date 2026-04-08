"""Utility functions for working with HoloHashes."""

from __future__ import annotations

import os

from holochain_client.types import (
    AGENT_PREFIX,
    DNA_PREFIX,
    ENTRY_PREFIX,
    ACTION_PREFIX,
    EXTERNAL_PREFIX,
    AgentPubKey,
    DnaHash,
    EntryHash,
    ActionHash,
    ExternalHash,
    HoloHash,
    HoloHashType,
    encode_hash_to_base64,
    decode_hash_from_base64,
)


def hash_type(h: HoloHash) -> HoloHashType:
    """Determine the type of a HoloHash from its 3-byte prefix."""
    prefix = h[:3]
    if prefix == AGENT_PREFIX:
        return HoloHashType.AGENT
    elif prefix == DNA_PREFIX:
        return HoloHashType.DNA
    elif prefix == ENTRY_PREFIX:
        return HoloHashType.ENTRY
    elif prefix == ACTION_PREFIX:
        return HoloHashType.ACTION
    elif prefix == EXTERNAL_PREFIX:
        return HoloHashType.EXTERNAL
    else:
        raise ValueError(f"Unknown hash prefix: {prefix.hex()}")


def core_hash(h: HoloHash) -> bytes:
    """Extract the 32-byte core hash (without prefix and location bytes)."""
    return h[3:35]


def location_bytes(h: HoloHash) -> bytes:
    """Extract the 4-byte DHT location from a HoloHash."""
    return h[35:39]


def fake_agent_pub_key(seed: int = 0) -> AgentPubKey:
    """Generate a fake AgentPubKey for testing."""
    core = bytes([seed % 256] * 32)
    return AGENT_PREFIX + core + bytes(4)


def fake_dna_hash(seed: int = 0) -> DnaHash:
    """Generate a fake DnaHash for testing."""
    core = bytes([seed % 256] * 32)
    return DNA_PREFIX + core + bytes(4)


def fake_entry_hash(seed: int = 0) -> EntryHash:
    core = bytes([seed % 256] * 32)
    return ENTRY_PREFIX + core + bytes(4)


def fake_action_hash(seed: int = 0) -> ActionHash:
    core = bytes([seed % 256] * 32)
    return ACTION_PREFIX + core + bytes(4)
