"""Tests for types, hash utilities, and HoloHashMap."""

import pytest

from holochain_client.types import (
    AGENT_PREFIX,
    DNA_PREFIX,
    ENTRY_PREFIX,
    ACTION_PREFIX,
    HoloHashType,
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


class TestHoloHashType:
    def test_agent_prefix(self):
        h = fake_agent_pub_key(0)
        assert hash_type(h) == HoloHashType.AGENT

    def test_dna_prefix(self):
        h = fake_dna_hash(0)
        assert hash_type(h) == HoloHashType.DNA

    def test_entry_prefix(self):
        h = fake_entry_hash(0)
        assert hash_type(h) == HoloHashType.ENTRY

    def test_action_prefix(self):
        h = fake_action_hash(0)
        assert hash_type(h) == HoloHashType.ACTION

    def test_unknown_prefix_raises(self):
        with pytest.raises(ValueError, match="Unknown hash prefix"):
            hash_type(bytes([0, 0, 0]) + bytes(36))


class TestHashParts:
    def test_core_hash(self):
        h = fake_agent_pub_key(42)
        assert len(core_hash(h)) == 32
        assert core_hash(h) == bytes([42] * 32)

    def test_location_bytes_default(self):
        h = fake_agent_pub_key(0)
        assert location_bytes(h) == bytes(4)


class TestBase64:
    def test_roundtrip(self):
        h = fake_dna_hash(7)
        b64 = encode_hash_to_base64(h)
        assert isinstance(b64, str)
        assert decode_hash_from_base64(b64) == h


class TestFakeHashes:
    def test_all_are_39_bytes(self):
        for fn in (fake_agent_pub_key, fake_dna_hash, fake_entry_hash, fake_action_hash):
            assert len(fn(0)) == 39
            assert len(fn(255)) == 39


class TestHoloHashMap:
    def test_set_and_get(self):
        m: HoloHashMap[str] = HoloHashMap()
        h = fake_entry_hash(1)
        m[h] = "hello"
        assert m[h] == "hello"

    def test_get_by_b64(self):
        m: HoloHashMap[int] = HoloHashMap()
        h = fake_dna_hash(5)
        m[h] = 42
        b64 = encode_hash_to_base64(h)
        assert m[b64] == 42

    def test_contains(self):
        m: HoloHashMap[str] = HoloHashMap()
        h = fake_action_hash(3)
        assert h not in m
        m[h] = "x"
        assert h in m

    def test_len(self):
        m: HoloHashMap[int] = HoloHashMap()
        assert len(m) == 0
        m[fake_entry_hash(1)] = 1
        m[fake_entry_hash(2)] = 2
        assert len(m) == 2

    def test_delete(self):
        m: HoloHashMap[str] = HoloHashMap()
        h = fake_entry_hash(10)
        m[h] = "val"
        del m[h]
        assert h not in m

    def test_iter(self):
        m: HoloHashMap[int] = HoloHashMap()
        hashes = [fake_entry_hash(i) for i in range(3)]
        for i, h in enumerate(hashes):
            m[h] = i
        keys = list(m)
        assert len(keys) == 3

    def test_dna_hash_map_alias(self):
        m: DnaHashMap[str] = DnaHashMap()
        h = fake_dna_hash(1)
        m[h] = "test"
        assert m[h] == "test"
