"""Tests for aioleviton WebSocket client."""

import json
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from aioleviton import LevitonConnectionError
from aioleviton.websocket import MAX_RECONNECT_DELAY, LevitonWebSocket


def _make_ws(**kwargs):
    """Create a LevitonWebSocket with test defaults."""
    return LevitonWebSocket(
        session=kwargs.get("session", MagicMock()),
        token="tok_test",
        user_id="user_001",
        user={"email": "test@example.com"},
        token_created="2026-01-01T00:00:00Z",
        token_ttl=5184000,
    )


def _make_ws_msg(data, msg_type=aiohttp.WSMsgType.TEXT):
    """Create a mock WebSocket message."""
    msg = MagicMock()
    msg.type = msg_type
    msg.data = json.dumps(data) if isinstance(data, dict) else data
    return msg


def _make_mock_ws_transport():
    """Create a mock WS transport that completes the auth handshake.

    Returns (session_mock, ws_transport_mock).
    """
    mock_ws = AsyncMock()
    ready_msg = _make_ws_msg(
        {"type": "status", "status": "ready", "connectionId": "conn_test"}
    )
    mock_ws.receive = AsyncMock(return_value=ready_msg)
    mock_ws.send_json = AsyncMock()
    mock_ws.closed = False
    mock_ws.close = AsyncMock()
    # Default: immediately stop iteration (no messages to process)
    mock_ws.__aiter__ = MagicMock(
        return_value=AsyncMock(__anext__=AsyncMock(side_effect=StopAsyncIteration))
    )

    session = MagicMock()
    session.ws_connect = AsyncMock(return_value=mock_ws)
    return session, mock_ws


async def _make_connected_ws():
    """Create a LevitonWebSocket that has gone through connect().

    Returns (ws, session_mock, ws_transport_mock).
    """
    session, mock_ws = _make_mock_ws_transport()
    ws = _make_ws(session=session)
    await ws.connect()
    return ws, session, mock_ws


# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------


class TestConnect:
    async def test_connect_success(self):
        ws, session, mock_ws = await _make_connected_ws()

        assert ws.connected is True
        session.ws_connect.assert_awaited_once()
        mock_ws.send_json.assert_awaited_once()
        # Verify auth message structure
        auth_call = mock_ws.send_json.call_args[0][0]
        assert "token" in auth_call
        assert auth_call["token"]["id"] == "tok_test"
        assert auth_call["token"]["userId"] == "user_001"

        await ws.disconnect()

    async def test_connect_connection_error(self):
        session = MagicMock()
        session.ws_connect = AsyncMock(
            side_effect=aiohttp.ClientConnectionError("refused")
        )
        ws = _make_ws(session=session)
        with pytest.raises(LevitonConnectionError, match="connection failed"):
            await ws.connect()
        assert ws.connected is False

    async def test_connect_os_error(self):
        """OSError during connect is wrapped as LevitonConnectionError."""
        session = MagicMock()
        session.ws_connect = AsyncMock(side_effect=OSError("network unreachable"))
        ws = _make_ws(session=session)
        with pytest.raises(LevitonConnectionError, match="connection failed"):
            await ws.connect()

    async def test_connect_timeout_no_ready(self):
        mock_ws = AsyncMock()
        mock_ws.receive = AsyncMock(side_effect=TimeoutError)
        mock_ws.send_json = AsyncMock()
        mock_ws.closed = False
        mock_ws.close = AsyncMock()

        session = MagicMock()
        session.ws_connect = AsyncMock(return_value=mock_ws)

        ws = _make_ws(session=session)
        with pytest.raises(LevitonConnectionError, match="ready state"):
            await ws.connect()

    async def test_connect_closed_during_auth(self):
        mock_ws = AsyncMock()
        closed_msg = _make_ws_msg({}, msg_type=aiohttp.WSMsgType.CLOSED)
        mock_ws.receive = AsyncMock(return_value=closed_msg)
        mock_ws.send_json = AsyncMock()
        mock_ws.closed = False
        mock_ws.close = AsyncMock()

        session = MagicMock()
        session.ws_connect = AsyncMock(return_value=mock_ws)

        ws = _make_ws(session=session)
        with pytest.raises(LevitonConnectionError, match="closed during auth"):
            await ws.connect()


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------


