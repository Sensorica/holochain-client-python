"""Low-level WebSocket client implementing the Holochain conductor wire protocol.

The wire protocol is msgpack-encoded messages with the shape:
  Request:  { id: int, type: "request", data: msgpack(payload) }
  Response: { id: int, type: "response", data: msgpack(payload) | null }
  Signal:   { type: "signal", data: msgpack(signal_payload) }
  Auth:     { type: "authenticate", data: msgpack({ token: bytes }) }
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

import msgpack
import websockets
from websockets.asyncio.client import ClientConnection

from holochain_client.types import AppAuthenticationToken

logger = logging.getLogger("holochain_client")


class HolochainError(Exception):
    """Error returned by the Holochain conductor."""

    def __init__(self, name: str, message: str) -> None:
        self.name = name
        super().__init__(f"{name}: {message}")


SignalHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


class WsClient:
    """A WebSocket client for the Holochain conductor wire protocol.

    Handles request/response correlation, signal dispatch, authentication,
    and automatic reconnection for app websockets.
    """

    def __init__(
        self,
        ws: ClientConnection,
        url: str | None = None,
    ) -> None:
        self._ws = ws
        self._url = url
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._index = 0
        self._signal_handlers: list[SignalHandler] = []
        self._listen_task: asyncio.Task[None] | None = None
        self._closed = False
        self._auth_token: AppAuthenticationToken | None = None

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    async def connect(cls, url: str, **kwargs: Any) -> WsClient:
        """Open a websocket connection to the conductor.

        Holochain 0.6+ requires an Origin header on every WebSocket
        handshake. The websockets library does not send one by default,
        so we inject "localhost" unless the caller overrides it.
        """
        kwargs.setdefault("origin", "localhost")
        ws = await websockets.connect(url, **kwargs)
        client = cls(ws, url=url)
        client._listen_task = asyncio.create_task(client._listen())
        return client

    # ------------------------------------------------------------------
    # Authentication (required for app interfaces since Holochain 0.3+)
    # ------------------------------------------------------------------

    async def authenticate(self, token: AppAuthenticationToken) -> None:
        """Send an authentication message (non-request, no id)."""
        self._auth_token = token
        payload = msgpack.packb({"token": token})
        msg = msgpack.packb({"type": "authenticate", "data": payload})
        await self._ws.send(msg)
        # The conductor does not reply to auth; it simply closes on invalid token.
        # We wait briefly to catch an immediate close.
        await asyncio.sleep(0.05)
        if self._closed:
            raise HolochainError(
                "InvalidTokenError",
                "Connection closed after authentication, likely invalid token.",
            )

    # ------------------------------------------------------------------
    # Reconnection
    # ------------------------------------------------------------------

    async def _reconnect(self) -> None:
        """Attempt to reconnect and re-authenticate (app websockets only)."""
        if not self._url:
            raise HolochainError("WebsocketClosedError", "Websocket closed and no URL for reconnect")

        logger.info("Attempting reconnection to %s", self._url)
        ws = await websockets.connect(self._url)
        self._ws = ws
        self._closed = False

        if self._listen_task:
            self._listen_task.cancel()
        self._listen_task = asyncio.create_task(self._listen())

        if self._auth_token:
            payload = msgpack.packb({"token": self._auth_token})
            msg = msgpack.packb({"type": "authenticate", "data": payload})
            await self._ws.send(msg)
            await asyncio.sleep(0.05)
            if self._closed:
                raise HolochainError("ReconnectFailed", "Reconnect auth failed")

    # ------------------------------------------------------------------
    # Request / response
    # ------------------------------------------------------------------

    async def request(self, payload: dict[str, Any], timeout: float = 60.0) -> Any:
        """Send a tagged request and await the conductor's response.

        If the websocket is closed and a URL + auth token are available,
        attempts automatic reconnection before sending.
        """
        if self._closed and self._url:
            await self._reconnect()
        elif self._closed:
            raise HolochainError("WebsocketClosedError", "Websocket is not open")

        req_id = self._index
        self._index += 1

        encoded_payload = msgpack.packb(payload)
        wire_msg = msgpack.packb(
            {"id": req_id, "type": "request", "data": encoded_payload}
        )

        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        try:
            await self._ws.send(wire_msg)
        except websockets.exceptions.ConnectionClosed:
            self._pending.pop(req_id, None)
            if self._url:
                await self._reconnect()
                # Retry once after reconnection
                self._pending[req_id] = future
                await self._ws.send(wire_msg)
            else:
                raise HolochainError("WebsocketClosedError", "Connection lost during send")

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise HolochainError("TimeoutError", f"Request {req_id} timed out after {timeout}s")

        return result

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def on_signal(self, handler: SignalHandler) -> Callable[[], None]:
        """Register a signal handler. Returns an unsubscribe function."""
        self._signal_handlers.append(handler)

        def unsubscribe() -> None:
            try:
                self._signal_handlers.remove(handler)
            except ValueError:
                pass

        return unsubscribe

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the websocket connection."""
        self._closed = True
        if self._listen_task:
            self._listen_task.cancel()
        await self._ws.close()
        # Reject all pending
        for req_id, fut in self._pending.items():
            if not fut.done():
                fut.set_exception(
                    HolochainError("ConnectionClosed", f"Connection closed with pending request {req_id}")
                )
        self._pending.clear()

    # ------------------------------------------------------------------
    # Internal listener
    # ------------------------------------------------------------------

    async def _listen(self) -> None:
        """Background task that dispatches incoming messages."""
        try:
            async for raw in self._ws:
                if isinstance(raw, str):
                    raw = raw.encode()
                msg = msgpack.unpackb(raw, raw=False)
                msg_type = msg.get("type")

                if msg_type == "response":
                    self._handle_response(msg)
                elif msg_type == "signal":
                    await self._handle_signal(msg)
                else:
                    logger.warning("Unknown message type: %s", msg_type)
        except websockets.exceptions.ConnectionClosed:
            self._closed = True
        except asyncio.CancelledError:
            pass

    def _handle_response(self, msg: dict[str, Any]) -> None:
        req_id = msg["id"]
        future = self._pending.pop(req_id, None)
        if future is None:
            logger.warning("Response for unknown request id=%d", req_id)
            return

        data = msg.get("data")
        if data is None:
            future.set_exception(HolochainError("ResponseCanceled", "Response canceled by conductor"))
            return

        decoded = msgpack.unpackb(data, raw=False)

        # Check for error responses
        if isinstance(decoded, dict) and decoded.get("type") == "error":
            err = decoded.get("value", {})
            if isinstance(err, dict):
                future.set_exception(
                    HolochainError(err.get("type", "UnknownError"), str(err.get("value", "")))
                )
            else:
                future.set_exception(HolochainError("ConductorError", str(err)))
            return

        future.set_result(decoded)

    async def _handle_signal(self, msg: dict[str, Any]) -> None:
        data = msg.get("data")
        if data is None:
            return
        signal = msgpack.unpackb(data, raw=False)
        for handler in self._signal_handlers:
            try:
                result = handler(signal)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("Error in signal handler")
