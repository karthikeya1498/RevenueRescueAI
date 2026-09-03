"""Contract tests for the live recovery event stream."""
from fastapi.testclient import TestClient

from app.main import app


def test_recovery_websocket_handshake_and_heartbeat() -> None:
    client = TestClient(app)

    with client.websocket_connect("/ws/recovery") as websocket:
        connected = websocket.receive_json()
        assert connected["version"] == 1
        assert connected["event"]["type"] == "connection.ready"

        websocket.send_text("ping")
        pong = websocket.receive_json()
        assert pong["version"] == 1
        assert pong["event"]["type"] == "connection.pong"