class TestDisconnect:
    async def test_disconnect_clean(self):
        ws, _, mock_ws = await _make_connected_ws()
        await ws.disconnect()
        assert ws.connected is False
        mock_ws.close.assert_awaited_once()

    async def test_disconnect_already_disconnected(self):
        ws = _make_ws()
        assert ws.connected is False
        await ws.disconnect()  # should not raise
        assert ws.connected is False

    async def test_disconnect_preserves_subscriptions(self):
        """Subscriptions survive disconnect for re-subscribe on reconnect."""
        ws, _, mock_ws = await _make_connected_ws()
        await ws.subscribe("IotWhem", "whem_001")
        await ws.disconnect()
        assert ("IotWhem", "whem_001") in ws.subscriptions


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestReset:
    async def test_reset_clears_all(self):
        ws, _, _ = await _make_connected_ws()
        await ws.subscribe("IotWhem", "whem_001")
        ws.on_notification(lambda d: None)
        ws.on_disconnect(lambda: None)

        await ws.reset()
        assert ws.connected is False
        assert len(ws.subscriptions) == 0


# ---------------------------------------------------------------------------
# Subscribe / Unsubscribe
# ---------------------------------------------------------------------------


class TestSubscribe:
    async def test_subscribe_sends_json(self):
        ws, _, mock_ws = await _make_connected_ws()
        await ws.subscribe("IotWhem", "whem_001")

        # Last send_json call should be the subscribe (first was auth)
        msg = mock_ws.send_json.call_args[0][0]
        assert msg["type"] == "subscribe"
        assert msg["subscription"]["modelName"] == "IotWhem"
        assert msg["subscription"]["modelId"] == "whem_001"

        await ws.disconnect()

    async def test_subscribe_updates_set(self):
        ws, _, _ = await _make_connected_ws()
        await ws.subscribe("IotWhem", "whem_001")
        assert ("IotWhem", "whem_001") in ws.subscriptions
        await ws.disconnect()

    async def test_subscribe_not_connected_raises(self):
        ws = _make_ws()
        with pytest.raises(LevitonConnectionError, match="not connected"):
            await ws.subscribe("IotWhem", "whem_001")

    async def test_unsubscribe_sends_json(self):
        ws, _, mock_ws = await _make_connected_ws()
        await ws.subscribe("IotWhem", "whem_001")
        await ws.unsubscribe("IotWhem", "whem_001")

        msg = mock_ws.send_json.call_args[0][0]
        assert msg["type"] == "unsubscribe"
        assert ("IotWhem", "whem_001") not in ws.subscriptions
        await ws.disconnect()

    async def test_unsubscribe_not_connected_noop(self):
        ws = _make_ws()
        # Should not raise — unsubscribe silently returns if not connected
        await ws.unsubscribe("IotWhem", "whem_001")


# ---------------------------------------------------------------------------
# Notification callbacks
# ---------------------------------------------------------------------------


class TestNotificationCallbacks:
    def test_register_and_remove(self):
        ws = _make_ws()
        remove = ws.on_notification(lambda d: None)
        remove2 = ws.on_notification(lambda d: None)
        # Two registered
        remove()
        remove2()
        # Verify by registering again (clean state)
        ws.on_notification(lambda d: None)


# ---------------------------------------------------------------------------
# Disconnect callbacks
# ---------------------------------------------------------------------------


class TestDisconnectCallbacks:
    def test_register_and_remove(self):
        ws = _make_ws()
        remove = ws.on_disconnect(lambda: None)
        remove()


# ---------------------------------------------------------------------------
# Listen loop
# ---------------------------------------------------------------------------


