import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
from app.services.market_data import fetch_quote
from app.services.alert_service import cache_price


class ConnectionManager:
    """
    Manages all active WebSocket connections.
    Each user can subscribe to multiple pairs.
    """

    def __init__(self):
        # Maps websocket -> set of pairs subscribed to
        self.active_connections: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = set()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    def subscribe(self, websocket: WebSocket, pairs: list):
        """Subscribe a connection to a list of pairs."""
        if websocket in self.active_connections:
            self.active_connections[websocket].update(pairs)

    async def send_to(self, websocket: WebSocket, data: dict):
        """Send data to a specific connection."""
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            self.disconnect(websocket)

    async def broadcast_price(self, pair: str, price: float):
        """Broadcast a price update to all connections subscribed to that pair."""
        message = {
            "type": "price_update",
            "pair": pair,
            "price": price,
        }
        disconnected = []
        for websocket, pairs in self.active_connections.items():
            if pair in pairs:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception:
                    disconnected.append(websocket)

        for ws in disconnected:
            self.disconnect(ws)

    def get_all_subscribed_pairs(self) -> Set[str]:
        """Get all pairs currently being watched across all connections."""
        all_pairs = set()
        for pairs in self.active_connections.values():
            all_pairs.update(pairs)
        return all_pairs


# Global connection manager instance
manager = ConnectionManager()


async def price_broadcast_loop():
    """
    Background task that fetches prices every 10 seconds
    and broadcasts to all subscribed WebSocket clients.
    """
    while True:
        try:
            pairs = manager.get_all_subscribed_pairs()
            if pairs:
                for pair in pairs:
                    quote = await fetch_quote(pair)
                    if quote:
                        price = quote["price"]
                        # Cache in Redis
                        cache_price(pair, price)
                        # Broadcast to subscribed clients
                        await manager.broadcast_price(pair, price)
                        await asyncio.sleep(0.5)  # small delay between pairs
        except Exception as e:
            print(f"Price broadcast error: {e}")

        await asyncio.sleep(10)  # fetch every 10 seconds


async def handle_price_websocket(websocket: WebSocket):
    """
    Handle a WebSocket connection for live price streaming.

    Client sends:
        {"action": "subscribe", "pairs": ["EUR/USD", "GBP/USD"]}
        {"action": "unsubscribe", "pairs": ["EUR/USD"]}

    Server sends:
        {"type": "price_update", "pair": "EUR/USD", "price": 1.08542}
        {"type": "connected", "message": "Connected to Forex Intel price feed"}
        {"type": "error", "message": "..."}
    """
    await manager.connect(websocket)

    try:
        # Send welcome message
        await manager.send_to(websocket, {
            "type": "connected",
            "message": "Connected to Forex Intel live price feed",
        })

        while True:
            # Wait for client messages
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                action = data.get("action")
                pairs = data.get("pairs", [])

                if action == "subscribe" and pairs:
                    manager.subscribe(websocket, pairs)
                    await manager.send_to(websocket, {
                        "type": "subscribed",
                        "pairs": pairs,
                        "message": f"Subscribed to {', '.join(pairs)}",
                    })

                    # Send immediate price for each pair
                    for pair in pairs:
                        quote = await fetch_quote(pair)
                        if quote:
                            await manager.send_to(websocket, {
                                "type": "price_update",
                                "pair": pair,
                                "price": quote["price"],
                            })

                elif action == "unsubscribe" and pairs:
                    for pair in pairs:
                        manager.active_connections[websocket].discard(pair)
                    await manager.send_to(websocket, {
                        "type": "unsubscribed",
                        "pairs": pairs,
                    })

                elif action == "ping":
                    await manager.send_to(websocket, {"type": "pong"})

            except json.JSONDecodeError:
                await manager.send_to(websocket, {
                    "type": "error",
                    "message": "Invalid JSON format.",
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)