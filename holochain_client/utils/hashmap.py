"""HoloHashMap: a dictionary keyed by HoloHash with base64 normalization.

In Python, bytes are hashable and can be dict keys directly, unlike JavaScript.
However, HoloHashes received from different sources (msgpack, base64 strings,
conductor responses) may need normalization. This class handles that transparently.
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import TypeVar, Generic

from holochain_client.types import (
    DnaHash,
    HoloHash,
    encode_hash_to_base64,
    decode_hash_from_base64,
)

V = TypeVar("V")


class HoloHashMap(MutableMapping[HoloHash, V], Generic[V]):
    """A dict-like container keyed by HoloHash bytes.

    Accepts both raw bytes and base64 strings as keys, normalizing internally.
    """

    def __init__(self) -> None:
        self._data: dict[bytes, V] = {}

    @staticmethod
    def _normalize(key: HoloHash | str) -> bytes:
        if isinstance(key, str):
            return decode_hash_from_base64(key)
        return bytes(key)

    def __setitem__(self, key: HoloHash | str, value: V) -> None:
        self._data[self._normalize(key)] = value

    def __getitem__(self, key: HoloHash | str) -> V:
        return self._data[self._normalize(key)]

    def __delitem__(self, key: HoloHash | str) -> None:
        del self._data[self._normalize(key)]

    def __contains__(self, key: object) -> bool:
        if isinstance(key, (bytes, str)):
            return self._normalize(key) in self._data
        return False

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        items = ", ".join(
            f"{encode_hash_to_base64(k)}: {v!r}" for k, v in self._data.items()
        )
        return f"HoloHashMap({{{items}}})"


class DnaHashMap(HoloHashMap[V], Generic[V]):
    """Convenience alias for maps keyed by DnaHash.

    Useful for mapping DNA hashes to role-specific data like cell info,
    signing credentials, or cached state.
    """
    pass
