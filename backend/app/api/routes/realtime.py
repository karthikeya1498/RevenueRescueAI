"""Real-time recovery event stream for the dashboard.

The stream is intentionally deterministic for the current foundation milestone:
it models the shape of processor and workflow events without performing payment
provider actions. A production adapter can publish the same event contract.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from itertools import cycle
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["realtime"])

DEMO_EVENTS: tuple[dict[str, Any], ...] = (
    {
        "type": "recovery.payment_recovered",
        "title": "Payment recovered",
        "message": "Northstar Labs paid $12,480",
        "account": "Northstar Labs",
        "amount": 12480,
        "severity": "success",
        "icon": "check",
    },
    {
        "type": "recovery.risk_signal",
        "title": "New risk signal detected",
        "message": "Asteria Living needs review before the next retry",
        "account": "Asteria Living",
        "amount": 8920,
        "severity": "warning",
        "icon": "activity",
    },
    {
        "type": "recovery.playbook_completed",
        "title": "Playbook completed",
        "message": "Card expiry recovery completed for 42 accounts",
        "account": "Card expiry recovery",
        "amount": 18640,
        "severity": "info",
        "icon": "spark",
    },
)


def event_payload(event: dict[str, Any]) -> str:
    """Return a versioned event envelope shared by all realtime clients."""
    return json.dumps(
        {
            "version": 1,
            "id": f"demo-{datetime.now(UTC).timestamp()}",
            "occurred_at": datetime.now(UTC).isoformat(),
            "event": event,
        }
    )


@router.websocket("/ws/recovery")
async def recovery_events(websocket: WebSocket) -> None:
    """Stream heartbeat and demo recovery events until the client disconnects."""
    await websocket.accept()
    await websocket.send_text(
        event_payload(
            {
                "type": "connection.ready",
                "title": "Live recovery feed connected",
                "message": "You are receiving workspace events in real time.",
                "severity": "system",
                "icon": "activity",
            }
        )
    )

    events = cycle(DEMO_EVENTS)
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                if message == "ping":
                    await websocket.send_text(
                        event_payload(
                            {
                                "type": "connection.pong",
                                "title": "Live feed healthy",
                                "message": "Heartbeat acknowledged.",
                                "severity": "system",
                                "icon": "shield",
                            }
                        )
                    )
            except asyncio.TimeoutError:
                await websocket.send_text(event_payload(next(events)))
    except WebSocketDisconnect:
        return