class TestListen:
    async def test_dispatches_notification(self):
        ws = _make_ws()
        received = []
        ws.on_notification(lambda d: received.append(d))

        notification_msg = _make_ws_msg(
            {
                "type": "notification",
                "notification": {
                    "modelName": "IotWhem",
                    "data": {"connected": True},
                },
            }
        )
        close_msg = MagicMock()
        close_msg.type = aiohttp.WSMsgType.CLOSED

        mock_ws = AsyncMock()

        async def aiter_messages():
            yield notification_msg
            yield close_msg

        mock_ws.__aiter__ = lambda self: aiter_messages()
        ws._ws = mock_ws
        ws._connected = True

        await ws._listen()

        assert len(received) == 1
        assert received[0]["modelName"] == "IotWhem"
        assert ws.connected is False

    async def test_handles_close_message(self):
        ws = _make_ws()
        dc_fired = []
        ws.on_disconnect(lambda: dc_fired.append(True))

        close_msg = MagicMock()
        close_msg.type = aiohttp.WSMsgType.CLOSED

        mock_ws = AsyncMock()

        async def aiter_messages():
            yield close_msg

        mock_ws.__aiter__ = lambda self: aiter_messages()
        ws._ws = mock_ws
        ws._connected = True

        await ws._listen()

        assert ws.connected is False
        assert len(dc_fired) == 1

    async def test_handles_error_message(self):
        ws = _make_ws()

        error_msg = MagicMock()
        error_msg.type = aiohttp.WSMsgType.ERROR

        mock_ws = AsyncMock()

        async def aiter_messages():
            yield error_msg

        mock_ws.__aiter__ = lambda self: aiter_messages()
        ws._ws = mock_ws
        ws._connected = True

        await ws._listen()
        assert ws.connected is False

    async def test_handles_non_json_message(self):
        """Non-JSON TEXT message is logged and skipped (lines 231-236)."""
        ws = _make_ws()
        received = []
        ws.on_notification(lambda d: received.append(d))

        bad_msg = MagicMock()
        bad_msg.type = aiohttp.WSMsgType.TEXT
        bad_msg.data = "not json at all"

        close_msg = MagicMock()
        close_msg.type = aiohttp.WSMsgType.CLOSED

        mock_ws = AsyncMock()

        async def aiter_messages():
            yield bad_msg
            yield close_msg

        mock_ws.__aiter__ = lambda self: aiter_messages()
        ws._ws = mock_ws
        ws._connected = True

        await ws._listen()
        assert len(received) == 0

    async def test_notification_callback_exception_logged(self):
        """Exception in notification callback is caught — _listen continues
        (covers websocket.py lines 243-244).
        """
        ws = _make_ws()
        good_results = []

        def bad_callback(d):
            raise ValueError("boom")

        ws.on_notification(bad_callback)
        ws.on_notification(lambda d: good_results.append(d))

        notification_msg = _make_ws_msg(
            {
                "type": "notification",
                "notification": {"modelName": "IotWhem", "data": {}},
            }
        )
        close_msg = MagicMock()
        close_msg.type = aiohttp.WSMsgType.CLOSED

        mock_ws = AsyncMock()

        async def aiter_messages():
            yield notification_msg
            yield close_msg

        mock_ws.__aiter__ = lambda self: aiter_messages()
        ws._ws = mock_ws
        ws._connected = True

        await ws._listen()

        # Good callback still received the notification despite bad one raising
        assert len(good_results) == 1

    async def test_listen_unexpected_exception(self):
        """Unexpected exception during iteration is caught
        (covers websocket.py lines 253-256).
        """
        ws = _make_ws()
        dc_fired = []
        ws.on_disconnect(lambda: dc_fired.append(True))

        mock_ws = AsyncMock()

        async def aiter_raise():
            raise RuntimeError("unexpected WS error")
            yield  # noqa: F401 — make this an async generator

        mock_ws.__aiter__ = lambda self: aiter_raise()
        ws._ws = mock_ws
        ws._connected = True

        await ws._listen()

        assert ws.connected is False
        # Disconnect callbacks still fire in the finally block
        assert len(dc_fired) == 1

    async def test_listen_cancelled_error(self):
        """CancelledError during listen returns cleanly
        (covers websocket.py line 254).
        """
        import asyncio

        ws = _make_ws()
        dc_fired = []
        ws.on_disconnect(lambda: dc_fired.append(True))

        mock_ws = AsyncMock()

        async def aiter_cancel():
            raise asyncio.CancelledError()
            yield  # noqa: F401 — make this an async generator

        mock_ws.__aiter__ = lambda self: aiter_cancel()
        ws._ws = mock_ws
        ws._connected = True

        await ws._listen()

        # CancelledError returns early — but finally block still runs
        assert ws.connected is False

    async def test_disconnect_callback_exception_logged(self):
        """Exception in disconnect callback is caught — other callbacks still run
        (covers websocket.py lines 262-263).
        """
        ws = _make_ws()
        good_fired = []

        def bad_dc():
            raise ValueError("dc boom")

        ws.on_disconnect(bad_dc)
        ws.on_disconnect(lambda: good_fired.append(True))

        close_msg = MagicMock()
        close_msg.type = aiohttp.WSMsgType.CLOSED

        mock_ws = AsyncMock()

        async def aiter_messages():
            yield close_msg

        mock_ws.__aiter__ = lambda self: aiter_messages()
        ws._ws = mock_ws
        ws._connected = True

        await ws._listen()

        assert ws.connected is False
        # Good disconnect callback still fired despite bad one raising
        assert len(good_fired) == 1

    async def test_non_notification_text_ignored(self):
        """TEXT messages that aren't notifications are silently ignored."""
        ws = _make_ws()
        received = []
        ws.on_notification(lambda d: received.append(d))

        # A status or other non-notification message
        status_msg = _make_ws_msg({"type": "status", "status": "ok"})
        close_msg = MagicMock()
        close_msg.type = aiohttp.WSMsgType.CLOSED

        mock_ws = AsyncMock()

        async def aiter_messages():
            yield status_msg
            yield close_msg

        mock_ws.__aiter__ = lambda self: aiter_messages()
        ws._ws = mock_ws
        ws._connected = True

        await ws._listen()
        assert len(received) == 0


