"""Tests for wire protocol message encoding/decoding."""

import msgpack
import pytest


class TestWireProtocol:
    """Test that our wire messages match the expected Holochain format."""

    def test_request_format(self):
        """Verify the structure: {id, type: 'request', data: msgpack(payload)}"""
        payload = {"type": "list_apps", "value": None}
        encoded_payload = msgpack.packb(payload)
        wire_msg = msgpack.packb(
            {"id": 0, "type": "request", "data": encoded_payload}
        )
        decoded = msgpack.unpackb(wire_msg, raw=False)
        assert decoded["id"] == 0
        assert decoded["type"] == "request"
        inner = msgpack.unpackb(decoded["data"], raw=False)
        assert inner["type"] == "list_apps"
        assert inner["value"] is None

    def test_auth_format(self):
        """Verify auth message: {type: 'authenticate', data: msgpack({token})}"""
        token = b"test-token-bytes"
        payload = msgpack.packb({"token": token})
        wire_msg = msgpack.packb({"type": "authenticate", "data": payload})
        decoded = msgpack.unpackb(wire_msg, raw=False)
        assert decoded["type"] == "authenticate"
        inner = msgpack.unpackb(decoded["data"], raw=False)
        assert inner["token"] == token

    def test_response_format(self):
        """Simulate a conductor response and verify decoding."""
        inner = {"type": "agent_pub_key_generated", "value": b"\x84\x20\x24" + bytes(36)}
        encoded_inner = msgpack.packb(inner)
        wire_msg = msgpack.packb({"id": 5, "type": "response", "data": encoded_inner})
        decoded = msgpack.unpackb(wire_msg, raw=False)
        assert decoded["id"] == 5
        assert decoded["type"] == "response"
        result = msgpack.unpackb(decoded["data"], raw=False)
        assert result["type"] == "agent_pub_key_generated"

    def test_signal_format(self):
        """Simulate a signal message."""
        signal_data = {
            "type": "app",
            "value": {
                "cell_id": [bytes(39), bytes(39)],
                "zome_name": "test",
                "signal": msgpack.packb({"msg": "hello"}),
            },
        }
        wire_msg = msgpack.packb(
            {"type": "signal", "data": msgpack.packb(signal_data)}
        )
        decoded = msgpack.unpackb(wire_msg, raw=False)
        assert decoded["type"] == "signal"
        signal = msgpack.unpackb(decoded["data"], raw=False)
        assert signal["type"] == "app"
        payload = msgpack.unpackb(signal["value"]["signal"], raw=False)
        assert payload["msg"] == "hello"

    def test_error_response_format(self):
        """Verify error response structure."""
        error = {"type": "error", "value": {"type": "RibosomeError", "value": "entry not found"}}
        encoded = msgpack.packb(error)
        wire_msg = msgpack.packb({"id": 1, "type": "response", "data": encoded})
        decoded = msgpack.unpackb(wire_msg, raw=False)
        result = msgpack.unpackb(decoded["data"], raw=False)
        assert result["type"] == "error"
        assert result["value"]["type"] == "RibosomeError"

    def test_tagged_request_encoding(self):
        """Verify install_app request with nested payload."""
        payload = {
            "type": "install_app",
            "value": {
                "source": {"type": "path", "value": "./test.happ"},
                "agent_key": bytes(39),
                "installed_app_id": "my-app",
            },
        }
        encoded = msgpack.packb(payload)
        decoded = msgpack.unpackb(encoded, raw=False)
        assert decoded["type"] == "install_app"
        assert decoded["value"]["installed_app_id"] == "my-app"
        assert decoded["value"]["source"]["type"] == "path"
