"""Tests for the signing module (no conductor needed)."""

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from holochain_client.api.signing import (
    SigningCredentials,
    generate_signing_key_pair,
    get_signing_credentials,
    set_signing_credentials,
    random_cap_secret,
    random_nonce,
    get_nonce_expiration,
    sign_zome_call,
)
from holochain_client.utils.hash import fake_agent_pub_key, fake_dna_hash


class TestKeyGeneration:
    def test_generate_signing_key_pair_length(self):
        private_key, signing_key = generate_signing_key_pair()
        assert len(signing_key) == 39

    def test_signing_key_has_agent_prefix(self):
        _, signing_key = generate_signing_key_pair()
        assert signing_key[:3] == bytes([132, 32, 36])

    def test_default_location_bytes_are_zero(self):
        _, signing_key = generate_signing_key_pair()
        assert signing_key[35:] == bytes(4)

    def test_location_bytes_from_agent_key(self):
        agent_key = fake_agent_pub_key(42)
        # Overwrite location bytes
        agent_key = agent_key[:35] + bytes([1, 2, 3, 4])
        _, signing_key = generate_signing_key_pair(agent_key)
        assert signing_key[35:] == bytes([1, 2, 3, 4])

    def test_private_key_can_sign(self):
        private_key, _ = generate_signing_key_pair()
        data = b"test data"
        signature = private_key.sign(data)
        assert len(signature) == 64
        # Verify signature
        public_key = private_key.public_key()
        public_key.verify(signature, data)  # Raises on failure


class TestCredentialsStore:
    def test_set_and_get(self):
        dna_hash = fake_dna_hash(1)
        agent_key = fake_agent_pub_key(1)
        cell_id = (dna_hash, agent_key)

        private_key, signing_key = generate_signing_key_pair()
        cap_secret = random_cap_secret()
        creds = SigningCredentials(cap_secret, private_key, signing_key)

        set_signing_credentials(cell_id, creds)
        retrieved = get_signing_credentials(cell_id)
        assert retrieved is not None
        assert retrieved.cap_secret == cap_secret
        assert retrieved.signing_key == signing_key

    def test_get_missing_returns_none(self):
        cell_id = (fake_dna_hash(99), fake_agent_pub_key(99))
        assert get_signing_credentials(cell_id) is None


class TestRandomGenerators:
    def test_cap_secret_length(self):
        assert len(random_cap_secret()) == 64

    def test_nonce_length(self):
        assert len(random_nonce()) == 32

    def test_nonce_expiration_is_future(self):
        import time
        now_us = int(time.time() * 1_000_000)
        exp = get_nonce_expiration()
        assert exp > now_us
        # Should be roughly 5 minutes from now
        assert exp - now_us > 4 * 60 * 1_000_000
        assert exp - now_us < 6 * 60 * 1_000_000


class TestSignZomeCall:
    def test_sign_zome_call_produces_signed_output(self):
        dna_hash = fake_dna_hash(10)
        agent_key = fake_agent_pub_key(10)
        cell_id = (dna_hash, agent_key)

        private_key, signing_key = generate_signing_key_pair()
        cap_secret = random_cap_secret()
        set_signing_credentials(
            cell_id, SigningCredentials(cap_secret, private_key, signing_key)
        )

        request = {
            "cell_id": cell_id,
            "zome_name": "test_zome",
            "fn_name": "test_fn",
            "payload": {"hello": "world"},
        }

        signed = sign_zome_call(request)
        assert len(signed.signature) == 64
        assert len(signed.bytes) > 0

    def test_sign_without_credentials_raises(self):
        cell_id = (fake_dna_hash(200), fake_agent_pub_key(200))
        request = {
            "cell_id": cell_id,
            "zome_name": "z",
            "fn_name": "f",
            "payload": None,
        }
        with pytest.raises(ValueError, match="No signing credentials"):
            sign_zome_call(request)