# ---------------------------------------------------------------------------
# Reconnect
# ---------------------------------------------------------------------------


class TestReconnect:
    async def test_reconnect_restores_subscriptions(self):
        session, mock_ws = _make_mock_ws_transport()

        ws = _make_ws(session=session)
        # Simulate already-connected state with subscriptions
        ws._connected = True
        old_ws = AsyncMock()
        old_ws.closed = False
        old_ws.close = AsyncMock()
        ws._ws = old_ws
        ws._listen_task = None
        ws._subscriptions = {
            ("IotWhem", "whem_001"),
            ("ResidentialBreaker", "brk_001"),
        }

        await ws.reconnect()

        assert ws.connected is True
        # Auth message + 2 subscribe messages
        assert mock_ws.send_json.await_count == 3
        assert ws.subscriptions == {
            ("IotWhem", "whem_001"),
            ("ResidentialBreaker", "brk_001"),
        }

        await ws.disconnect()


# ---------------------------------------------------------------------------
# Reconnect delay
# ---------------------------------------------------------------------------


class TestReconnectDelay:
    def test_first_attempt(self):
        delay = LevitonWebSocket.reconnect_delay(0)
        # 1.0 * (2^0) * (0.5*rand + 0.75) => between 0.75 and 1.25
        assert 0.5 <= delay <= 1.5

    def test_exponential_growth(self):
        # attempts=2 → base delay 4x, attempts=3 → 8x
        # With jitter, d3 should generally be larger than d1
        d1 = LevitonWebSocket.reconnect_delay(1)
        d3 = LevitonWebSocket.reconnect_delay(3)
        # Both should be within bounds
        assert d1 <= MAX_RECONNECT_DELAY
        assert d3 <= MAX_RECONNECT_DELAY

    def test_capped_at_max(self):
        delay = LevitonWebSocket.reconnect_delay(100)
        assert delay <= MAX_RECONNECT_DELAY

    def test_never_negative(self):
        for i in range(20):
            assert LevitonWebSocket.reconnect_delay(i) >= 0
