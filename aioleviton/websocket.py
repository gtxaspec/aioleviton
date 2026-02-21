"""WebSocket connection manager for the Leviton real-time push API."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
from collections.abc import Callable
from typing import Any

import aiohttp

from .const import USER_AGENT, WEBSOCKET_URL
from .exceptions import LevitonConnectionError

_LOGGER = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT = 60.0  # seconds
MAX_RECONNECT_DELAY = 16.0  # seconds


class LevitonWebSocket:
    """WebSocket client for Leviton real-time push notifications."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        user_id: str,
        user: dict[str, Any],
        token_created: str,
        token_ttl: int,
    ) -> None:
        """Initialize the WebSocket client.

        Args:
            session: aiohttp ClientSession for the connection.
            token: Authentication token string.
            user_id: Authenticated user ID.
            user: User profile dict from login response.
            token_created: ISO 8601 token creation timestamp.
            token_ttl: Token time-to-live in seconds.
        """
        self._session = session
        self._token = token
        self._user_id = user_id
        self._user = user
        self._token_created = token_created
        self._token_ttl = token_ttl
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._connection_id: str | None = None
        self._subscriptions: set[tuple[str, str | int]] = set()
        self._notification_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._disconnect_callbacks: list[Callable[[], None]] = []
        self._listen_task: asyncio.Task[None] | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        """Return True if the WebSocket is connected and ready."""
        return self._connected

    @property
    def subscriptions(self) -> set[tuple[str, str | int]]:
        """Return the set of active subscriptions (model_name, model_id)."""
        return self._subscriptions.copy()

    async def connect(self) -> None:
        """Connect to the WebSocket server and authenticate.

        Raises:
            LevitonConnectionError: If the connection fails.
        """
        try:
            self._ws = await self._session.ws_connect(
                WEBSOCKET_URL,
                heartbeat=HEARTBEAT_TIMEOUT / 2,
                headers={"user-agent": USER_AGENT},
            )
        except (aiohttp.ClientError, OSError) as err:
            raise LevitonConnectionError(f"WebSocket connection failed: {err}") from err

        # Send authentication message
        auth_msg = {
            "token": {
                "id": self._token,
                "ttl": self._token_ttl,
                "scopes": None,
                "created": self._token_created,
                "userId": self._user_id,
                "user": self._user,
                "rememberMe": False,
            }
        }
        await self._ws.send_json(auth_msg)

        # Wait for ready status
        ready = False
        for _ in range(10):
            try:
                msg = await asyncio.wait_for(self._ws.receive(), timeout=10.0)
            except TimeoutError:
                break

            if msg.type in (
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
                aiohttp.WSMsgType.CLOSING,
            ):
                raise LevitonConnectionError("WebSocket closed during auth")

            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("type") == "status" and data.get("status") == "ready":
                    self._connection_id = data.get("connectionId")
                    ready = True
                    break

        if not ready:
            await self._ws.close()
            raise LevitonConnectionError("WebSocket did not reach ready state")

        self._connected = True
        _LOGGER.debug("WebSocket connected (connectionId=%s)", self._connection_id)

        # Start listening for messages
        self._listen_task = asyncio.create_task(self._listen())

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server.

        Subscriptions are preserved so callers can re-subscribe after reconnect.
        Call reset() for full teardown including subscription clearing.
        """
        self._connected = False
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listen_task
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    async def reset(self) -> None:
        """Fully disconnect and clear all subscriptions and callbacks."""
        await self.disconnect()
        self._subscriptions.clear()
        self._notification_callbacks.clear()
        self._disconnect_callbacks.clear()

    async def subscribe(self, model_name: str, model_id: str | int) -> None:
        """Subscribe to real-time updates for a model.

        Args:
            model_name: The model type (e.g., "IotWhem", "ResidentialBreakerPanel").
            model_id: The model instance ID.
        """
        if not self._ws or self._ws.closed:
            raise LevitonConnectionError("WebSocket not connected")

        msg = {
            "type": "subscribe",
            "subscription": {"modelName": model_name, "modelId": model_id},
        }
        await self._ws.send_json(msg)
        self._subscriptions.add((model_name, model_id))
        _LOGGER.debug("Subscribed to %s/%s", model_name, model_id)

    async def unsubscribe(self, model_name: str, model_id: str | int) -> None:
        """Unsubscribe from a model's updates.

        Args:
            model_name: The model type.
            model_id: The model instance ID.
        """
        if not self._ws or self._ws.closed:
            return

        msg = {
            "type": "unsubscribe",
            "subscription": {"modelName": model_name, "modelId": model_id},
        }
        await self._ws.send_json(msg)
        self._subscriptions.discard((model_name, model_id))
        _LOGGER.debug("Unsubscribed from %s/%s", model_name, model_id)

    def on_notification(
        self, callback: Callable[[dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Register a callback for incoming notifications.

        Args:
            callback: Function called with the notification data dict.

        Returns:
            A function to unregister the callback.
        """
        self._notification_callbacks.append(callback)

        def remove() -> None:
            self._notification_callbacks.remove(callback)

        return remove

    def on_disconnect(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a callback for disconnect events.

        Args:
            callback: Function called when the WebSocket disconnects.

        Returns:
            A function to unregister the callback.
        """
        self._disconnect_callbacks.append(callback)

        def remove() -> None:
            self._disconnect_callbacks.remove(callback)

        return remove

    async def _listen(self) -> None:
        """Listen for incoming WebSocket messages."""
        assert self._ws is not None

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        _LOGGER.warning(
                            "Received non-JSON WebSocket message: %s",
                            msg.data[:200],
                        )
                        continue

                    if data.get("type") == "notification":
                        notification = data.get("notification", {})
                        for callback in self._notification_callbacks:
                            try:
                                callback(notification)
                            except Exception:
                                _LOGGER.exception("Error in notification callback")

                elif msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                    aiohttp.WSMsgType.CLOSING,
                ):
                    break

        except asyncio.CancelledError:
            return
        except Exception:
            _LOGGER.exception("WebSocket listen error")
        finally:
            self._connected = False
            for dc_callback in self._disconnect_callbacks:
                try:
                    dc_callback()
                except Exception:
                    _LOGGER.exception("Error in disconnect callback")

    async def reconnect(self) -> None:
        """Reconnect and re-subscribe to all previous subscriptions.

        Call this after a disconnect to re-establish the connection and
        restore all previous subscriptions automatically.

        Raises:
            LevitonConnectionError: If the connection or auth fails.
        """
        saved = self._subscriptions.copy()
        await self.disconnect()
        await self.connect()
        for model_name, model_id in saved:
            await self.subscribe(model_name, model_id)

    @staticmethod
    def reconnect_delay(attempts: int) -> float:
        """Calculate reconnection delay with exponential backoff and jitter.

        Args:
            attempts: Number of previous reconnection attempts.

        Returns:
            Delay in seconds before next reconnection attempt.
        """
        delay: float = min(
            1.0 * (2**attempts) * (0.5 * random.random() + 0.75),
            MAX_RECONNECT_DELAY,
        )
        return delay
